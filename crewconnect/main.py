from simconnect_mobiflight import SimConnectMobiFlight
from mobiflight_variable_requests import MobiFlightVariableRequests
import time
import requests
import socket

###################################### VARIABLES ######################################

BASE_URL = "http://localhost"
PORT = 8080          # Node HTTP port
EXCHANGE_PORT = 8081 # TCP exchange port

SEND_TIMEOUT = 5
PING_INTERVAL = 2.0
last_ping_check = 0.0

###################################### HEARTBEAT ######################################

def handle_ping():
    global last_ping_check
    now = time.time()

    if now - last_ping_check < PING_INTERVAL:
        return
    last_ping_check = now

    try:
        r = requests.get(f"{BASE_URL}:{PORT}/ping", timeout=1)
        if r.status_code != 200:
            return

        token = r.json().get("token")
        if not token:
            return

        requests.post(
            f"{BASE_URL}:{PORT}/pong",
            json={"token": token, "code": 657},
            timeout=1
        )
    except requests.exceptions.RequestException:
        pass

###################################### APP INFO ######################################

def getAppInfo():
    handle_ping()
    try:
        r = requests.get(f"{BASE_URL}:{PORT}/app-info", timeout=1)
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("mode") == "none":
            data["code"] = "null"
        return data
    except requests.exceptions.RequestException:
        return None

###################################### WAIT FOR NODE ######################################

def wait_for_node():
    while True:
        try:
            with socket.create_connection(("localhost", PORT), timeout=1):
                print("Connected to Node.js server.")
                return
        except (ConnectionRefusedError, socket.timeout):
            print("Waiting for Node.js server to start...")
            time.sleep(1)

###################################### SOCKET MANAGEMENT ######################################

def createServerSocket():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", EXCHANGE_PORT))
    s.listen(1)
    s.settimeout(0.01)
    print(f"Server listening on port {EXCHANGE_PORT}")
    return s, None

def createClientSocket(ip):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.01)
    s.connect((ip, EXCHANGE_PORT))
    print(f"Client connected to {ip}:{EXCHANGE_PORT}")
    return s

###################################### NETWORK HELPERS ######################################

def try_accept(server_socket, server_conn):
    if server_conn:
        return server_conn
    try:
        conn, addr = server_socket.accept()
        conn.settimeout(0.01)
        print(f"Client connected from {addr}")
        return conn
    except socket.timeout:
        return None

def sendData(sock, data):
    if not sock:
        return
    try:
        sock.sendall((data + "\n").encode())
    except (socket.timeout, OSError):
        pass

def receiveData(sock):
    if not sock:
        return None
    try:
        data = sock.recv(1024).decode().strip()
        return data if data else None
    except (socket.timeout, OSError):
        return None

###################################### WAIT FOR APP INFO ######################################

def waitForAppInfo():
    while True:
        app_info = getAppInfo()
        if app_info:
            if app_info.get("mode") in ("client", "server"):
                if app_info.get("code") != "null":
                    return app_info
            if app_info.get("mode") == "none":
                return "RESET"

        handle_ping()
        time.sleep(0.2)

###################################### MAIN LOOP ######################################

def loop(server_socket, server_conn, client_socket, vr):
    app_info = waitForAppInfo()

    if app_info == "RESET":
        if server_conn:
            server_conn.close()
        if server_socket:
            server_socket.close()
        if client_socket:
            client_socket.close()
        return None, None, None

    if app_info["mode"] == "server" and not server_socket:
        server_socket, server_conn = createServerSocket()

    if app_info["mode"] == "client" and not client_socket:
        client_socket = createClientSocket(app_info["targetIP"])

    actionLoop(app_info, server_socket, server_conn, client_socket, vr)

    handle_ping()
    time.sleep(0.05)
    return server_socket, server_conn, client_socket

###################################### ACTION LOOP ######################################

def actionLoop(app_info, server_socket, server_conn, client_socket, vr):

    if app_info["mode"] == "server":
        server_conn = try_accept(server_socket, server_conn)

        if server_conn:
            for var in vr.get_changed():
                sendData(server_conn, f"{var.name}={var.float_value}")

            incoming = receiveData(server_conn)
            if incoming:
                print(f"[CLIENT] {incoming}")

    elif app_info["mode"] == "client":
        incoming = receiveData(client_socket)
        if incoming:
            print(f"[SERVER] {incoming}")

###################################### ENTRY POINT ######################################

def main():
    sm = SimConnectMobiFlight()
    vr = MobiFlightVariableRequests(sm)

    wait_for_node()
    requests.post(f"{BASE_URL}:{PORT}/reset", timeout=1)

    server_socket = None
    server_conn = None
    client_socket = None

    while True:
        try:
            server_socket, server_conn, client_socket = loop(
                server_socket, server_conn, client_socket, vr
            )
        except KeyboardInterrupt:
            print("Shutting down...")
            break

    for s in (server_conn, server_socket, client_socket):
        if s:
            s.close()

if __name__ == "__main__":
    main()
