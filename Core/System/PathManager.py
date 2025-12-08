# Core/System/PathManager.py
import sys
import os
from pathlib import Path

class PathManager:
    """
    Gestiona rutas de recursos de forma compatible con ejecutables empaquetados.
    """
    def __init__(self):
        self._base_path = self._determine_base_path()
        
    def _determine_base_path(self) -> Path:
        """Determina la ruta base según si estamos en desarrollo o empaquetados"""
        if getattr(sys, 'frozen', False):
            # Ejecutable empaquetado
            return Path(sys.executable).parent
        else:
            # Entorno de desarrollo
            return Path(__file__).parent.parent.parent
            
    def get_base_path(self) -> Path:
        """Retorna la ruta base del proyecto"""
        return self._base_path
        
    def get_config_path(self, filename: str) -> Path:
        """Retorna la ruta completa a un archivo de configuración"""
        return self._base_path / "Config" / filename
        
    def get_image_path(self, filename: str) -> Path:
        """Retorna la ruta completa a una imagen"""
        return self._base_path / "images" / filename
        
    def get_pendientes_usb_path(self) -> Path:
        """Retorna la ruta completa al directorio pendientes_usb"""
        return self._base_path / "pendientes_usb"
        
    def get_db_path(self, filename: str) -> Path:
        """Retorna la ruta completa a un archivo de base de datos"""
        return self._base_path / filename
        
    def ensure_directories_exist(self):
        """Asegura que todos los directorios necesarios existan"""
        directories = [
            self._base_path / "Config",
            self._base_path / "images",
            self.get_pendientes_usb_path()
        ]
        
        for directory in directories:
            directory.mkdir(exist_ok=True)
            
    #Añade este método a la clase PathManager en PathManager.py
    def get_storage_path(self) -> Path:
        """Obtiene la ruta de almacenamiento, verificando primero D:\\"""
        # Verificar si existe la unidad D:
        d_drive = Path("D:/")
        if d_drive.exists():
            storage_path = d_drive / "TesseractData"
        else:
            # Usar directorio de documentos si D: no existe
            documents_path = Path.home() / "Documents"
            storage_path = documents_path / "TesseractData"
        
        # Crear directorio si no existe
        storage_path.mkdir(exist_ok=True)
        return storage_path
# Instancia singleton para uso global
path_manager = PathManager()