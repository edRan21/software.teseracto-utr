# Core/System/ThreadManager.py

import threading
import time
import logging
from typing import Dict, List, Callable
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
# APORTACIÓN 1: Importar ErrorHandler
from Core.System.ErrorHandler import ErrorHandler

class ThreadManager(QObject):
    """Gestiona hilos de trabajo de forma segura y evita acumulación"""
    
    # Señales para comunicación con GUI
    thread_finished = pyqtSignal(str, bool)  # thread_id, success
    thread_timeout = pyqtSignal(str)         # thread_id
    
    def __init__(self):
        super().__init__()
        self._active_threads: Dict[str, threading.Thread] = {}
        self._thread_timeouts: Dict[str, float] = {}
        self._max_threads = 5
        self._default_timeout = 10.0  # segundos
        
        # Timer para limpieza de hilos
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self._cleanup_stuck_threads)
        self.cleanup_timer.start(5000)  # Cada 5 segundos

    # APORTACIÓN 1: Agregar error_handler opcional
    def start_thread(self, thread_id: str, target: Callable, args: tuple = (), timeout: float = None, error_handler: ErrorHandler = None) -> bool:
        """Inicia un hilo de forma controlada"""
        
        if len(self._active_threads) >= self._max_threads:
            msg = f"Límite de hilos alcanzado. Rechazando: {thread_id}"
            logging.warning(msg)
            # APORTACIÓN 1: Notificación visual
            if error_handler:
                error_handler.log_error("010", msg, es_error_sistema=True)
            return False
            
        self._cleanup_completed_threads()
        
        thread = threading.Thread(
            target=self._thread_wrapper,
            # Pasamos el error_handler al wrapper
            args=(thread_id, target, args, timeout or self._default_timeout, error_handler),
            name=f"Worker-{thread_id}",
            daemon=True
        )
        
        self._active_threads[thread_id] = thread
        self._thread_timeouts[thread_id] = time.time() + (timeout or self._default_timeout)
        thread.start()
        
        logging.debug(f"Hilo iniciado: {thread_id}")
        return True

    # APORTACIÓN 1: El wrapper ahora acepta y usa el error_handler
    def _thread_wrapper(self, thread_id: str, target: Callable, args: tuple, timeout: float, error_handler: ErrorHandler = None):
        """Envuelve la ejecución del hilo con manejo de errores y timeout"""
        start_time = time.time()
        success = False
        
        try:
            target(*args)
            success = True
            
        except Exception as e:
            msg = f"Colapso en proceso en segundo plano: {thread_id}"
            logging.error(f"{msg}. Detalle: {e}")
            # APORTACIÓN 1: Notificación visual del fallo del hilo
            if error_handler:
                error_handler.log_error("010", msg, es_error_sistema=True)
            success = False
            
        finally:
            self._active_threads.pop(thread_id, None)
            self._thread_timeouts.pop(thread_id, None)
            self.thread_finished.emit(thread_id, success)
            execution_time = time.time() - start_time
            logging.debug(f"Hilo {thread_id} finalizado en {execution_time:.2f}s")

    def _cleanup_completed_threads(self):
        """Limpia hilos que han terminado pero no fueron removidos"""
        completed = []
        for thread_id, thread in self._active_threads.items():
            if not thread.is_alive():
                completed.append(thread_id)
                
        for thread_id in completed:
            self._active_threads.pop(thread_id, None)
            self._thread_timeouts.pop(thread_id, None)

    def _cleanup_stuck_threads(self):
        """Termina hilos que excedieron su timeout"""
        current_time = time.time()
        stuck_threads = []
        
        for thread_id, timeout_time in self._thread_timeouts.items():
            if current_time > timeout_time:
                stuck_threads.append(thread_id)
                
        for thread_id in stuck_threads:
            logging.warning(f"Terminando hilo bloqueado: {thread_id}")
            thread = self._active_threads.get(thread_id)
            if thread and thread.is_alive():
                # En Python no podemos forzar terminación, pero podemos marcarlo
                self._active_threads.pop(thread_id, None)
                self._thread_timeouts.pop(thread_id, None)
                self.thread_timeout.emit(thread_id)

    def stop_all_threads(self):
        """Detiene todos los hilos activos (para cierre de aplicación)"""
        logging.info("Deteniendo todos los hilos de trabajo...")
        self._active_threads.clear()
        self._thread_timeouts.clear()

# Instancia global
thread_manager = ThreadManager()