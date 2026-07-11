import sys
import os
from pathlib import Path

class PathManager:
    """
    Gestiona rutas de recursos de forma compatible con ejecutables empaquetados.
    """
    def __init__(self):
        self._base_path = self._determine_base_path()
        self._writable_path = self._determine_writable_path()
        
    def _determine_base_path(self) -> Path:
        """Determina la ruta base según si estamos en desarrollo o empaquetados"""
        if getattr(sys, 'frozen', False):
            # Ejecutable empaquetado
            exe_dir = Path(sys.executable).parent
            # En --onedir, los recursos están en _internal junto al exe
            internal = exe_dir / "_internal"
            if internal.exists():
                return internal
            return exe_dir
        else:
            # Entorno de desarrollo
            return Path(__file__).parent.parent.parent

    def _determine_writable_path(self) -> Path:
        local_app_data = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        writable = Path(local_app_data) / "TESSERACTO-UTR"
        writable.mkdir(parents=True, exist_ok=True)
        return writable

    def get_base_path(self) -> Path:
        """Retorna la ruta base del proyecto"""
        return self._base_path

    def get_image_path(self, filename: str) -> Path:
        """Retorna la ruta completa a una imagen"""
        return self._base_path / "images" / filename

    def get_readonly_config_path(self, filename: str) -> Path:
        return self._base_path / "Config" / filename

    def get_writable_path(self) -> Path:
        return self._writable_path

    def get_config_path(self, filename: str) -> Path:
        return self._writable_path / "Config" / filename

    def get_pendientes_usb_path(self) -> Path:
        """Retorna la ruta completa al directorio pendientes_usb"""
        usb_path = self._writable_path / "pendientes_usb"
        usb_path.mkdir(exist_ok=True)
        return usb_path

    def get_db_path(self, filename: str) -> Path:
        """Retorna la ruta completa a un archivo de base de datos"""
        return self._writable_path / filename

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

    def ensure_directories_exist(self):
        (self._writable_path / "Config").mkdir(exist_ok=True)
        self.get_pendientes_usb_path()

# Instancia singleton para uso global
path_manager = PathManager()