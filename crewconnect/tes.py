# from simconnect_mobiflight import SimConnectMobiFlight
# from mobiflight_variable_requests import MobiFlightVariableRequests
import time
import requests
import socket

###################################### VARIABLES ######################################


BASE_URL = "http://localhost:8090"
SEND_TIMEOUT = 5
PING_INTERVAL = 2.0
last_ping_check = 0.0

###################################### IHANDLE PING ######################################


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

###################################### INIT SIMCONNECT VARIABLES ######################################

def initialize_lvars(vr):
    vr.clear_sim_variables()
    vr.send_command("MF.LVars.List")
    time.sleep(0.5)

    if not hasattr(vr, "_lvar_list"):
        print("No LVars discovered.")
        return

    for index, lvar in enumerate(vr._lvar_list):
        vr.get(f"(L:{lvar})")
        print(f"#{index}")


###################################### GET APP INFOS ######################################

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

###################################### WAIT FOR NODE ######################################

def wait_for_node():
    while True:
        try:
            with socket.create_connection(("localhost", 8080), timeout=1):
                print("Connected to Node.js server.")
                return
        except (ConnectionRefusedError, socket.timeout):
            print("Waiting for Node.js server to start...")
            time.sleep(1)


###################################### SOCKET MANAGEMENT ######################################

def createServerSocket() -> socket.socket:
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', 8081))
    server_socket.listen(5)
    print("Server socket listening on port 8081")
    return server_socket

def createClientSocket(ip) -> socket.socket:
    if ip and ip != 'none':
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((ip, 8081))
        print("Client socket connected to server on port 8081")
        return client_socket

###################################### DATA NETWORKING ######################################


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

###################################### WAIT FOR APP INFO ######################################

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
    

def CheckForReset(app_info, server_socket, client_socket):
    if app_info == "RESET":
        if server_socket:
            server_socket.close()
            server_socket = None
        if client_socket:
            client_socket.close()
            client_socket = None
            

###################################### MAINLOOP ######################################

def loop(server_socket, client_socket) -> tuple[socket.socket, socket.socket]:
    app_info = waitForAppInfo()

    CheckForReset(app_info, server_socket, client_socket)

    if app_info == "RESET":
        handle_ping()
        time.sleep(0.05)
        return server_socket, client_socket
    
    if isinstance(app_info, dict):
        if app_info.get("mode") == "server" and not client_socket:
            server_socket = createServerSocket()
        elif app_info.get("mode") == "client" and not server_socket:
            client_socket = createClientSocket(app_info.get("targetIP"))
    
    if app_info and app_info != "RESET":
        actionLoop(app_info, server_socket, client_socket) 

    handle_ping()
    time.sleep(0.05)
    return server_socket, client_socket

def actionLoop(app_info,server_socket: socket.socket, client_socket: socket.socket):
    password = app_info.get("code")
    
    if app_info.get("mode") == "client":
        pass
    elif app_info.get("mode") == "server":
        receiveData(server_socket)


    # for var in vr.get_changed():
    #     pass
        # print(f"[SIM] {var.name} = {var.float_value}")

###################################### ENTRY POINT ######################################
def main():
    # sm = SimConnectMobiFlight()
    # vr = MobiFlightVariableRequests(sm)
    
    wait_for_node()
    requests.post(f"{BASE_URL}/reset", timeout=1).json()

    client_socket = None
    server_socket = None

    while True:
        client_socket, server_socket = loop(server_socket, client_socket)


if __name__ == "__main__":
    main()
    