from scapy import all
import threading
import queue
import logging
import flask
import json

logger = logging.getLogger("listener")
logger.setLevel(logging.INFO)

fh = logging.FileHandler(f"listener.log",mode='w')
fh.setLevel(logging.INFO)


queue_lock = threading.Lock()

logger.addHandler(fh)

SERVER_HOST = '127.0.0.1'
PORT = 5000
done = False

conversations = {}
pending_conversations = queue.Queue()

def place_conversation(pkt):
    global conversations
    global pending_conversations

    queue_lock.acquire()
    pkt = pkt['TCP']
    cli_port = pkt.dport if pkt.dport != PORT else pkt.sport
    if cli_port in conversations.keys():
        logger.info(f"Added {pkt} to queue {cli_port}")
        conversations[cli_port].put(pkt)
    elif 'S' in pkt.flags:
        logger.info(f"Found new conversation {cli_port} opened with {pkt}")
        conversations[cli_port] = queue.Queue()
        conversations[cli_port].put(pkt)
        pending_conversations.put(cli_port)
    else:
        logger.info(f"Skipped packet due to nonexistent/cleared conversation: {pkt}")
    queue_lock.release()
    

def find_packets():
    while not done:
        logger.info("Begin sniffing")
        all.sniff(prn=place_conversation,filter='tcp src or dst port 5000',store=0,stop_filter=lambda p: done)

class ResetException(Exception):
    pass

def get_conversation_length(conversation: int):
    global conversations

    first_fin = False

    conversation_client_port = None
    client_to_server = 0
    server_to_client = 0

    client_base_ack = None
    server_base_ack = None

    while True:
        try:
            pkt = conversations[conversation].get(timeout = None if conversation_client_port is None else 2)['TCP'] #TODO: change timeout to instead stop when a message is received from the attacker server.
            logger.info(f"Processing {pkt} for conversation port {conversation}")
        except KeyError as k:
            raise k
        except:
            return client_to_server,server_to_client
        
        if conversation_client_port is None: #set the client's port for this conversation so we can ignore irrelevant packets
            conversation_client_port = pkt.sport
            logger.info(f"conversation started on port {conversation_client_port}")

        if conversation_client_port == pkt.sport or conversation_client_port == pkt.dport:
            if 'S' in pkt.flags and pkt.dport == PORT:
                logger.info("SYN")
                logger.info(f"seq = {pkt.seq} ack = {pkt.ack}")
                server_base_ack = pkt.seq
            elif 'S' in pkt.flags:
                logger.info("SYN-ACK")
                logger.info(f"seq = {pkt.seq} ack = {pkt.ack}")

                logger.info(pkt.seq)
                client_base_ack = pkt.seq
            elif 'A' in pkt.flags and pkt.dport == PORT and pkt.ack - client_base_ack > server_to_client:
                logger.info(f"client ACK {pkt.ack}")
                server_to_client = pkt.ack - client_base_ack 
            elif 'A' in pkt.flags and pkt.dport != PORT and pkt.ack - server_base_ack > client_to_server:
                logger.info(f"server ACK {pkt.ack}")
                client_to_server = pkt.ack - server_base_ack
            
            if 'F' in pkt.flags and first_fin:
                return client_to_server, server_to_client #This may miss a little data from client_to_server in non HTTP connections. However, in HTTP a client has already finished sending the request at this point.
            elif 'F' in pkt.flags:
                first_fin = True
            elif 'R' in pkt.flags:
                raise ResetException("Connection was reset")

def page_len()->int:
    
    global pending_conversations

    while True:
        c = pending_conversations.get()
        logger.info(f"found conversation on client port {c}")

        request_len, response_len = get_conversation_length(c)
        logger.info(f"Conversation length: client -> server {request_len}, server -> client {response_len}, total: {request_len+response_len}")
        if request_len > 1000 and response_len > 1000:
            break
    return response_len

server_logger = logging.getLogger("server")
server_logger.setLevel(logging.DEBUG)
fh = logging.FileHandler("server.log",mode='w')
fh.setLevel(logging.DEBUG)
server_logger.addHandler(fh)
app = flask.Flask(__name__)
app.config['LOGGER'] = server_logger

@app.route("/conversations",methods=['DELETE'])
def reset():
    queue_lock.acquire()
    global pending_conversations
    global conversations
    flask.current_app.config["LOGGER"].debug("cleared conversations")
    logger.info("Cleared packets from queue")
    pending_conversations = queue.Queue()
    conversations = {}
    queue_lock.release()
    return "", 204


@app.route("/conversations/page_len")
def get_page_len():
    flask.current_app.config['LOGGER'].debug("getting page length")
    try:
        ln = page_len()
        flask.current_app.config['LOGGER'].debug(f"Got length {ln}")
        return json.dumps({"page_size": ln})
    except Exception as e:
        flask.current_app.config['LOGGER'].error(e)
        return str(e), 500

@app.route("/")
def ping():
    flask.current_app.config['LOGGER'].debug("Received ping command")
    return "", 204

def main():
    listener = threading.Thread(target=find_packets)
    listener.start()
    app.run("0.0.0.0",7000)

if __name__ == "__main__":
    main()