# TESERACTO-UTR/Core/System/StateManager.py

import threading
from typing import Any, Dict

class StateManager:
    """
    Máquina de Estados Finita (FSM) para el control de flujo de la Interfaz Gráfica.
    Gestiona estrictamente los puntos de control (checkpoints) de configuración.
    """
    _states: Dict[str, bool] = {
        "settings": False,
        "ftp_email": False,
        "meter_config": False,
        "report_templates": False
    }
    
    # Almacén de referencias pasivas para la UI (No transaccionales)
    _system_state: Dict[str, Any] = {}
    _lock = threading.RLock()

    @classmethod
    def marcar_completado(cls, state_name: str) -> None:
        """Marca un checkpoint de configuración como completado."""
        with cls._lock:
            if state_name in cls._states:
                cls._states[state_name] = True

    @classmethod
    def sistema_esta_listo(cls) -> bool:
        """Evalúa si todos los pasos obligatorios han sido configurados."""
        with cls._lock:
            return all(cls._states.values())
    
    @classmethod
    def esta_completado(cls, state_name: str) -> bool:
        """Consulta el estado de un checkpoint específico."""
        with cls._lock:
            return cls._states.get(state_name, False)
    
    @classmethod
    def reiniciar_estados(cls) -> None:
        """Reinicia la máquina de estados a su condición inicial."""
        with cls._lock:
            for key in cls._states:
                cls._states[key] = False
            
    @classmethod
    def guardar_referencia(cls, key: str, value: Any) -> None:
        """Almacena una referencia de configuración."""
        with cls._lock:
            cls._system_state[key] = value
            
    @classmethod
    def obtener_referencia(cls, key: str) -> Any:
        """Recupera una referencia de configuración."""
        with cls._lock:
            return cls._system_state.get(key)