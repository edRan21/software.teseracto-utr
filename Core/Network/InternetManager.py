# TESERACTO-UTR/Core/Network/InternetManager.py

import threading
import time
import socket
import logging
from typing import Optional
from Core.System.ErrorHandler import ErrorHandler

class MonitorRed:
    """
    Monitor de Red en segundo plano.
    Verifica la conectividad a Internet de forma asíncrona y notifica
    al ErrorHandler (KER-001) sin bloquear los hilos principales del sistema.
    """
    def __init__(self, error_handler: ErrorHandler, frecuencia_verificacion: float = 10.0):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.error_handler = error_handler
        
        # Frecuencia en segundos (ping cada 10s por defecto)
        self._frecuencia_verificacion = frecuencia_verificacion
        
        self._en_ejecucion = False
        self._hilo_trabajo: Optional[threading.Thread] = None
        
        # Asumimos desconectado hasta que el primer ping demuestre lo contrario
        self._estado_conexion = False 

    def iniciar(self) -> None:
        """Enciende el hilo de monitoreo continuo."""
        if self._en_ejecucion:
            return
            
        self._en_ejecucion = True
        self._hilo_trabajo = threading.Thread(
            target=self._ciclo_monitoreo,
            name="MonitorRed-Thread",
            daemon=True
        )
        self._hilo_trabajo.start()
        self.logger.info("MonitorRed iniciado en segundo plano.")

    def detener(self) -> None:
        """Apaga el hilo de forma segura."""
        self._en_ejecucion = False
        if self._hilo_trabajo and self._hilo_trabajo.is_alive():
            self._hilo_trabajo.join(timeout=2.0)
        self.logger.info("MonitorRed detenido.")

    def _ciclo_monitoreo(self) -> None:
        """Bucle infinito aislado."""
        while self._en_ejecucion:
            conexion_exitosa = self._verificar_conexion()
            
            # Transición: De Sin Red a Con Red
            if conexion_exitosa and not self._estado_conexion:
                self._estado_conexion = True
                self.error_handler.resolver_ker_sistema("001")
                self.logger.info("Conexión a internet detectada/restablecida.")
            
            # Transición: De Con Red a Sin Red
            elif not conexion_exitosa and self._estado_conexion:
                self._estado_conexion = False
                self.error_handler.activar_ker_sistema("001", "Pérdida de salida a servidores externos")
                self.logger.warning("Conexión a internet perdida.")
            
            time.sleep(self._frecuencia_verificacion)

    def _verificar_conexion(self) -> bool:
        """
        Intenta abrir un socket TCP al DNS de Google (8.8.8.8) en el puerto 53.
        Es el método más determinista y rápido para validar salida real a internet.
        """
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3.0)
            return True
        except OSError:
            pass
        return False
        
    def tiene_conexion(self) -> bool:
        """
        Método público O(1) para que módulos como FTPManager o FileScheduler 
        consulten si hay red sin tener que hacer pings por su cuenta.
        """
        return self._estado_conexion