# TESERACTO-UTR/Core/DataProcessing/DataProcessor.py

import logging
from typing import Dict, Any
from Core.System.ErrorHandler import ErrorHandler

class DataProcessor:
    """
    Motor Matemático y de Conversión.
    Responsabilidad: Aplicar los factores de escala de la interfaz gráfica a las magnitudes 
    y preservar la integridad estructural de los registros discretos/estado.
    """
    def __init__(self, error_handler: ErrorHandler):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.error_handler = error_handler

    def process(self, datos_crudos: Dict[str, Any], perfil: Dict[str, Any]) -> Dict[str, Any]:
        if not datos_crudos or not perfil:
            return self._generar_diccionario_neutro()

        procesados = self._generar_diccionario_neutro()
        registros_config = perfil.get("registros", {})

        # PROTECCIÓN ESTRUCTURAL: Campos que JAMÁS deben ser alterados aritméticamente
        campos_estado = {"codigo_error", "direccion_flujo", "contador_energizacion", "unidad_flujo"}

        try:
            # 1. Aplicar Escalas Matemáticas o Preservar Estado
            for reg_name, valor_crudo in datos_crudos.items():
                if valor_crudo is None:
                    continue
                    
                reg_config = registros_config.get(reg_name, {})
                escala = reg_config.get("escala", 1.0)
                no_escalar = reg_config.get("no_escalar", False)
                
                # Evaluación de tipo numérico puro
                if isinstance(valor_crudo, (int, float)) and not isinstance(valor_crudo, bool):
                    
                    if reg_name in campos_estado or no_escalar:
                        # PRESERVACIÓN: Se mantiene el tipo de dato original decodificado (int)
                        procesados[reg_name] = valor_crudo
                    else:
                        # ESCALADO: Se aplica magnitud de UI y se asume float
                        procesados[reg_name] = float(valor_crudo) * float(escala)
                else:
                    # Estructuras complejas (diccionarios de bits, booleanos)
                    procesados[reg_name] = valor_crudo

            # 2. Delegación de Diagnóstico KER (Estado del Medidor)
            # Ahora está garantizado que estado_bruto es un entero puro
            estado_bruto = procesados.get("codigo_error", 0)
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