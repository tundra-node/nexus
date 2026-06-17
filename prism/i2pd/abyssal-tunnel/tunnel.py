import socket, threading, time, os, sys, logging, json, base64, hashlib

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("tunnel")

SAM_HOST = os.environ.get("SAM_HOST", "i2pd")
SAM_PORT = int(os.environ.get("SAM_PORT", "7656"))
KEYS_DIR = os.environ.get("KEYS_DIR", "/data/tunnel-keys")

TUNNELS = [
    {"name": "abyssal", "backend_host": "abyssal-frontend", "backend_port": 80},
    {"name": "abyssal-api", "backend_host": "abyssal-backend", "backend_port": 8000},
]


def recv_line(sock, timeout=30):
    sock.settimeout(timeout)
    buf = b""
    while True:
        c = sock.recv(1)
        if not c:
            return None
        if c == b"\n":
            return buf.decode().strip()
        buf += c


def read_forward(sock, buf_size=65536):
    try:
        return sock.recv(buf_size)
    except:
        return b""


def generate_keys(name):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(30)
    s.connect((SAM_HOST, SAM_PORT))
    s.sendall(b"HELLO VERSION\n")
    recv_line(s)
    s.sendall(b"DEST GENERATE\n")
    resp = recv_line(s, timeout=10)
    s.close()
    if resp and resp.startswith("DEST REPLY"):
        parts = resp.split()
        pub = priv = ""
        for p in parts:
            if p.startswith("PUB="):
                pub = p.split("=", 1)[1]
            elif p.startswith("PRIV="):
                priv = p.split("=", 1)[1]
        if priv:
            return priv
    raise RuntimeError(f"Key generation failed: {resp}")


def load_or_create_keys(name):
    os.makedirs(KEYS_DIR, exist_ok=True)
    path = os.path.join(KEYS_DIR, f"{name}.keys")
    try:
        with open(path) as f:
            key = f.read().strip()
            if key:
                log.info(f"[{name}] Loaded existing keys ({len(key)} chars)")
                return key
    except:
        pass
    key = generate_keys(name)
    with open(path, "w") as f:
        f.write(key + "\n")
    log.info(f"[{name}] Generated new keys ({len(key)} chars)")
    return key


def get_b32(dest_b64):
    b64 = dest_b64.replace('~', '=').replace('-', '+').replace('_', '/')
    pad = 4 - len(b64) % 4
    if pad != 4:
        b64 += '=' * pad
    raw = base64.b64decode(b64)
    h = hashlib.sha256(raw).digest()
    return base64.b32encode(h).decode().lower().replace('=', '')


def run_tunnel(cfg):
    name = cfg["name"]
    bh = cfg["backend_host"]
    bp = cfg["backend_port"]

    while True:
        notif_sock = None
        try:
            full_key = load_or_create_keys(name)
            b32 = get_b32(full_key)
            log.info(f"[{name}] b32: ...{b32[:20]}")

            notif_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            notif_sock.settimeout(30)
            notif_sock.connect((SAM_HOST, SAM_PORT))
            notif_sock.sendall(b"HELLO VERSION\n")
            resp = recv_line(notif_sock)
            if not resp or "RESULT=OK" not in resp:
                raise ConnectionError(f"SAM hello failed: {resp}")

            session_id = f"tun_{name}_{int(time.time())}_{os.urandom(2).hex()}"
            cmd = f"SESSION CREATE STYLE=STREAM ID={session_id} DESTINATION={full_key}"
            log.info(f"[{name}] Sending: {cmd[:120]}...")
            notif_sock.sendall((cmd + "\n").encode())
            resp = recv_line(notif_sock, timeout=30)
            log.info(f"[{name}] Session: {resp}")

            if resp and "RESULT=OK" in resp:
                pub_dest = ""
                for part in resp.split():
                    if part.startswith("DESTINATION="):
                        pub_dest = part.split("=", 1)[1]
                b32_addr = get_b32(pub_dest)
                log.info(f"[{name}] b32: {b32_addr}.b32.i2p")

                notif_sock.settimeout(None)
                buf = b""
                while True:
                    data = notif_sock.recv(4096)
                    if not data:
                        break
                    buf += data
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        line_s = line.decode().strip()
                        if "STREAM STATUS" in line_s:
                            sid = ""
                            for part in line_s.split():
                                if part.startswith("STREAM="):
                                    sid = part.split("=", 1)[1]
                            if sid:
                                threading.Thread(
                                    target=handle_stream,
                                    args=(name, session_id, sid, bh, bp),
                                    daemon=True,
                                ).start()
            else:
                log.warning(f"[{name}] Session failed, retrying in 15s")
                time.sleep(15)
        except Exception as e:
            log.error(f"[{name}] Error: {e}")
            time.sleep(5)
        finally:
            if notif_sock:
                try:
                    notif_sock.close()
                except:
                    pass
        log.info(f"[{name}] Reconnecting in 15s...")
        time.sleep(15)


