import time
import socket
import requests
from simconnect_mobiflight import SimConnectMobiFlight
from mobiflight_variable_requests import MobiFlightVariableRequests
import json

################################ CONFIG ################################

BASE_URL = "http://localhost"
HTTP_PORT = 8080
TCP_PORT = 8081

PING_INTERVAL = 2.0
SEND_INTERVAL = 1.0
SOCKET_TIMEOUT = 0.2

last_ping = 0.0
last_send = 0.0

#######################################################################
# HEARTBEAT
#######################################################################

def handle_ping():
    global last_ping
    now = time.time()
    if now - last_ping < PING_INTERVAL:
        return
    last_ping = now
    try:
        r = requests.get(f"{BASE_URL}:{HTTP_PORT}/ping", timeout=1)
        if r.status_code == 200:
            token = r.json().get("token")
            if token:
                requests.post(
                    f"{BASE_URL}:{HTTP_PORT}/pong",
                    json={"token": token, "code": 657},
                    timeout=1
                )
    except requests.RequestException:
        pass

#######################################################################
# APP INFO
#######################################################################

def get_app_info():
    handle_ping()
    try:
        r = requests.get(f"{BASE_URL}:{HTTP_PORT}/app-info", timeout=1)
        if r.status_code != 200:
            return None
        return r.json()
    except requests.RequestException:
        return None

#######################################################################
# TCP SERVER
#######################################################################

def create_server_socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", TCP_PORT))
    s.listen(5)
    s.settimeout(SOCKET_TIMEOUT)
    print(f"[SERVER] Listening on {TCP_PORT}")
    return s

def try_accept(server_socket, conn, expected_code):
    if conn:
        return conn

    try:
        conn, addr = server_socket.accept()
        conn.settimeout(SOCKET_TIMEOUT)
        print(f"[SERVER] Client connected from {addr}")

        hello = conn.recv(1024).decode().strip()
        if not hello.startswith("HELLO|"):
            conn.close()
            return None

        _, client_ip, client_code = hello.split("|", 2)
        print(f"[SERVER] HELLO IP={client_ip} CODE={client_code}")

        if client_code != expected_code:
            conn.sendall(b"REFUSED\n")
            conn.close()
            requests.post(
                f"{BASE_URL}:{HTTP_PORT}/disconnect",
                json={"reason": "pswd"},
                timeout=1
            )
            return None

        conn.sendall(b"OK\n")
        print("[SERVER] Client authenticated")
        return conn

    except socket.timeout:
        return None

#######################################################################
# TCP CLIENT
#######################################################################

def create_client_socket(ip, code):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((ip, TCP_PORT))
        s.settimeout(SOCKET_TIMEOUT)

        s.sendall(f"HELLO|127.0.0.1|{code}\n".encode())
        reply = s.recv(1024).decode().strip()

        if reply != "OK":
            s.close()
            requests.post(
                f"{BASE_URL}:{HTTP_PORT}/disconnect",
                json={"reason": "pswd"},
                timeout=1
            )
            return None

        print("[CLIENT] Connected & authenticated")
        return s

    except OSError as e:
        print("[CLIENT] Connection failed:", e)
        return None

#######################################################################
# NETWORK IO (IDLE SAFE)
#######################################################################

def send_data(sock, msg):
    try:
        sock.sendall((msg + "\n").encode())
        return True
    except OSError:
        return False

def receive_data(sock):
    try:
        data = sock.recv(1024)
        if data == b"":
            return "__DEAD__"     # peer really gone
        return data.decode().strip()
    except socket.timeout:
        return None              # idle client → OK
    except OSError:
        return "__DEAD__"

#######################################################################
# ACTION LOOP
#######################################################################

def action_loop(app_info, server_socket: socket.socket | None, server_conn: socket.socket | None, client_socket: socket.socket | None, vr: MobiFlightVariableRequests):
    global last_send
    now = time.time()

    if app_info["mode"] == "server":
        server_conn = try_accept(server_socket, server_conn, app_info["code"])

        if server_conn:
            if now - last_send >= SEND_INTERVAL:
                if not send_data(server_conn, "PING"):
                    print("[SERVER] Client vanished")
                    if server_conn:
                        server_conn.close()
                    server_conn = None
                last_send = now

            incoming = receive_data(server_conn) 
            if incoming == "__DEAD__":
                print("[SERVER] Client disconnected")
                if server_conn:server_conn.close()
                server_conn = None
            elif incoming:
                print("[CLIENT]", incoming)

    elif app_info["mode"] == "client":
        if not client_socket:
            return server_conn, client_socket

        if now - last_send >= SEND_INTERVAL:
            changed = vr.get_changed_dict()
            if changed:
                changed_json = json.dumps(changed)
                if not send_data(client_socket, f"DATA|{changed_json}"):
                    print("[CLIENT] Server vanished")
                    client_socket.close()
                    client_socket = None
            last_send = now

        incoming = receive_data(client_socket)
        if incoming == "__DEAD__":
            print("[CLIENT] Server disconnected")
            requests.post(
                f"{BASE_URL}:{HTTP_PORT}/disconnect",
                json={"reason": "server"},
                timeout=1
            )
            if client_socket:client_socket.close()
            client_socket = None
        elif incoming:
            print("[SERVER]", incoming)

    return server_conn, client_socket

#######################################################################
# MAIN
#######################################################################

def main():
    server_socket = None
    server_conn = None
    client_socket = None
    
    sm = SimConnectMobiFlight()
    vr = MobiFlightVariableRequests(sm)

    while True:
        try:
            app_info = get_app_info()
            if not app_info:
                time.sleep(0.2)
                continue

            if app_info["mode"] == "none":
                for s in (server_conn, client_socket, server_socket):
                    if s:
                        s.close()
                server_socket = server_conn = client_socket = None
                time.sleep(0.5)
                continue

            if app_info["mode"] == "server" and not server_socket:
                server_socket = create_server_socket()

            if app_info["mode"] == "client" and not client_socket:
                client_socket = create_client_socket(
                    app_info["targetIP"],
                    app_info["clientCode"]
                )

            server_conn, client_socket = action_loop(
                app_info,
                server_socket,
                server_conn,
                client_socket,
                vr
            )

            time.sleep(0.05)

        except KeyboardInterrupt:
            print("\n[SYSTEM] Shutdown")
            break

    for s in (server_conn, client_socket, server_socket):
        if s:
            s.close()

#######################################################################
# ENTRY
#######################################################################

if __name__ == "__main__":
    main()
