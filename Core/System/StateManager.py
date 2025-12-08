# Tesseract/Core/System/StateManager.py

import threading
from typing import Any

class StateManager:
    """Gestiona el estado de preparación del sistema mediante checkpoints"""
    _states = {
        "settings": False,
        "ftp_email": False,
        "meter_config": False,
        "report_templates": False
    }
    _system_state = {}  # Almacena objetos del sistema
    _lock = threading.RLock()

    @classmethod
    def set_ready(cls, state_name: str):
        with cls._lock:
            if state_name in cls._states:
                cls._states[state_name] = True
                print(f"✅ Checkpoint [{state_name}] completado")

    @classmethod
    def is_system_ready(cls) -> bool:
        with cls._lock:
            return all(cls._states.values())
    
    @classmethod
    def is_ready(cls, state_name: str) -> bool:
        with cls._lock:
            return cls._states.get(state_name, False)
    
    @classmethod
    def reset_all(cls):
        with cls._lock:
            for key in cls._states:
                cls._states[key] = False
            print("🔄 Todos los checkpoints reiniciados")
            
    @classmethod
    def set_state(cls, key: str, value: Any):
        with cls._lock:
            cls._system_state[key] = value
            
    @classmethod
    def get_state(cls, key: str) -> Any:
        with cls._lock:
            return cls._system_state.get(key)