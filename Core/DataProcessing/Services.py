# Tesseract/Core/DataProcessing/Services.py - 

import logging
import os
import shutil
from datetime import datetime
from typing import Dict
from .Interfaces import IConfigProvider, IBitmaskConverter, IUnitConverter, IRecordFormatter, IFileNameGenerator

class ConfigProvider(IConfigProvider):
    def __init__(self, config_manager):
        self.config_manager = config_manager
    
    def get_config(self) -> dict:
        return self.config_manager.cargar_config_general()

class BitmaskConverter(IBitmaskConverter):
    def to_integer(self, bitmask_dict: Dict[str, bool]) -> int:
        value = 0
        for bit_str, flag_value in bitmask_dict.items():
            try:
                if flag_value:
                    bit = int(bit_str)
                    value |= (1 << bit)
            except ValueError:
                logging.warning(f"Bit inválido omitido: {bit_str}")
        return value

class UnitConverter(IUnitConverter):
    CONVERSION_STRATEGIES = {
        # Conversiones directas entre unidades de flujo
        ('m³/h', 'L/s'): lambda v: v * (1000 / 3600),
        ('m³/h', 'GPM'): lambda v: v * 4.40287,
        ('L/s', 'm³/h'): lambda v: v * (3600 / 1000),
        ('L/s', 'GPM'): lambda v: v * 15.8503,
        ('GPM', 'm³/h'): lambda v: v * 0.227125,
        ('GPM', 'L/s'): lambda v: v * 0.0630902,
        
        # Conversiones para volumen
        ('m³', 'L'): lambda v: v * 1000,
        ('m³', 'gal'): lambda v: v * 264.172,
        ('L', 'm³'): lambda v: v * 0.001,
        ('gal', 'm³'): lambda v: v * 0.00378541
    }
    
    def convert(self, value: float, from_unit: str, to_unit: str) -> float:
        if from_unit == to_unit:
            return value
            
        # Intentar conversión directa
        direct_key = (from_unit, to_unit)
        if direct_key in self.CONVERSION_STRATEGIES:
            return self.CONVERSION_STRATEGIES[direct_key](value)
            
        # Intentar conversión inversa
        reverse_key = (to_unit, from_unit)
        if reverse_key in self.CONVERSION_STRATEGIES:
            reverse_fn = self.CONVERSION_STRATEGIES[reverse_key]
            return value / reverse_fn(1) if reverse_fn(1) != 0 else value
            
        raise ValueError(f"Conversión no soportada: {from_unit}→{to_unit}")

class FileNameGenerator(IFileNameGenerator):
    def __init__(self, config_provider: IConfigProvider):
        self.config_provider = config_provider
    
    # 1. Implementación del método abstracto REQUERIDO
    def generate(self, tipo_registro: str, fecha_en_nombre: bool = True) -> str:
        """Método de compatibilidad (no usado en nuevo diseño)"""
        if fecha_en_nombre:
            return self.generate_daily_name(tipo_registro)
        return self.generate_historic_name(tipo_registro)
    
    def generate_historic_name(self, tipo_registro: str) -> str:
        """Nombre para archivo histórico acumulativo (SIN FECHA)"""
        try:
            config = self.config_provider.get_config()
            if tipo_registro == "Medidor":
                return f"{config['RFC']}_{config['NSM']}_{config['NSUT']}.txt"
            elif tipo_registro == "SistemaMedicion":
                return f"{config['RFC']}_{config['NSUT']}.txt"
        except Exception as e:
            logging.error(f"Error nombre histórico: {e}")
            return "historico_mediciones.txt"

    def generate_daily_name(self, tipo_registro: str) -> str:
        """Nombre para archivo diario de envío (CON FECHA)"""
        try:
            config = self.config_provider.get_config()
            fecha = datetime.now().strftime("%Y%m%d")
            if tipo_registro == "Medidor":
                return f"{config['RFC']}_{fecha}_{config['NSM']}_{config['NSUT']}.txt"
            elif tipo_registro == "SistemaMedicion":
                return f"{config['RFC']}_{fecha}_{config['NSUT']}.txt"
        except Exception as e:
            logging.error(f"Error nombre diario: {e}")
            return f"reporte_{datetime.now().strftime('%Y%m%d')}.txt"

