# TESERACTO-UTR/Core/Hardware/USBManejador.py

import os
import logging
import threading
import psutil  
from Core.System.ErrorHandler import ErrorHandler

class USBManejador:
    def __init__(self, error_handler: ErrorHandler, poll_interval: int = 5):
        self.error_handler = error_handler
        self._poll_interval = poll_interval
        self._lock = threading.Lock()
        self._monitoring_thread = None
        self._running = False

    def inicializar_monitoreo(self):
        self._running = True
        self._monitoring_thread = threading.Thread(
            target=self._monitor_usb_changes,
            args=(self._poll_interval,),
            daemon=True
        )
        self._monitoring_thread.start()

    def _monitor_usb_changes(self, interval):
        last_state = set()
        
        while self._running:
            current_state = self._get_usb_drives()
            new_drives = current_state - last_state
            
            if new_drives:
                for drive in new_drives:
                    # Solo registra en la bitácora visual que se detectó la USB.
                    # ❌ SE ELIMINÓ EL ROBO A LA CARPETA PENDIENTES
                    self.error_handler.log_evento(f"USB detectado: {drive}")
            
            last_state = current_state
            threading.Event().wait(interval)

    def _get_usb_drives(self):
        drives = set()
        for partition in psutil.disk_partitions():
            if 'removable' in partition.opts or 'usb' in partition.device.lower():
                drives.add(partition.mountpoint)
        return drives

    def _get_first_usb_drive(self):
        drives = self._get_usb_drives()
        return next(iter(drives), None) if drives else None

    def detener_monitoreo(self):
        self._running = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)