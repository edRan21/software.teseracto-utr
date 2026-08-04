# TESERACTO-UTR/Core/DataProcessing/DataProcessor.py

import logging
from typing import Dict, Any
from Core.DataProcessing.Services import UnitConverter
from Core.System.ErrorHandler import ErrorHandler

class DataProcessor:
    """
    Motor Matemático y de Conversión.
    Responsabilidad: Aplicar los factores de escala de la interfaz gráfica y 
    gestionar las alarmas físicas sin intervenir en la decodificación binaria (Modbus).
    """
    def __init__(self, convertidor_unidades: UnitConverter, error_handler: ErrorHandler):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.unit_converter = convertidor_unidades
        self.error_handler = error_handler

    def process(self, datos_crudos: Dict[str, Any], perfil: Dict[str, Any]) -> Dict[str, Any]:
        if not datos_crudos or not perfil:
            return self._generar_diccionario_neutro()

        procesados = self._generar_diccionario_neutro()
        registros_config = perfil.get("registros", {})

        try:
            # 1. Aplicar Escalas Matemáticas configuradas en la UI
            for reg_name, valor_crudo in datos_crudos.items():
                if valor_crudo is None:
                    continue
                    
                reg_config = registros_config.get(reg_name, {})
                escala = reg_config.get("escala", 1.0)
                
                # Si el dato es numérico, aplicamos la escala multiplicativa
                if isinstance(valor_crudo, (int, float)) and not isinstance(valor_crudo, bool):
                    procesados[reg_name] = float(valor_crudo) * float(escala)
                else:
                    # Para diccionarios de bits (como errores_sensor) o booleanos
                    procesados[reg_name] = valor_crudo

            # 2. Delegación de Diagnóstico KER (Estado del Medidor)
            estado_bruto = datos_crudos.get("codigo_error", 0)
            tipo_medidor = perfil.get("tipo_medidor", "Desconocido")
            
            if estado_bruto is not None and isinstance(estado_bruto, int):
                self.error_handler.procesar_estado_bruto_medidor(estado_bruto, tipo_medidor)

            return procesados

        except Exception as e:
            self.error_handler.log_error("303", f"Fallo al escalar y procesar datos: {str(e)}")
            return self._generar_diccionario_neutro()

    def _generar_diccionario_neutro(self) -> Dict[str, Any]:
        return {
            "flujo_instantaneo": 0.0,
            "flujo_acumulado": 0.0,
            "velocidad_flujo": 0.0,
            "direccion_flujo": 0,
            "contador_energizacion": 0,
            "codigo_error": 0,
            "errores_sensor": {}
        }