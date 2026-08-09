# TESERACTO-UTR/Core/Network/APITelemetryWorker.py

import threading
import time
import logging
from datetime import datetime
from typing import Optional

from Core.System.ConfigManager import ConfigManager
from Core.System.ThreadManager import thread_manager
from Core.System.ErrorHandler import ErrorHandler
from Core.Network.APIManager import APIManager

class APITelemetryWorker:
    """
    Hilo Consumidor Periódico (Canal 1).
    Extrae la telemetría en tiempo real de la RAM y la transmite a la API
    en intervalos regulares sin interferir con la adquisición de datos de Modbus.
    """
    def __init__(self, api_manager: APIManager, error_handler: ErrorHandler):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.api_manager = api_manager
        self.error_handler = error_handler

        self._en_ejecucion = False
        self._hilo_trabajo: Optional[threading.Thread] = None

        self._actualizar_parametros()

    def _actualizar_parametros(self):
        config = ConfigManager.cargar_config_api()
        self.habilitado = config.get("enabled", False)
        # Convertimos los minutos configurados por el usuario a segundos
        self.intervalo_segundos = int(config.get("intervalo_minutos", 15)) * 60

    def actualizar_configuracion(self, nueva_config: dict):
        """Sincronización en caliente detonada desde WebAPIConfigWindow."""
        self.api_manager.actualizar_configuracion(nueva_config)
        self.habilitado = nueva_config.get("enabled", False)
        self.intervalo_segundos = int(nueva_config.get("intervalo_minutos", 15)) * 60

    def iniciar(self):
        if self._en_ejecucion: return
        self._en_ejecucion = True
        self._hilo_trabajo = threading.Thread(
            target=self._ciclo_transmision,
            name="APITelemetry-Thread",
            daemon=True
        )
        self._hilo_trabajo.start()
        self.logger.info("Motor APITelemetryWorker iniciado.")

    def detener(self):
        self._en_ejecucion = False
        if self._hilo_trabajo and self._hilo_trabajo.is_alive():
            self._hilo_trabajo.join(timeout=3.0)
        self.logger.info("Motor APITelemetryWorker detenido.")

    def _ciclo_transmision(self):
        """Bucle infinito con interrupción temprana (Graceful Shutdown)."""
        while self._en_ejecucion:
            # Fragmentación del sleep: 
            # Si el intervalo es de 20 min, no hacemos un sleep(1200) que congelaría el hilo.
            # Hacemos 1200 sleeps de 1 segundo, permitiendo detener el hilo casi instantáneamente.
            for _ in range(self.intervalo_segundos):
                if not self._en_ejecucion:
                    break
                time.sleep(1)

            if not self._en_ejecucion or not self.habilitado:
                continue

            # Máquina de estados: Solo ensambla y envía si hay red comprobada
            if thread_manager.monitor_red and thread_manager.monitor_red.tiene_conexion():
                self._ensamblar_y_enviar()

    def _ensamblar_y_enviar(self):
        try:
            config_general = ConfigManager.cargar_config_general()

            # Extracción atómica de la memoria RAM (O(1)) a través del orquestador
            poller = thread_manager.modbus_poller
            if poller:
                paquete = poller.obtener_ultimo_paquete()
                datos = paquete.get("datos_crudos", {})
            else:
                datos = {}

            # Construcción estricta del Payload exigida por la nueva funcionalidad
            payload = {
                "rfc": config_general.get("RFC", ""),
                "nsm": config_general.get("NSM", ""),
                "nsue": config_general.get("NSUE", ""),
                "nsut": config_general.get("NSUT", ""),
                "timestamp": datetime.now().isoformat(),
                "flow_instant": float(datos.get("flujo_instantaneo", 0.0) or 0.0),
                "flow_accumulated": float(datos.get("flujo_acumulado", 0.0) or 0.0),
                "flow_velocity": float(datos.get("velocidad_flujo", 0.0) or 0.0),
                "flow_direction": int(datos.get("direccion_flujo", 0) or 0),
                "ker_code": self.error_handler.obtener_ker_para_reporte(),
                "latitude": float(config_general.get("Lat", 0.0) or 0.0),
                "longitude": float(config_general.get("Long", 0.0) or 0.0),
                "unit_measurement": config_general.get("unidad_visualizacion", "m³/h")
            }

            self.api_manager.enviar_telemetria(payload)
            
        except Exception as e:
            self.error_handler.activar_ker_sistema("010", f"Error ensamblando payload API: {e}")