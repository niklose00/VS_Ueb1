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
USE_MULTICAST = True  # wird durch Argument gesteuert

def make_socket(bind_host, bind_port, multicast=False):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((bind_host, bind_port))
    if multicast:
        mreq = struct.pack("=4s4s", socket.inet_aton(MCAST_GRP), socket.inet_aton(bind_host))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return sock

def send_multicast(message, my_id=None, peers=None):
    if USE_MULTICAST:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        ttl = struct.pack('b', 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        sock.sendto(message.encode(), (MCAST_GRP, MCAST_PORT))
        sock.close()
    else:
        for peer in peers:
            if peer["id"] != my_id:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(message.encode(), (peer["host"], peer["port"]))
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
    round_times = []

    print(f"[Node {my_id}] Starte an {me['host']}:{me['port']}, nächster: {next_peer['host']}:{next_peer['port']}")

    if my_id == 0:
        time.sleep(2)
        init_token = {"round": 0, "p": p}
        sock.sendto(json.dumps(init_token).encode(), (next_peer['host'], next_peer['port']))

    while True:
        start_time = time.time()
        rlist, _, _ = select([sock], [], [], TOKEN_TIMEOUT)
        if not rlist:
            print(f"[Node {my_id}] TIMEOUT – Token verloren?")
            break

        data, _ = sock.recvfrom(BUFFER_SIZE)
        round_times.append(time.time() - start_time)
        token = json.loads(data.decode())
        round_num += 1
        launched = False

        if random.random() < p:
            send_multicast(json.dumps({'node': my_id, 'round': token['round']}), my_id, peers)
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

    stats = {
        "id": my_id,
        "host": me["host"],
        "port": me["port"],
        "rounds": round_num,
        "fireworks": firework_count,
        "silent_rounds_until_stop": silent_rounds,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    if round_times:
        stats["min_round_time"] = min(round_times)
        stats["max_round_time"] = max(round_times)
        stats["avg_round_time"] = sum(round_times) / len(round_times)
    else:
        stats["min_round_time"] = stats["max_round_time"] = stats["avg_round_time"] = None

    with open(f"stats_node_{my_id}.json", "w") as f:
        json.dump(stats, f, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, required=True, help="ID des Knotens laut peers.json")
    parser.add_argument("--config", type=str, required=True, help="Pfad zur peers.json")
    parser.add_argument("--p", type=float, required=True, help="Initiale Wahrscheinlichkeit p")
    parser.add_argument("--k", type=int, required=True, help="Anzahl stiller Runden zur Terminierung")
    parser.add_argument("--unicast", action="store_true", help="Fallback zu Unicast statt Multicast")
    args = parser.parse_args()

    USE_MULTICAST = not args.unicast
    run_node(args.id, args.config, args.p, args.k)
