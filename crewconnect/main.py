from simconnect_mobiflight import SimConnectMobiFlight
from mobiflight_variable_requests import MobiFlightVariableRequests
import time
import requests
import socket

BASE_URL = "http://localhost:8080"
SEND_TIMEOUT = 5
PING_INTERVAL = 2.0
last_ping_check = 0.0

def handle_ping():
    global last_ping_check
    now = time.time()

    if now - last_ping_check < PING_INTERVAL:
        return

    last_ping_check = now

    try:
        r = requests.get(f"{BASE_URL}/ping", timeout=1)
        if r.status_code != 200:
            return

        token = r.json().get("token")
        if not token:
            return

        requests.post(
            f"{BASE_URL}/pong",
            json={"token": token, "code": 657},
            timeout=1
        )

    except requests.exceptions.RequestException:
        pass


def initialize_lvars(sm, vr):
    vr.clear_sim_variables()
    vr.send_command("MF.LVars.List")
    time.sleep(0.5)
    # ───────────────────────── Subscribe to all LVars ─────────────────────────
    if not hasattr(vr, "_lvar_list"):
        print("No LVars discovered.")
        return

    for index, lvar in enumerate(vr._lvar_list):
        vr.get(f"(L:{lvar})")
        print(f"#{index}")


def getAppInfo():
    try:
        r = requests.get(f"{BASE_URL}/app-info", timeout=1)
        if r.status_code != 200:
            return None
        if r.json().get("mode") == "none":
            r.json()["code"] = 'null'
        return r.json()
    except requests.exceptions.RequestException:
        return None


def wait_for_node():
    while True:
        try:
            with socket.create_connection(("localhost", 8080), timeout=1):
                print("Connected to Node.js server.")
                return
        except (ConnectionRefusedError, socket.timeout):
            print("Waiting for Node.js server to start...")
            time.sleep(1)


def createServerSocket():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', 8081))
    server_socket.listen(5)
    print("Server socket listening on port 8081")
    return server_socket

def createClientSocket(ip):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((ip, 8081))
    print("Client socket connected to server on port 8081")
    return client_socket


def sendData(socket, data):
    try:
        socket.sendall(data.encode())
        print(f"Sent data: {data}")
    except Exception as e:
        print(f"Error sending data: {e}")
        
        
def receiveData(socket):
    try:
        conn, addr = socket.accept()
        print(f"Connection accepted from {addr}")
        data = conn.recv(1024).decode()
        print(f"Received data: {data}")
        conn.close()
        return data
    except Exception as e:
        print(f"Error receiving data: {e}")
        return None

def waitForAppInfo():
    while True:
        app_info = getAppInfo()
        if app_info:
            if app_info.get("mode") == "client":
                if app_info.get("targetIP"):
                    if not app_info.get("code") == 'null':
                        return app_info
            if app_info.get("mode") == "server":   
                if not app_info.get("code") == 'null':
                    return app_info
            if app_info.get("mode") == "none":
                return "RESET"
        
        handle_ping()
        time.sleep(1)


    

def main():
    sm = SimConnectMobiFlight()
    vr = MobiFlightVariableRequests(sm)
    
    wait_for_node()

    client_socket = None
    server_socket = None

    app_info = waitForAppInfo()

    while True:
        # for var in vr.get_changed():
        #     pass
            # print(f"[SIM] {var.name} = {var.float_value}")
        app_info = waitForAppInfo()
        
        if app_info == "RESET":
            if server_socket:
                server_socket.close()
                server_socket = None
            if client_socket:
                client_socket.close()
                client_socket = None
            continue
        
        if app_info.get("mode") == "client":
            if server_socket is None:
                server_socket = createServerSocket()
        elif app_info.get("mode") == "server":
            if client_socket is None:
                client_socket = createClientSocket(app_info.get("targetIP"))
        
        
        
        handle_ping()
        time.sleep(0.05)


if __name__ == "__main__":
    main()
    