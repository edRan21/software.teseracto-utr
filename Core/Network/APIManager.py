# TESERACTO-UTR/Core/Network/APIManager.py

import os
import logging
import requests
from typing import Tuple
from datetime import datetime

class APIManager:
    """
    Gestor del protocolo HTTP/HTTPS para la Web API.
    Responsabilidad Única: Transmitir telemetría (JSON) y reportes de auditoría (TXT)
    hacia los endpoints del servidor web mediante métodos POST.
    """
    def __init__(self, config: dict, error_handler):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.error_handler = error_handler
        self._actualizar_credenciales(config)

    def actualizar_configuracion(self, config: dict) -> None:
        """Sincronización en caliente desde la UI."""
        self._actualizar_credenciales(config)

    def _actualizar_credenciales(self, config: dict) -> None:
        # Extraemos la URL base (eliminando slash final si existe) y el Token
        self.api_url = config.get("api_url", "").rstrip('/')
        self.api_key = config.get("api_key", "")

    def enviar_telemetria(self, payload: dict) -> bool:
        """
        Canal 1: Transmite el estado actual del sistema (Telemetría Periódica).
        Endpoint destino: /telemetry
        """
        if not self.api_url or not self.api_key:
            return False

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            endpoint = f"{self.api_url}/telemetry"
            respuesta = requests.post(endpoint, json=payload, headers=headers, timeout=10.0)
            
            if respuesta.status_code in (200, 201):
                return True
            else:
                self.error_handler.activar_ker_sistema("010", f"API HTTP {respuesta.status_code}: Rechazo en telemetría")
                return False
                
        except requests.exceptions.RequestException as e:
            self.error_handler.activar_ker_sistema("010", f"Error de conexión API: {str(e)}")
            return False

    def enviar_archivo(self, ruta_local: str, nombre_adjunto: str) -> Tuple[bool, str]:
        """
        Canales 2 y 3: Transmisión de Reportes (Diarios e Históricos).
        Implementa la firma exacta requerida por FileScheduler.
        Endpoint destino: /reports
        """
        if not self.api_url or not self.api_key:
            return False, "Credenciales API incompletas o no configuradas."

        if not os.path.exists(ruta_local):
            return False, "El archivo a transmitir no existe en el disco duro."

        try:
            # Lectura en memoria del archivo generado por ReportsWindow
            with open(ruta_local, 'r', encoding='utf-8') as archivo:
                contenido_txt = archivo.read()

            # NO HAY Inferencia robusta del tipo de reporte basándose en el prefijo o nomenclatura PORQUE SOLO SON DOS TIPOS DE REPORTE QUE EL SISTEMA GENERA,
            # sino empieza "M" el contenido del reporte entonces es el otro tipo de reporte.
            tipo_reporte = "Medidor" if nombre_adjunto.startswith("M") else "SistemaMedicion"

            payload = {
                "filename": nombre_adjunto,
                "report_type": tipo_reporte,
                "content": contenido_txt,
                "transmitted_at": datetime.now().isoformat()
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            endpoint = f"{self.api_url}/reports"
            # Se otorga un timeout mayor (15s) al tratarse de archivos completos
            respuesta = requests.post(endpoint, json=payload, headers=headers, timeout=15.0)

            if respuesta.status_code in (200, 201):
                return True, f"{respuesta.status_code} OK - Reporte transmitido a API"
            else:
                mensaje_error = f"HTTP {respuesta.status_code} - Rechazo del servidor"
                self.error_handler.activar_ker_sistema("010", mensaje_error)
                return False, mensaje_error

        except requests.exceptions.RequestException as e:
            error_msg = f"Excepción de red (API): {str(e)}"
            self.error_handler.activar_ker_sistema("010", error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Fallo I/O al preparar payload API: {str(e)}"
            self.error_handler.activar_ker_sistema("305", error_msg)
            return False, error_msg