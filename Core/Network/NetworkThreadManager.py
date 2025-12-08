# TESERACTO-UTR/Core/Network/NetworkThreadManager.py
# VERSIÓN CORREGIDA - SIN ERROR DE SINGLETON

import threading
import logging
from typing import Dict, Callable, Optional
from PyQt5.QtCore import QObject, pyqtSignal, Qt

class NetworkThreadManager(QObject):
    """
    Gestor de hilos EXCLUSIVO para operaciones de red (FTP, Email, SMS).
    NO se usa para procesos industriales críticos como lectura de medidores.
    """
    
    # Señales para comunicación segura con UI
    operation_started = pyqtSignal(str)      # operation_id
    operation_finished = pyqtSignal(str, object)  # operation_id, result
    operation_failed = pyqtSignal(str, str)  # operation_id, error_message
    
    # Singleton pattern CORREGIDO
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Inicializar atributos básicos ANTES de __init__
            cls._instance._network_threads = {}
            cls._instance._lock = threading.RLock()
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        # Evitar doble inicialización
        if self._initialized:
            return
            
        # Solo llamar a super().__init__() UNA VEZ
        super().__init__()
        self._initialized = True
        logging.info("✅ NetworkThreadManager iniciado (aislado para operaciones de red)")
    
    def execute_network_operation(self, operation_id: str, operation_fn: Callable, 
                                  args: tuple = (), kwargs: dict = None) -> bool:
        """
        Ejecuta una operación de red en un hilo aislado.
        NO usar para procesos industriales críticos.
        """
        with self._lock:
            # Evitar duplicados
            if operation_id in self._network_threads:
                thread = self._network_threads[operation_id]
                if thread.is_alive():
                    logging.warning(f"Operación {operation_id} ya está en ejecución")
                    return False
            
            # Preparar kwargs
            if kwargs is None:
                kwargs = {}
            
            # Crear wrapper seguro
            def thread_wrapper():
                result = None
                error = None
                
                try:
                    # Ejecutar operación
                    result = operation_fn(*args, **kwargs)
                except Exception as e:
                    error = str(e)
                    logging.error(f"❌ Error en operación {operation_id}: {error}")
                finally:
                    # Limpiar referencia
                    with self._lock:
                        if operation_id in self._network_threads:
                            del self._network_threads[operation_id]
                    
                    # Emitir resultado (se ejecutará en hilo de Qt)
                    if error is not None:
                        self.operation_failed.emit(operation_id, error)
                    else:
                        self.operation_finished.emit(operation_id, result)
            
            # Crear hilo
            thread = threading.Thread(
                target=thread_wrapper,
                name=f"Network-{operation_id}",
                daemon=True
            )
            
            self._network_threads[operation_id] = thread
            self.operation_started.emit(operation_id)
            thread.start()
            
            logging.debug(f"🔄 Operación de red iniciada: {operation_id}")
            return True
    
    def stop_operation(self, operation_id: str) -> bool:
        """Intenta detener una operación de red"""
        with self._lock:
            if operation_id in self._network_threads:
                thread = self._network_threads[operation_id]
                # No podemos forzar terminación, pero marcamos para limpieza
                del self._network_threads[operation_id]
                logging.info(f"🛑 Operación {operation_id} marcada para detención")
                return True
        return False
    
    def stop_all_operations(self):
        """Detiene todas las operaciones de red"""
        with self._lock:
            logging.info("🛑 Deteniendo todas las operaciones de red...")
            self._network_threads.clear()
    
    def is_operation_running(self, operation_id: str) -> bool:
        """Verifica si una operación está en ejecución"""
        with self._lock:
            thread = self._network_threads.get(operation_id)
            return thread is not None and thread.is_alive()

# Instancia global
network_thread_manager = NetworkThreadManager()