def handle_stream(name, session_id, sid, backend_host, backend_port):
    log.info(f"[{name}] Incoming stream SID={sid[:24]}...")
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(30)
        s.connect((SAM_HOST, SAM_PORT))
        s.sendall(b"HELLO VERSION\n")
        resp = recv_line(s)
        if not resp or "RESULT=OK" not in resp:
            return

        s.sendall(f"STREAM ACCEPT ID={session_id} SID={sid}\n".encode())
        resp = recv_line(s, timeout=10)

        if not resp:
            log.warning(f"[{name}] No accept response for SID={sid[:24]}")
            return
        if "RESULT=OK" not in resp:
            log.warning(f"[{name}] Accept failed: {resp[:100]}")
            return

        backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        backend.settimeout(30)
        backend.connect((backend_host, backend_port))

        s.settimeout(None)
        backend.settimeout(None)

        data = s.recv(8192)
        if data:
            backend.sendall(data)

        s.settimeout(30)
        while True:
            try:
                data = s.recv(65536)
                if not data:
                    break
                backend.sendall(data)
            except socket.timeout:
                pass

            try:
                backend.settimeout(0.1)
                data = backend.recv(65536)
                if not data:
                    break
                s.sendall(data)
            except socket.timeout:
                continue
            except:
                break
    except Exception as e:
        log.debug(f"[{name}] Stream error: {e}")
    finally:
        if s:
            try:
                s.close()
            except:
                pass
        try:
            backend.close()
        except:
            pass


def collect_and_write_tunnel_info():
    """Read persisted keys and write /data/tunnel-info.json with b32 addresses."""
    info = []
    for t in TUNNELS:
        path = os.path.join(KEYS_DIR, f"{t['name']}.keys")
        try:
            with open(path) as f:
                full_key = f.read().strip()
            b32 = get_b32(full_key)
            b32_full = f"{b32}.b32.i2p"
            info.append({
                "name": t["name"],
                "b32": b32,
                "b32_address": b32_full,
                "host": t["backend_host"],
                "port": t["backend_port"],
            })
        except Exception as e:
            log.warning(f"[{t['name']}] Could not read keys for info file: {e}")
    if info:
        out_path = os.path.join(os.path.dirname(KEYS_DIR), "tunnel-info.json")
        with open(out_path, "w") as f:
            json.dump(info, f, indent=2)
        log.info(f"Wrote tunnel info to {out_path}: {[i['b32_address'] for i in info]}")


def main():
    log.info("Abyssal SAM Tunnel Service")
    log.info(f"SAM: {SAM_HOST}:{SAM_PORT}, Keys: {KEYS_DIR}")

    for attempt in range(60):
        try:
            s = socket.create_connection((SAM_HOST, SAM_PORT), timeout=2)
            s.close()
            log.info("SAM reachable!")
            break
        except:
            if attempt % 10 == 0:
                log.info(f"Waiting SAM... ({attempt + 1}/60)")
            time.sleep(2)

    for attempt in range(60):
        all_ok = True
        for t in TUNNELS:
            try:
                s = socket.create_connection((t["backend_host"], t["backend_port"]), timeout=2)
                s.close()
            except:
                all_ok = False
        if all_ok:
            log.info("Backends reachable!")
            break
        if attempt % 10 == 0:
            log.info(f"Waiting backends... ({attempt + 1}/60)")
        time.sleep(2)

    threads = [threading.Thread(target=run_tunnel, args=(t,), daemon=True) for t in TUNNELS]
    for t in threads:
        t.start()
    log.info("All tunnels started")

    # Schedule periodic tunnel-info writes
    def write_loop():
        while True:
            time.sleep(30)
            collect_and_write_tunnel_info()

    threading.Thread(target=write_loop, daemon=True).start()

    # Write initial info after short delay
    time.sleep(5)
    collect_and_write_tunnel_info()

    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
