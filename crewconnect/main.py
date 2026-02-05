from simconnect_mobiflight import SimConnectMobiFlight
from mobiflight_variable_requests import MobiFlightVariableRequests
import time
import requests

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


def main():
    sm = SimConnectMobiFlight()
    vr = MobiFlightVariableRequests(sm)

    print("Clearing previous sim variables…")
    vr.clear_sim_variables()

    print("Requesting LVar list…")
    vr.send_command("MF.LVars.List")
    time.sleep(0.5)

    # ───────────────────────── Subscribe to all LVars ─────────────────────────
    if not hasattr(vr, "_lvar_list"):
        print("No LVars discovered.")
        return

    for index, lvar in enumerate(vr._lvar_list):
        vr.get(f"(L:{lvar})")
        print(f"#{index} subscribed → {lvar}")

    print(f"Subscribed to {len(vr._lvar_list)} LVars")
    print("Entering main loop…\n")

    # ───────────────────────── Main Loop ─────────────────────────
    while True:
        try:
            for var in vr.get_changed():
                print(f"[SIM] {var.name} = {var.float_value}")

                # ── Send sim → backend ──
                try:
                    requests.post(
                        f"{BASE_URL}/lvar/sim",
                        json={
                            "lvar": var.name,
                            "value": var.float_value
                        },
                        timeout=SEND_TIMEOUT
                    )
                except requests.exceptions.RequestException as e:
                    print(f"[NET] POST /lvar/sim failed: {e}")

                # ── Ask backend for commands ──
                try:
                    response = requests.get(
                        f"{BASE_URL}/lvar/send",
                        timeout=SEND_TIMEOUT
                    )
                except requests.exceptions.RequestException as e:
                    print(f"[NET] GET /lvar/send failed: {e}")
                    continue

                if response.status_code != 200:
                    continue 

                # ── Parse JSON safely ──
                try:
                    data = response.json()
                except ValueError:
                    print("[JSON] Invalid JSON from backend")
                    continue

                if not isinstance(data, list):
                    continue

                # ── Apply backend → sim updates ──
                for item in data:
                    try:
                        lvar = item["lvar"]
                        value = float(item["value"])
                    except (KeyError, ValueError, TypeError):
                        continue

                    if vr.should_accept_backend_update(lvar, value):
                        print(f"[BACKEND] {lvar} → {value}")
                        vr.send_command(f"{value} (>L:{lvar})")

        except KeyboardInterrupt:
            print("\nStopping main loop.")
            break

        except Exception as e:
            print(f"[FATAL] Unexpected error: {e}")


        handle_ping()
        time.sleep(0.05)


if __name__ == "__main__":
    main()
    