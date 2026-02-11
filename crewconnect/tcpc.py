import time
import socket
import requests
import json
from simconnect_mobiflight import SimConnectMobiFlight
from mobiflight_variable_requests import MobiFlightVariableRequests

################################ CONFIG ################################

BASE_URL = "http://localhost"
HTTP_PORT = 8090
TCP_PORT = 8081

PING_INTERVAL = 2.0
SEND_INTERVAL = 1.0
SOCKET_TIMEOUT = 0.2

last_ping = 0.0
last_send = 0.0

#######################################################################
# HEARTBEAT (NODE)
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

        hello = conn.recv(2048).decode().strip()
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
        reply = s.recv(2048).decode().strip()

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
# PROTOCOL HELPERS (LOCK-STEP)
#######################################################################

def send_packet(sock, packet):
    try:
        sock.sendall((json.dumps(packet) + "\n").encode())
        return True
    except OSError:
        return False

def receive_packet(sock, buffer):
    try:
        data = sock.recv(4096)
        if data == b"":
            return "__DEAD__", buffer
        buffer += data.decode()
    except socket.timeout:
        return None, buffer
    except OSError:
        return "__DEAD__", buffer

    if "\n" not in buffer:
        return None, buffer

    line, buffer = buffer.split("\n", 1)
    return json.loads(line), buffer

#######################################################################
# ACTION LOOP (ACK-BASED)
#######################################################################

def action_loop(app_info, server_socket, server_conn, client_socket, vr,
                recv_buffer, waiting_for_ack):

    global last_send
    now = time.time()

    ################################################ SERVER MODE ################################################
    if app_info["mode"] == "server":
        server_conn = try_accept(server_socket, server_conn, app_info["code"])

        if server_conn:
            msg, recv_buffer = receive_packet(server_conn, recv_buffer)

            if msg == "__DEAD__":
                print("[SERVER] Client disconnected")
                server_conn.close()
                return None, None, "", False

            if isinstance(msg, dict):
                if msg["type"] == "DATA":
                    print("[CLIENT DATA]", msg["payload"])
                    send_packet(server_conn, {"type": "ACK"})

                elif msg["type"] == "ACK":
                    waiting_for_ack = False

                elif msg["type"] == "PING":
                    send_packet(server_conn, {"type": "ACK"})

            if not waiting_for_ack and now - last_send >= SEND_INTERVAL:
                send_packet(server_conn, {
                    "type": "PING"
                })
                last_send = now

    ################################################ CLIENT MODE ################################################
    elif app_info["mode"] == "client":
        if not client_socket:
            return server_conn, client_socket, recv_buffer, waiting_for_ack

        msg, recv_buffer = receive_packet(client_socket, recv_buffer)

        if msg == "__DEAD__":
            print("[CLIENT] Server disconnected")
            requests.post(
                f"{BASE_URL}:{HTTP_PORT}/disconnect",
                json={"reason": "server"},
                timeout=1
            )
            client_socket.close()
            return server_conn, None, "", False

        if isinstance(msg, dict):
            if msg["type"] == "DATA":
                print("[SERVER DATA]", msg["payload"])
                send_packet(client_socket, {"type": "ACK"})

            elif msg["type"] == "ACK":
                waiting_for_ack = False

            elif msg["type"] == "PING":
                send_packet(client_socket, {"type": "ACK"})

        if not waiting_for_ack and now - last_send >= SEND_INTERVAL:
            changed = vr.get_changed_dict()
            if changed:
                if send_packet(client_socket, {
                    "type": "DATA",
                    "payload": changed
                }):
                    waiting_for_ack = True
            last_send = now

    return server_conn, client_socket, recv_buffer, waiting_for_ack

#######################################################################
# MAIN
#######################################################################

def main():
    server_socket = None
    server_conn = None
    client_socket = None

    recv_buffer = ""
    waiting_for_ack = False

    sm = SimConnectMobiFlight()
    vr = MobiFlightVariableRequests(sm)

    vr.clear_sim_variables()
    vr.send_command("MF.LVars.List")
    time.sleep(0.5)

    for lvar in vr._lvar_list:
        vr.get(f"(L:{lvar})")

    print(f"Subscribed to {len(vr._lvar_list)} LVars")

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
                recv_buffer = ""
                waiting_for_ack = False
                time.sleep(0.5)
                continue

            if app_info["mode"] == "server" and not server_socket:
                server_socket = create_server_socket()

            if app_info["mode"] == "client" and not client_socket:
                client_socket = create_client_socket(
                    app_info["targetIP"],
                    app_info["clientCode"]
                )

            server_conn, client_socket, recv_buffer, waiting_for_ack = action_loop(
                app_info,
                server_socket,
                server_conn,
                client_socket,
                vr,
                recv_buffer,
                waiting_for_ack
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
