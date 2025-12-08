# Tesseract/Core/Network/IFileTransfer.py

from abc import ABC, abstractmethod  

class IFileTransfer(ABC):  
    @abstractmethod  
    def enviar_archivo(self, local_path: str, remote_path: str) -> bool:  
        pass
        
    @abstractmethod
    def verificar_conexion(self) -> bool:
        pass