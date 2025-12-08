# TESERACTO-UTR/Core/Network/InternetManager.py

import requests
import time 
from Core.System.ErrorHandler import ErrorHandler


class InternetManager:
    """Gestiona la verificación de conectividad a internet."""
    
    TEST_URLS = [
        "http://www.google.com",
        "http://www.cloudflare.com",
        "http://www.amazon.com"
    ]
    
    def __init__(self, error_handler: ErrorHandler, timeout=5):
        """Inicializa el InternetManager."""
        self.error_handler = error_handler
        self.timeout = timeout

    def is_connected(self) -> bool:
        """Verifica conectividad con múltiples endpoints."""
        for url in self.TEST_URLS:
            try:
                response = requests.head(url, timeout=self.timeout)
                if response.status_code < 500:
                    return True
            except:
                continue
        self.error_handler.log_evento("NET-001", "Sin conexión a internet")
        return False
        
    def wait_for_connection(self, max_retries=10, base_delay=3) -> bool:
        """Espera hasta que se restaure la conexión."""
        for intento in range(max_retries):
            if self.is_connected():
                return True
            delay = base_delay * (2 ** intento)
            time.sleep(min(delay, 60))  # Máximo 60s entre reintentos
        return False