# TESERACTO-UTR/GUI/App.py
# VERSIÓN CORREGIDA - SIN QTextCursor problemático

import sys
import os
import logging
from PyQt5.QtWidgets import QApplication, QMessageBox
# ✅ SOLO registrar tipos si existen
from PyQt5.QtCore import QMetaType, QTimer

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from GUI.Windows.LoginWindow import LoginWindow
from Core.System.ConfigManager import ConfigManager
from Core.System.ErrorHandler import ErrorHandler
from Core.System.StateManager import StateManager
from Core.System.PathManager import path_manager

class TesseractApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        
        # ✅ Timer para procesar eventos pendientes (SOLUCIÓN REAL)
        self.event_processor = QTimer()
        self.event_processor.timeout.connect(lambda: self.processEvents())
        self.event_processor.start(100)  # Procesar eventos cada 100ms
        
        self.error_handler = ErrorHandler()
        self.config_manager = ConfigManager()
        
        # Asegurar que los directorios necesarios existan
        path_manager.ensure_directories_exist()
        
        self.init_state_manager()
        self.init_usb_storage()
        self.init_scheduler()
        
        try:
            self.sensor_profiles = ConfigManager.obtener_perfiles_sensores()
        except Exception as e:
            self.error_handler.log_error("APP_INIT", f"Error cargando perfiles: {e}")
            sys.exit(1)
        
        self.login_window = LoginWindow(self.error_handler)
        self.login_window.login_success.connect(self.on_login_success)
        self.login_window.window_closed.connect(self.quit)
        self.login_window.show()
    
    def quit(self):
        """Cierra la aplicación completamente"""
        sys.exit(0)
    
    def init_state_manager(self):
        StateManager.reset_all()
        logging.info("StateManager inicializado")
    
    def init_usb_storage(self):
        try:
            # Usar PathManager para obtener la ruta de almacenamiento
            usb_path = path_manager.get_storage_path()
            
            # Asegurar que el directorio existe
            usb_path.mkdir(exist_ok=True)
            
        except Exception as e:
            self.error_handler.log_error("APP_INIT_USB", f"Error inicializando almacenamiento USB: {e}")

    def init_scheduler(self):
        from Core.Network.FTPManager import FTPManager
        from Core.System.FileScheduler import FileScheduler
        
        # Cargar configuración FTP
        ftp_config = ConfigManager.cargar_config_ftp()
        
        # Configuración por defecto si no existe
        if not ftp_config:
            ftp_config = {
                "host": "",
                "usuario": "",
                "clave": "",
                "ruta_remota": "/",
                "hora_envio": "23:59",
                "timeout": 30,
                "secure": False,  # IMPORTANTE: False para CONAGUA
                "puerto": 21
            }
        
        # Crear FTPManager
        ftp_manager = FTPManager(ftp_config, self.error_handler)
        
        # Directorio de pendientes
        pendientes_dir = str(path_manager.get_pendientes_usb_path())
        
        # Configuración del scheduler
        sched_config = {
            "hora_envio": ftp_config.get("hora_envio", "23:59"),
            "directorio_pendientes": pendientes_dir,
            "ruta_remota": ftp_config.get("ruta_remota", "/"),
            "retencion_dias": 180,
            "enabled": True
        }
        
        # Función para nombres remotos
        def get_plantilla(nombre_archivo):
            return {"nombre_remoto": nombre_archivo}
        
        # Crear scheduler
        self.file_scheduler = FileScheduler(
            transfer_service=ftp_manager,
            config=sched_config,
            get_plantilla_fn=get_plantilla,
            error_handler=self.error_handler
        )
        
        # Iniciar si está habilitado
        if sched_config.get("enabled", True):
            try:
                self.file_scheduler.iniciar()
                logging.info("✅ Scheduler iniciado")
            except Exception as e:
                self.error_handler.log_error("SCHED-INIT", f"Error: {e}")
                logging.error(f"❌ Error iniciando scheduler: {e}")

    def on_login_success(self, user):
        from GUI.Windows.MainWindow import MainWindow
        
        self.main_window = MainWindow(
            user=user,
            error_handler=self.error_handler,
            sensor_profiles=self.sensor_profiles,
            file_scheduler=self.file_scheduler
        )
        
        self.start_system_services()
        
        if not StateManager.is_system_ready():
            QMessageBox.information(
                self.main_window,
                "Configuraciones Pendientes",
                "Algunas configuraciones (FTP/Email) están incompletas. "
                "El monitoreo está activo pero algunas funciones pueden no estar disponibles."
            )
        
        self.main_window.showMaximized()
        self.login_window.close()
    
    def start_system_services(self):
        try:
            if self.file_scheduler.config.get("enabled", True):
                if not (hasattr(self.file_scheduler, '_scheduler') 
                        and self.file_scheduler._scheduler 
                        and self.file_scheduler._scheduler.running):
                    self.file_scheduler.iniciar()
                    logging.info("FileScheduler iniciado")
        except Exception as e:
            self.error_handler.log_error("APP_START", f"Error iniciando servicios: {e}")

if __name__ == "__main__":
    app = TesseractApp(sys.argv)
    sys.exit(app.exec_())