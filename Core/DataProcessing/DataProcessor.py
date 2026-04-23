# TESERACTO-UTR/Core/DataProcessing/DataProcessor.py

from .Interfaces import IUnitConverter
from Core.System.ErrorHandler import ErrorHandler  # NUEVO: Importamos el notificador
import logging

class DataProcessor:  
    """Procesador de datos brutos que aplica conversiones de unidades según el perfil
    del sensor.
    """
    # APORTACIÓN 1: Inyectamos ErrorHandler de forma opcional
    def __init__(self, unit_converter: IUnitConverter, error_handler: ErrorHandler = None):  
        self.unit_converter = unit_converter  
        self.error_handler = error_handler

    def process(self, raw_data: dict, sensor_profile: dict) -> dict:
        processed = {}  
        registros = sensor_profile.get("registros", {})
        
        for name, value in raw_data.items():  
            try:  
                reg_config = registros.get(name, {})
                if "unidad" in reg_config and "escala" in reg_config:
                    processed[name] = value * reg_config["escala"]
                elif "unidad_destino" in reg_config and "unidad" in reg_config:  
                    processed[name] = self.unit_converter.convert(
                        value, 
                        reg_config["unidad"], 
                        reg_config["unidad_destino"]
                    )  
                else:  
                    processed[name] = value  
            except Exception as e:  
                # APORTACIÓN 1: Notificar visualmente el error de conversión (Código 303)
                if self.error_handler:
                    self.error_handler.log_error("303", f"Fallo al procesar dato '{name}'", es_error_sistema=True)
                
                logging.error(f"Error detallado procesando {name}: {str(e)}")  
                processed[name] = None 
                
        return processed