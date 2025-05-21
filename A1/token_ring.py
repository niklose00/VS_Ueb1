import multiprocessing
import socket
import json
import time
import random
import struct
import sys
from select import select

MCAST_GRP = '224.0.0.1'
MCAST_PORT = 5007
BASE_PORT = 20000
BUFFER_SIZE = 1024
TOKEN_TIMEOUT = 5

def make_socket(port, multicast=False):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except AttributeError:
        pass
    sock.bind(('127.0.0.1', port))
    if multicast:
        mreq = struct.pack("=4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return sock

def send_multicast(message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    ttl = struct.pack('b', 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
    sock.sendto(message.encode(), (MCAST_GRP, MCAST_PORT))
    sock.close()

def node_process(i, n, p_init, k, stats_q):
    recv_port = BASE_PORT + i
    next_port = BASE_PORT + ((i + 1) % n)
    recv_sock = make_socket(recv_port)
    mcast_sock = make_socket(MCAST_PORT, multicast=True)

    firework_count = 0
    token_rounds = 0
    round_times = []
    silent_rounds = 0
    p = p_init

    print(f"[{i}] Prozess gestartet. Warte auf Token an Port {recv_port}")

    while True:
        start = time.time()
        rlist, _, _ = select([recv_sock], [], [], TOKEN_TIMEOUT)
        if not rlist:
            print(f"[{i}] Timeout – kein Token empfangen")
            break

        data, _ = recv_sock.recvfrom(BUFFER_SIZE)
        token = json.loads(data.decode())
        print(f"[{i}] Token empfangen: {token}")
        token_rounds += 1
        launched = False

        if random.random() < p:
            send_multicast(json.dumps({'node': i, 'round': token['round']}))
            firework_count += 1
            launched = True

        if i == 0:
            if launched:
                silent_rounds = 0
            else:
                silent_rounds += 1
            token['round'] += 1
            token['p'] /= 2
            if silent_rounds >= k:
                print(f"[{i}] Terminierung nach {k} stillen Runden")
                break
        else:
            token['p'] = p

        p = token['p']
        end = time.time()
        round_times.append(end - start)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(json.dumps(token).encode(), ('127.0.0.1', next_port))
        sock.close()

    stats_q.put({
        'node': i,
        'rounds': token_rounds,
        'fireworks': firework_count,
        'round_times': round_times
    })

def run_ring(n, p, k):
    stats_q = multiprocessing.Queue()
    procs = []

    for i in range(n):
        proc = multiprocessing.Process(target=node_process, args=(i, n, p, k, stats_q))
        proc.start()
        time.sleep(0.1)

        procs.append(proc)

    time.sleep(1.0)

    init_token = {'round': 0, 'p': p}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(json.dumps(init_token).encode(), ('127.0.0.1', BASE_PORT))
    sock.close()

    for proc in procs:
        proc.join()

    return [stats_q.get() for _ in range(n)]
