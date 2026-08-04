# TESERACTO-UTR/Core/System/ThreadManager.py

import logging
from typing import Optional, Any
from Core.Hardware.ModbusPoller import ModbusPoller
from Core.Network.InternetManager import MonitorRed

class ThreadManager:
    """
    Gestor del Ciclo de Vida (Lifecycle Manager).
    Orquesta el arranque y detención de los procesos industriales en segundo plano,
    garantizando que no existan hilos huérfanos (zombies) ni bloqueos de hardware.
    """
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        # Referencia al Productor Único
        # Referencias a Procesos en Segundo Plano
        self.modbus_poller: Optional[ModbusPoller] = None
        self.monitor_red: Optional[MonitorRed] = None 
        self.file_scheduler: Optional[Any] = None

    def registrar_poller(self, poller: ModbusPoller) -> None:
        """Registra la instancia del motor de hardware en el orquestador."""
        self.modbus_poller = poller
        self.logger.info("ModbusPoller registrado en el gestor de ciclo de vida.")
        
    def registrar_monitor_red(self, monitor: MonitorRed) -> None:
        self.monitor_red = monitor
        self.logger.info("MonitorRed registrado en el gestor de ciclo de vida.")
    
    def registrar_scheduler(self, scheduler: Any) -> None:
        """Registra la instancia del planificador de red en el orquestador"""
        self.file_scheduler = scheduler
        self.logger.info("FileScheduler registrado en el gestor de ciclo de vida.")
        

    def arrancar_hardware(self) -> None:
        """Ordena el inicio de las lecturas industriales en segundo plano."""
        if self.modbus_poller:
            self.logger.info("Orquestador iniciando el gobernador de hardware...")
            self.modbus_poller.iniciar()
        else:
            self.logger.error("Fallo de orquestación: ModbusPoller no está registrado.")
    
    def arrancar_monitor_red(self):
        """Inicia el monitoreo de conectividad."""
        if self.monitor_red:
            self.logger.info("Orquestador iniciando el monitoreo de red...")
            self.monitor_red.iniciar()
            
    def arrancar_scheduler(self):
        """Iniciar el planificador cronométrico."""
        if self.file_scheduler:
            self.logger.info("Orquestador iniciando el planificador de envíos...")
            self.file_scheduler.iniciar()
            
    def detener_hardware(self) -> None:
        """Ordena la detención controlada de las lecturas y liberación del puerto."""
        if self.modbus_poller:
            self.logger.info("Orquestador deteniendo el gobernador de hardware...")
            self.modbus_poller.detener()
    
    def manejar_desconexion_fisica(self) -> None:
        """
        Intervención de emergencia (Interrupt).
        Invocado por el USBManejador cuando detecta que el usuario arrancó el cable.
        Fuerza la liberación de los hilos de lectura para prevenir bloqueos de Windows.
        """
        self.logger.warning("Alerta de desconexión física recibida. Ejecutando paro de emergencia del ModbusPoller...")
        if self.modbus_poller:
            self.modbus_poller.detener()

    def detener_todos_los_procesos(self) -> None:
        """
        Secuencia de apagado (Teardown).
        Garantiza la limpieza absoluta de la memoria RAM y recursos de red/hardware 
        antes de que el sistema operativo destruya el proceso principal.
        """
        self.logger.info("Ejecutando limpieza global de procesos en segundo plano...")
        
        if self.modbus_poller:
            self.detener_hardware()
        # Aquí se pueden agregar futuras detenciones de otros motores si el sistema escala
        if self.monitor_red:
            self.monitor_red.detener()
        if self.file_scheduler:
            self.file_scheduler.detener()
            self.logger.info("FileScheduler detenido de forma segura por el Orquestador.")

# Instancia global (Singleton) para acceso centralizado
thread_manager = ThreadManager()