# Tesseract/Core/DataProcessing/DataProcessor.py

from .Interfaces import IUnitConverter
import logging

class DataProcessor:  
    """Procesador de datos brutos que aplica conversiones de unidades según el perfil
    del sensor.
    
    Args: 
        unit_converter (IUnitConverter): Instancia para realizar conversiones de
        unidades.
    """
    def __init__(self, unit_converter: IUnitConverter):  
        self.unit_converter = unit_converter  

    def process(self, raw_data: dict, sensor_profile: dict) -> dict:
        
        processed = {}  
        registros = sensor_profile.get("registros", {})
        
        for name, value in raw_data.items():  
            try:  
                reg_config = registros.get(name, {})
                # Usar clave CORRECTA según sensor_config.json
                if "unidad" in reg_config and "escala" in reg_config:
                    processed[name] = value * reg_config["escala"]
                # Converión de unidades SOLO si se especifica
                elif "unidad_destino" in reg_config and "unidad" in reg_config:  
                    processed[name] = self.unit_converter.convert(
                        value, 
                        reg_config["unidad"], 
                        reg_config["unidad_destino"]
                    )  
                else:  
                    processed[name] = value  
            except Exception as e:  
                logging.error(f"Error crítico en {name}: {str(e)}")  
                processed[name] = None # Evita corrupción de datos
        return processed