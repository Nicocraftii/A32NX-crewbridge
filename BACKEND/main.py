from simconnect_mobiflight import SimConnectMobiFlight
from mobiflight_variable_requests import MobiFlightVariableRequests
from time import sleep
import requests

BASE_URL = "http://localhost:8080"

sm = SimConnectMobiFlight()
vr = MobiFlightVariableRequests(sm)
vr.clear_sim_variables()
vr.send_command("MF.LVars.List")
sleep(0.5)

for lvar in vr._lvar_list:
    vr.get(f"(L:{lvar})")
    print(f"#{vr._lvar_list.index(lvar)} : Subscribed to LVar: {lvar}")

    
while True:
    for var in vr.get_changed():
        print(f"{var.name} -> {var.float_value}")
        
        payload = {
            "lvar": var.name,
            "value": var.float_value,
        }
        try:
            requests.post(f"{BASE_URL}/lvar/sim", json=payload)
        except requests.exceptions.RequestException as e:
            print(f"Error sending LVAR update: {e}")
            
        lresponse = requests.get(f"{BASE_URL}/lvar/send", params={"lvar": var.name, "value": var.float_value})
        data = lresponse.json()
        if data:
            for item in data:
                vr.send_command(f"{item['value']} (>L:{item['lvar']})")
        
    sleep(0.05)
