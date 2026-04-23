# TESERACTO-UTR/GUI/App.py
# VERSIÓN CORREGIDA - SIN QTextCursor problemático y CIERRE SEGURO

import sys
import os
import logging
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QMetaType, QTimer

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from GUI.Windows.LoginWindow import LoginWindow
from Core.System.ConfigManager import ConfigManager
from Core.System.ErrorHandler import ErrorHandler
from Core.System.StateManager import StateManager
from Core.System.PathManager import path_manager
# 1. Agregar esta importación en la parte superior de App.py
from Core.Hardware.USBManejador import USBManejador

class TesseractApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.event_processor = QTimer()
        self.event_processor.timeout.connect(lambda: self.processEvents())
        self.event_processor.start(100)  
        
        self.error_handler = ErrorHandler()
        self.config_manager = ConfigManager()
        
        path_manager.ensure_directories_exist()
        
        # APORTACIÓN: Encender el vigilante de la USB a nivel global
        self.usb_manejador = USBManejador(self.error_handler)
        self.usb_manejador.inicializar_monitoreo()
        
        self.init_state_manager()
        self.init_usb_storage()
        self.init_scheduler()
        
        try:
            self.sensor_profiles = ConfigManager.obtener_perfiles_sensores()
        except Exception as e:
            self.error_handler.log_error("301", f"Error cargando perfiles de sensores al inicio: {e}", es_error_sistema=True)
            sys.exit(1)
        
        self.login_window = LoginWindow(self.error_handler)
        self.login_window.login_success.connect(self.on_login_success)
        self.login_window.window_closed.connect(self.quit)
        self.login_window.show()

# 3. Reemplaza el método quit (para detener la USB al cerrar)
    def quit(self):
        """Cierra la aplicación completamente de forma segura"""
        logging.info("Iniciando secuencia de apagado seguro...")
        try:
            if hasattr(self, 'file_scheduler') and self.file_scheduler:
                self.file_scheduler.detener()
            
            # APORTACIÓN: Apagar el vigilante USB
            if hasattr(self, 'usb_manejador') and self.usb_manejador:
                self.usb_manejador.detener_monitoreo()
                
            from Core.System.ThreadManager import thread_manager
            thread_manager.stop_all_threads()
        except Exception as e:
            logging.error(f"Error durante el apagado de hilos: {e}")
        sys.exit(0)
    
    def init_state_manager(self):
        StateManager.reset_all()
        logging.info("StateManager inicializado")
    
    def init_usb_storage(self):
        try:
            usb_path = path_manager.get_storage_path()
            usb_path.mkdir(exist_ok=True)
        except Exception as e:
            # APORTACIÓN 1: Uso de código KER oficial "010"
            self.error_handler.log_error("010", f"Error inicializando almacenamiento local: {e}", es_error_sistema=True)

    def init_scheduler(self):
        from Core.Network.FTPManager import FTPManager
        from Core.System.FileScheduler import FileScheduler
        from Core.System.ConfigManager import ConfigManager  
        
        ftp_config = ConfigManager.cargar_config_ftp()
        email_config = ConfigManager.cargar_config_email()  
        
        if not ftp_config:
            ftp_config = {
                "host": "", "usuario": "", "clave": "",
                "ruta_remota": "/", "hora_envio": "23:59",
                "timeout": 60, "secure": False, "puerto": 21
            }
        
        ftp_manager = FTPManager(ftp_config, self.error_handler)
        pendientes_dir = str(path_manager.get_pendientes_usb_path())
        
        sched_config = {
            "hora_envio": ftp_config.get("hora_envio", "23:59"),
            "directorio_pendientes": pendientes_dir,
            "ruta_remota": ftp_config.get("ruta_remota", "/"),
            "retencion_dias": 180,
            "enabled": True
        }
        
        def get_plantilla(nombre_archivo):
            return {"nombre_remoto": nombre_archivo}
        
        self.file_scheduler = FileScheduler(
            transfer_service=ftp_manager,
            config=sched_config,
            get_plantilla_fn=get_plantilla,
            error_handler=self.error_handler
        )
        
        if hasattr(self.file_scheduler, 'email_config'):
            self.file_scheduler.email_config = email_config
        
        if sched_config.get("enabled", True):
            try:
                self.file_scheduler.iniciar()
                logging.info("✅ Scheduler iniciado con configuración FTP/Email")
            except Exception as e:
                # APORTACIÓN 1: Uso de código KER oficial "010"
                self.error_handler.log_error("010", f"Fallo crítico al arrancar envíos automáticos: {e}", es_error_sistema=True)

    # 4. Reemplaza el método on_login_success (para pasar el manejador a la MainWindow)
    def on_login_success(self, user):
        from GUI.Windows.MainWindow import MainWindow
        self.main_window = MainWindow(
            user=user,
            error_handler=self.error_handler,
            sensor_profiles=self.sensor_profiles,
            file_scheduler=self.file_scheduler,
            usb_manejador=self.usb_manejador  # <--- APORTACIÓN: Pasamos el manejador
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
                logging.info("FileScheduler verificado e iniciado")
        except Exception as e:
            # APORTACIÓN 1: Uso de código KER oficial "010"
            self.error_handler.log_error("010", f"Error arrancando servicios secundarios: {e}", es_error_sistema=True)

if __name__ == "__main__":
    app = TesseractApp(sys.argv)
    sys.exit(app.exec_())