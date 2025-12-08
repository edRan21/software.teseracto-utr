# Tesseract/Core/DataProcessing/Interfaces.py 

from abc import ABC, abstractmethod
from typing import Dict, Any

class IUnitConverter(ABC):
    @abstractmethod
    def convert(self, value: float, from_unit: str, to_unit: str) -> float:
        pass

class IConfigProvider(ABC):
    @abstractmethod
    def get_config(self) -> dict:
        pass

class IBitmaskConverter(ABC):
    @abstractmethod
    def to_integer(self, bitmask_dict: Dict[str, bool]) -> int:
        pass

class IFileNameGenerator(ABC):
    @abstractmethod
    def generate(self, tipo_registro: str, fecha_en_nombre: bool = True) -> str:
        pass

class IRecordFormatter(ABC):
    @abstractmethod
    def format(self, tipo_registro: str, datos_sensor: dict, perfil_sensor: dict, ker_code: str = "000") -> str:
        pass

# NUEVA INTERFAZ PARA ALMACENAMIENTO
class IRecordStorage(ABC):
    @abstractmethod
    def store_record(self, tipo_registro: str, formatted_record: str):
        pass
