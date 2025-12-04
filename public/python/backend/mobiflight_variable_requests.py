import logging
import struct
from time import sleep, time
from ctypes import sizeof
from ctypes.wintypes import FLOAT
from SimConnect.Enum import SIMCONNECT_CLIENT_DATA_PERIOD, SIMCONNECT_UNUSED
from typing import Dict, Optional
import threading

# Minimal logging
logging.getLogger().setLevel(logging.WARNING)


class MobiFlightVariableRequests:
    """Simplified and reliable MobiFlight handler"""
    
    def __init__(self, simConnect):
        self.sm = simConnect
        self.sim_vars = {}  # var_id -> {'name': str, 'value': float, 'received': bool}
        self.sim_var_name_to_id = {}
        self.next_var_id = 1
        
        # SimConnect data areas
        self.CLIENT_DATA_AREA_LVARS = 0
        self.CLIENT_DATA_AREA_CMD = 1
        self.DATA_STRING_SIZE = 512
        
        # Thread safety
        self.lock = threading.RLock()
        self.command_semaphore = threading.Semaphore(5)  # Limit concurrent commands
        
        # Initialize SimConnect
        self._initialize_simconnect()
        
        # Register callback
        self.sm.register_client_data_handler(self.client_data_callback_handler)
    
    def _initialize_simconnect(self):
        """Initialize SimConnect - called once"""
        try:
            # LVars data area
            self.sm.dll.MapClientDataNameToID(self.sm.hSimConnect, 
                                            b"MobiFlight.LVars", 
                                            self.CLIENT_DATA_AREA_LVARS)
            self.sm.dll.CreateClientData(self.sm.hSimConnect, 
                                       self.CLIENT_DATA_AREA_LVARS, 
                                       32768,  # 32KB buffer
                                       SIMCONNECT_UNUSED)
            
            # Command area
            self.sm.dll.MapClientDataNameToID(self.sm.hSimConnect, 
                                            b"MobiFlight.Command", 
                                            self.CLIENT_DATA_AREA_CMD)
            self.sm.dll.CreateClientData(self.sm.hSimConnect, 
                                       self.CLIENT_DATA_AREA_CMD, 
                                       self.DATA_STRING_SIZE, 
                                       SIMCONNECT_UNUSED)
            
        except Exception as e:
            # Already initialized, that's OK
            pass
    
    def _send_command_safe(self, command: str):
        """Send command with rate limiting"""
        with self.command_semaphore:
            try:
                # Ensure command fits
                if len(command) > self.DATA_STRING_SIZE - 2:
                    command = command[:self.DATA_STRING_SIZE - 2]
                
                # Convert to bytes
                cmd_bytes = command.encode('ascii', errors='ignore') + b'\x00'
                if len(cmd_bytes) < self.DATA_STRING_SIZE:
                    cmd_bytes += b'\x00' * (self.DATA_STRING_SIZE - len(cmd_bytes))
                
                # Send command
                self.sm.dll.SetClientData(
                    self.sm.hSimConnect,
                    self.CLIENT_DATA_AREA_CMD,
                    0,  # definition_id
                    0,  # flags
                    0,  # reserved
                    self.DATA_STRING_SIZE,
                    cmd_bytes)
                
                # Small delay to avoid overwhelming
                sleep(0.003)
                
            except Exception as e:
                # Silently fail - we'll retry if needed
                pass
    
    def client_data_callback_handler(self, client_data):
        """Handle incoming data - SIMPLE and RELIABLE"""
        try:
            var_id = client_data.dwDefineID
            
            with self.lock:
                if var_id in self.sim_vars:
                    # Extract float value
                    data_bytes = struct.pack("I", client_data.dwData[0])
                    float_value = struct.unpack('<f', data_bytes)[0]
                    
                    # Store value
                    self.sim_vars[var_id]['value'] = float_value
                    self.sim_vars[var_id]['received'] = True
                    
        except:
            # Ignore errors in callback
            pass
    
    def get(self, variable_string: str, timeout: float = 0.25) -> Optional[float]:
        """Get variable value - SIMPLE and RELIABLE"""
        with self.lock:
            # Check if already registered
            if variable_string in self.sim_var_name_to_id:
                var_id = self.sim_var_name_to_id[variable_string]
                if var_id in self.sim_vars and self.sim_vars[var_id].get('received', False):
                    return self.sim_vars[var_id].get('value', 0.0)
            
            # Register new variable
            var_id = self.next_var_id
            self.next_var_id += 1
            
            # Store variable info
            self.sim_vars[var_id] = {
                'name': variable_string,
                'value': 0.0,
                'received': False
            }
            self.sim_var_name_to_id[variable_string] = var_id
            
            # Setup SimConnect subscription
            try:
                offset = (var_id - 1) * sizeof(FLOAT)
                
                self.sm.dll.AddToClientDataDefinition(
                    self.sm.hSimConnect,
                    var_id,
                    offset,
                    sizeof(FLOAT),
                    0.0,
                    SIMCONNECT_UNUSED)
                
                self.sm.dll.RequestClientData(
                    self.sm.hSimConnect,
                    self.CLIENT_DATA_AREA_LVARS,
                    var_id,
                    var_id,
                    SIMCONNECT_CLIENT_DATA_PERIOD.SIMCONNECT_CLIENT_DATA_PERIOD_ON_SET,
                    0,
                    0, 0, 0)
                    
            except:
                # Setup might fail if already done, that's OK
                pass
        
        # Send request for this variable
        self._send_command_safe(f"MF.SimVars.Add.{variable_string}")
        
        # Wait for response (with timeout)
        start_time = time()
        while time() - start_time < timeout:
            with self.lock:
                if self.sim_vars[var_id].get('received', False):
                    return self.sim_vars[var_id].get('value', 0.0)
            
            # Small sleep to prevent CPU spinning
            sleep(0.005)
        
        # Timeout - return 0.0
        return 0.0
    
    def clear_sim_variables(self):
        """Clear all variables"""
        with self.lock:
            self.sim_vars.clear()
            self.sim_var_name_to_id.clear()
            self.next_var_id = 1
        
        # Send clear command
        self._send_command_safe("MF.SimVars.Clear")
        sleep(0.2)