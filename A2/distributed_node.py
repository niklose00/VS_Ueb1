import socket
import json
import time
import random
import struct
import argparse
from select import select

MCAST_GRP = '224.0.0.1'
MCAST_PORT = 5007
BUFFER_SIZE = 1024
TOKEN_TIMEOUT = 5

def make_socket(bind_host, bind_port, multicast=False):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((bind_host, bind_port))
    if multicast:
        mreq = struct.pack("=4s4s", socket.inet_aton(MCAST_GRP), socket.inet_aton(bind_host))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return sock

def send_multicast(message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    ttl = struct.pack('b', 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
    sock.sendto(message.encode(), (MCAST_GRP, MCAST_PORT))
    sock.close()

def run_node(my_id, peer_config_path, p_init, k):
    with open(peer_config_path) as f:
        peers = json.load(f)

    me = peers[my_id]
    n = len(peers)
    next_peer = peers[(my_id + 1) % n]

    sock = make_socket(me["host"], me["port"])
    mcast_sock = make_socket(me["host"], MCAST_PORT, multicast=True)

    p = p_init
    silent_rounds = 0
    round_num = 0
    firework_count = 0

    print(f"[Node {my_id}] Starte an {me['host']}:{me['port']}, nächster: {next_peer['host']}:{next_peer['port']}")

    if my_id == 0:
        time.sleep(2)
        init_token = {"round": 0, "p": p}
        sock.sendto(json.dumps(init_token).encode(), (next_peer['host'], next_peer['port']))

    while True:
        rlist, _, _ = select([sock], [], [], TOKEN_TIMEOUT)
        if not rlist:
            print(f"[Node {my_id}] TIMEOUT – Token verloren?")
            break

        data, _ = sock.recvfrom(BUFFER_SIZE)
        token = json.loads(data.decode())
        round_num += 1
        launched = False

        if random.random() < p:
            send_multicast(json.dumps({'node': my_id, 'round': token['round']}))
            firework_count += 1
            launched = True

        if my_id == 0:
            token['round'] += 1
            token['p'] /= 2
            p = token['p']
            silent_rounds = 0 if launched else silent_rounds + 1
            if silent_rounds >= k:
                print(f"[Node {my_id}] Terminierungsbedingung erreicht.")
                break
        else:
            p = token['p']

        sock.sendto(json.dumps(token).encode(), (next_peer['host'], next_peer['port']))

    print(f"[Node {my_id}] Beendet. Runden: {round_num}, Feuerwerke: {firework_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, required=True, help="ID des Knotens laut peers.json")
    parser.add_argument("--config", type=str, required=True, help="Pfad zur peers.json")
    parser.add_argument("--p", type=float, required=True, help="Initiale Wahrscheinlichkeit p")
    parser.add_argument("--k", type=int, required=True, help="Anzahl stiller Runden für Terminierung")
    args = parser.parse_args()

    run_node(args.id, args.config, args.p, args.k)
