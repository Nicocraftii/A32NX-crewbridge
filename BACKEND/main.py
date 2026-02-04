from simconnect_mobiflight import SimConnectMobiFlight
from mobiflight_variable_requests import MobiFlightVariableRequests
from time import sleep

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
    sleep(0.05)
