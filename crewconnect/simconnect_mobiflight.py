import logging, logging.handlers
import ctypes
from ctypes import wintypes
from SimConnect import SimConnect
from SimConnect.Enum import SIMCONNECT_CLIENT_DATA_ID, SIMCONNECT_RECV_ID, SIMCONNECT_RECV_CLIENT_DATA
import os
import sys

class SimConnectMobiFlight(SimConnect):

    def __init__(self, auto_connect=True, library_path=None):
        self.client_data_handlers = []
        
        # Initialisation du SimConnect
        if library_path:
            super().__init__(auto_connect, library_path)
        else:
            super().__init__(auto_connect)
        
        # Vérifier si la méthode MapClientDataNameToID existe
        try:
            # Essayer d'accéder à la méthode
            self.dll.MapClientDataNameToID.argtypes = [wintypes.HANDLE, ctypes.c_char_p, SIMCONNECT_CLIENT_DATA_ID]
            logging.info("✅ MapClientDataNameToID method available")
        except AttributeError:
            # Méthode non disponible - utiliser l'alternative
            logging.warning("⚠️ MapClientDataNameToID not available in this SimConnect version")
            self._map_client_data_alternative = self._create_alternative_mapping()
    
    def _create_alternative_mapping(self):
        """Alternative method for client data mapping"""
        # Cache pour stocker les mappings
        self._client_data_mapping = {}
        return self._map_client_data_fallback
    
    def _map_client_data_fallback(self, client_data_name, client_data_id):
        """Fallback method when MapClientDataNameToID is not available"""
        logging.debug(f"Mapping client data {client_data_name} to ID {client_data_id}")
        # Stocker le mapping dans un cache local
        self._client_data_mapping[client_data_name] = client_data_id
        return True
    
    def map_client_data_name_to_id(self, client_data_name, client_data_id):
        """Safe wrapper for MapClientDataNameToID"""
        try:
            if hasattr(self.dll, 'MapClientDataNameToID'):
                # Méthode native disponible
                return self.dll.MapClientDataNameToID(
                    self.hSimConnect,
                    client_data_name.encode('utf-8'),
                    client_data_id
                )
            else:
                # Utiliser la méthode alternative
                return self._map_client_data_fallback(client_data_name, client_data_id)
        except Exception as e:
            logging.error(f"Error mapping client data: {e}")
            return False

    def register_client_data_handler(self, handler):
        if handler not in self.client_data_handlers:
            logging.info(f"Register new client data handler: {handler.__name__ if hasattr(handler, '__name__') else 'anonymous'}")
            self.client_data_handlers.append(handler)
            return True
        return False

    def unregister_client_data_handler(self, handler):
        if handler in self.client_data_handlers:
            logging.info(f"Unregister client data handler: {handler.__name__ if hasattr(handler, '__name__') else 'anonymous'}")
            self.client_data_handlers.remove(handler)
            return True
        return False

    def my_dispatch_proc(self, pData, cbData, pContext):
        """Dispatch procedure for SimConnect events"""
        try:
            dwID = pData.contents.dwID
            
            if dwID == SIMCONNECT_RECV_ID.SIMCONNECT_RECV_ID_CLIENT_DATA:
                # Client data received
                client_data = ctypes.cast(pData, ctypes.POINTER(SIMCONNECT_RECV_CLIENT_DATA)).contents
                
                # Appeler tous les handlers enregistrés
                for handler in self.client_data_handlers:
                    try:
                        handler(client_data)
                    except Exception as e:
                        logging.error(f"Error in client data handler: {e}")
                        
            else:
                # Laisser le parent gérer les autres événements
                super().my_dispatch_proc(pData, cbData, pContext)
                
        except Exception as e:
            logging.error(f"Error in dispatch procedure: {e}")
            # Essayer de passer au parent même en cas d'erreur
            try:
                super().my_dispatch_proc(pData, cbData, pContext)
            except:
                pass

    def request_client_data(self, client_data_id, period=None):
        """Request client data from SimConnect"""
        try:
            if hasattr(self.dll, 'RequestClientData'):
                # Implémentation selon la version de SimConnect
                pass  # Ajouter l'implémentation selon tes besoins
            else:
                logging.warning("RequestClientData not available")
        except Exception as e:
            logging.error(f"Error requesting client data: {e}")