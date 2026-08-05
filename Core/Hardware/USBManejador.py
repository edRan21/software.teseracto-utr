# TESERACTO-UTR/Core/Hardware/USBManejador.py

import threading
import time
import logging
import serial.tools.list_ports
from typing import Optional

from Core.System.ErrorHandler import ErrorHandler
from Core.System.ConfigManager import ConfigManager
from Core.System.ThreadManager import thread_manager

class USBManejador:
    """
    Vigía de Puertos Físicos.
    Monitorea constantemente la conexión física a nivel de sistema operativo (Windows).
    Si el dispositivo es desconectado abruptamente, notifica al Orquestador para 
    evitar colisiones (Kernel Panics) y detener las lecturas.
    """
    def __init__(self, error_handler: ErrorHandler):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.error_handler = error_handler
        
        # Frecuencia de escaneo pasivo (cada 2 segundos)
        self._frecuencia_escaneo = 2.0 
        self._en_ejecucion = False
        self._hilo_trabajo: Optional[threading.Thread] = None
        
        self._estado_conexion = False

    def inicializar_monitoreo(self) -> None:
        """Punto de entrada llamado desde App.py"""
        if self._en_ejecucion: return
        self._en_ejecucion = True
        self._hilo_trabajo = threading.Thread(
            target=self._ciclo_vigilancia,
            name="USBManejador-Thread",
            daemon=True
        )
        self._hilo_trabajo.start()
        self.logger.info("Vigía de hardware (USBManejador) iniciado.")

    def detener_monitoreo(self) -> None:
        """Punto de salida seguro llamado desde App.py"""
        self._en_ejecucion = False
        if self._hilo_trabajo and self._hilo_trabajo.is_alive():
            self._hilo_trabajo.join(timeout=2.0)
        self.logger.info("Vigía de hardware detenido.")

    def _ciclo_vigilancia(self) -> None:
        """Bucle infinito que audita los dispositivos USB/COM activos."""
        while self._en_ejecucion:
            try:
                # 1. Obtener el puerto que el sistema está utilizando actualmente desde el Orquestador
                puerto_objetivo = None
                if thread_manager.modbus_poller and thread_manager.modbus_poller.medidor:
                    perfil = thread_manager.modbus_poller.medidor.perfil
                    if perfil:
                        puerto_objetivo = perfil.get("puerto_serie")
                
                if puerto_objetivo:
                    # 2. Escanear el registro de Windows
                    puertos_activos = [p.device for p in serial.tools.list_ports.comports()]
                    
                    if puerto_objetivo in puertos_activos:
                        if not self._estado_conexion:
                            self._estado_conexion = True
                            self.error_handler.resolver_ker_sistema("005")
                            self.logger.info(f"Puerto hardware detectado: {puerto_objetivo}")
                    else:
                        if self._estado_conexion:
                            self._estado_conexion = False
                            self.error_handler.activar_ker_sistema("005", f"Extracción física del cable en {puerto_objetivo}")
                            self.logger.error(f"Pérdida crítica de hardware en {puerto_objetivo}.")
                            
                            # 3. Disparar el protocolo de emergencia al Orquestador
                            thread_manager.manejar_desconexion_fisica()
            except Exception as e:
                self.error_handler.activar_ker_sistema("010", f"Fallo interno en el vigía de hardware: {e}")
            
            time.sleep(self._frecuencia_escaneo)