class RecordFormatter(IRecordFormatter):
    def __init__(self, config_provider: IConfigProvider, bitmask_converter: IBitmaskConverter):
        self.config_provider = config_provider
        self.bitmask_converter = bitmask_converter

    def format(self, tipo_registro: str, datos_sensor: dict, perfil_sensor: dict, ker_code: str = "000") -> str:
        try:
            config = self.config_provider.get_config()
            now = datetime.now()
            fecha = now.strftime("%Y%m%d")
            hora = now.strftime("%H%M%S")
            mapa = perfil_sensor.get("output_mapping", {})
            
            # BÚSQUEDA ROBUSTA SIN LOGGING
            flujo_inst = self._buscar_valor_robusto(datos_sensor, mapa.get("flujo_instantaneo"), "flujo_instantaneo")
            flujo_acum = self._buscar_valor_robusto(datos_sensor, mapa.get("flujo_acumulado"), "flujo_acumulado")
            
            # Asegurar que ker_code tenga 3 dígitos
            ker_code_str = str(ker_code).zfill(3)
                
            if tipo_registro == "Medidor":
                return (
                    f"M|{fecha}|{hora}|{config['RFC']}|{config['NSM']}|{config['NSUE']}|"
                    f"{flujo_acum:.3f}|{config['Lat']}|{config['Long']}|{ker_code_str}"
                )
            elif tipo_registro == "SistemaMedicion":
                return (
                    f"QA|{fecha}|{hora}|{config['RFC']}|{config['NSUE']}|{flujo_inst:.3f}|"
                    f"{flujo_acum:.3f}|{config['Lat']}|{config['Long']}|{ker_code_str}"
                )
            else:
                raise ValueError("Tipo de registro inválido")
        except Exception as e:
            # Incluir el código KER incluso en errores
            ker_code_str = str(ker_code).zfill(3)
            return f"ERR|{datetime.now().strftime('%Y%m%d|%H%M%S')}|{type(e).__name__}|{str(e)}|{ker_code_str}"
    
    def _buscar_valor_robusto(self, datos_sensor: dict, clave_mapeada: str, nombre_parametro: str) -> float:
        """Búsqueda robusta de valores con múltiples estrategias"""
        try:
            # ESTRATEGIA 1: Usar clave mapeada directamente
            if clave_mapeada and clave_mapeada in datos_sensor:
                valor = datos_sensor[clave_mapeada]
                if valor is not None:
                    return float(valor)
            
            # ESTRATEGIA 2: Buscar por nombre del parámetro directamente
            if nombre_parametro in datos_sensor:
                valor = datos_sensor[nombre_parametro]
                if valor is not None:
                    return float(valor)
            
            # ESTRATEGIA 3: Buscar en claves alternativas
            claves_alternativas = {
                "flujo_instantaneo": ["instant_flow", "flow_rate", "Q", "flujo_inst"],
                "flujo_acumulado": ["total_flow", "accumulated_flow", "Vol", "flujo_acum"]
            }
            
            for clave_alt in claves_alternativas.get(nombre_parametro, []):
                if clave_alt in datos_sensor:
                    valor = datos_sensor[clave_alt]
                    if valor is not None:
                        return float(valor)
            
            # ESTRATEGIA 4: Buscar cualquier clave que contenga el nombre
            for clave, valor in datos_sensor.items():
                if nombre_parametro in clave.lower() and valor is not None:
                    return float(valor)
            
            return 0.0
            
        except (ValueError, TypeError) as e:
            return 0.0