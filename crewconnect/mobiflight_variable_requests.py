import ctypes
import logging
import struct
from time import sleep
from ctypes import sizeof
from ctypes.wintypes import FLOAT
from SimConnect.Enum import SIMCONNECT_CLIENT_DATA_PERIOD, SIMCONNECT_UNUSED
from collections import deque


class SimVariable:
    def __init__(self, id, name, float_value=None):
        self.id = id
        self.name = name
        self.float_value = None
        self.last_value = None
        self.initialized = False

    def __str__(self):
        return f"Id={self.id}, value={self.float_value}, name={self.name}"

    def has_changed(self):
        return self.last_value != self.float_value


class MobiFlightVariableRequests:

    VALUE_EPSILON = 0.0001   # tolerance to avoid float noise loops

    def __init__(self, simConnect):
        logging.info("MobiFlightVariableRequests __init__")

        self.changed_vars = deque()
        self.sm = simConnect

        self.sim_vars = {}
        self.sim_var_name_to_id = {}

        # 🔒 Prevent backend → sim infinite loops
        self.last_backend_values = {}

        self.CLIENT_DATA_AREA_LVARS    = 0
        self.CLIENT_DATA_AREA_CMD      = 1
        self.CLIENT_DATA_AREA_RESPONSE = 2

        self.FLAG_DEFAULT = 0
        self.FLAG_CHANGED = 1

        self.DATA_STRING_SIZE = 256
        self.DATA_STRING_OFFSET = 0
        self.DATA_STRING_DEFINITION_ID = 0

        self.sm.register_client_data_handler(self.client_data_callback_handler)
        self.initialize_client_data_areas()


    # ───────────────────────── Client Data Setup ─────────────────────────

    def add_to_client_data_definition(self, definition_id, offset, size):
        self.sm.dll.AddToClientDataDefinition(
            self.sm.hSimConnect,
            definition_id,
            offset,
            size,
            0,
            SIMCONNECT_UNUSED
        )

    def subscribe_to_data_change(self, data_area_id, request_id, definition_id):
        self.sm.dll.RequestClientData(
            self.sm.hSimConnect,
            data_area_id,
            request_id,
            definition_id,
            SIMCONNECT_CLIENT_DATA_PERIOD.SIMCONNECT_CLIENT_DATA_PERIOD_ON_SET,
            self.FLAG_CHANGED,
            0,
            0,
            0
        )

    def send_data(self, data_area_id, definition_id, size, dataBytes):
        self.sm.dll.SetClientData(
            self.sm.hSimConnect,
            data_area_id,
            definition_id,
            self.FLAG_DEFAULT,
            0,
            size,
            dataBytes
        )

    def send_command(self, command):
        data_byte_array = bytearray(command, "ascii")
        data_byte_array.extend(bytearray(self.DATA_STRING_SIZE - len(data_byte_array)))
        self.send_data(
            self.CLIENT_DATA_AREA_CMD,
            self.DATA_STRING_DEFINITION_ID,
            self.DATA_STRING_SIZE,
            bytes(data_byte_array)
        )


    def initialize_client_data_areas(self):
        self.sm.dll.MapClientDataNameToID(
            self.sm.hSimConnect,
            b"MobiFlight.LVars",
            self.CLIENT_DATA_AREA_LVARS
        )
        self.sm.dll.CreateClientData(
            self.sm.hSimConnect,
            self.CLIENT_DATA_AREA_LVARS,
            4096,
            self.FLAG_DEFAULT
        )

        self.sm.dll.MapClientDataNameToID(
            self.sm.hSimConnect,
            b"MobiFlight.Command",
            self.CLIENT_DATA_AREA_CMD
        )
        self.sm.dll.CreateClientData(
            self.sm.hSimConnect,
            self.CLIENT_DATA_AREA_CMD,
            self.DATA_STRING_SIZE,
            self.FLAG_DEFAULT
        )

        self.sm.dll.MapClientDataNameToID(
            self.sm.hSimConnect,
            b"MobiFlight.Response",
            self.CLIENT_DATA_AREA_RESPONSE
        )
        self.sm.dll.CreateClientData(
            self.sm.hSimConnect,
            self.CLIENT_DATA_AREA_RESPONSE,
            self.DATA_STRING_SIZE,
            self.FLAG_DEFAULT
        )

        self.add_to_client_data_definition(
            self.DATA_STRING_DEFINITION_ID,
            self.DATA_STRING_OFFSET,
            self.DATA_STRING_SIZE
        )

        self.subscribe_to_data_change(
            self.CLIENT_DATA_AREA_RESPONSE,
            self.DATA_STRING_DEFINITION_ID,
            self.DATA_STRING_DEFINITION_ID
        )


    # ───────────────────────── Callback Handler ─────────────────────────

    def client_data_callback_handler(self, client_data):

        # WASM response messages
        if client_data.dwDefineID == self.DATA_STRING_DEFINITION_ID:
            msg = ctypes.string_at(
                client_data.dwData,
                self.DATA_STRING_SIZE
            ).split(b'\x00', 1)[0].decode("ascii", errors="ignore")

            if msg:
                self.handle_response_message(msg)
            return

        # FLOAT LVars
        sim_var = self.sim_vars.get(client_data.dwDefineID)
        if not sim_var:
            return

        raw = struct.pack("I", client_data.dwData[0])
        value = round(struct.unpack('<f', raw)[0], 5)

        if not sim_var.initialized:
            sim_var.float_value = value
            sim_var.last_value = value
            sim_var.initialized = True
            return

        if value != sim_var.float_value:
            sim_var.last_value = sim_var.float_value
            sim_var.float_value = value
            self.changed_vars.append(sim_var)


    # ───────────────────────── Public API ─────────────────────────

    def get(self, variableString):
        if variableString not in self.sim_var_name_to_id:
            id = len(self.sim_vars) + 1
            self.sim_vars[id] = SimVariable(id, variableString)
            self.sim_var_name_to_id[variableString] = id

            offset = (id - 1) * sizeof(FLOAT)
            self.add_to_client_data_definition(id, offset, sizeof(FLOAT))
            self.subscribe_to_data_change(self.CLIENT_DATA_AREA_LVARS, id, id)
            self.send_command("MF.SimVars.Add." + variableString)

        sim_var = self.sim_vars[self.sim_var_name_to_id[variableString]]

        wait = 0
        while wait < 10 and sim_var.float_value is None:
            sleep(0.0005)
            wait += 1

        return sim_var.float_value if sim_var.float_value is not None else 0.0


    def clear_sim_variables(self):
        self.sim_vars.clear()
        self.sim_var_name_to_id.clear()
        self.last_backend_values.clear()
        self.send_command("MF.SimVars.Clear")


    def get_changed(self):
        changed = []
        while self.changed_vars:
            changed.append(self.changed_vars.popleft())
        return changed


    # ───────────────────────── Backend Loop Protection ─────────────────────────

    def should_accept_backend_update(self, lvar, value):
        """
        Returns False if backend is trying to send the same value again
        """
        last = self.last_backend_values.get(lvar)

        if last is not None and abs(last - value) < self.VALUE_EPSILON:
            return False

        self.last_backend_values[lvar] = value
        return True


    # ───────────────────────── WASM Responses ─────────────────────────

    def handle_response_message(self, msg):

        if msg == "MF.LVars.List.Start":
            self._lvar_list = []
            return

        if msg == "MF.LVars.List.End":
            print(f"Discovered {len(self._lvar_list)} LVars")
            return

        if hasattr(self, "_lvar_list"):
            self._lvar_list.append(msg)
