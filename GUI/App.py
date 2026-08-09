# TESERACTO-UTR/GUI/App.py

import sys
import logging
import ctypes
import os

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon

# Añadir el directorio raíz al path para importaciones absolutas
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from GUI.Windows.LoginWindow import LoginWindow
from GUI.Windows.MainWindow import MainWindow

from Core.System.ConfigManager import ConfigManager
from Core.System.ErrorHandler import ErrorHandler
from Core.System.StateManager import StateManager
from Core.System.PathManager import path_manager
from Core.Hardware.USBManejador import USBManejador
from Core.Network.FTPManager import FTPManager
from Core.Network.EmailManager import EmailManager
from Core.System.FileScheduler import FileScheduler
from Core.Network.InternetManager import MonitorRed
from Core.Network.APIManager import APIManager
from Core.Network.APITelemetryWorker import APITelemetryWorker

# Orquestador Central
from Core.System.ThreadManager import thread_manager 

class TesseractApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self._configurar_entorno_windows()
        
        # 1. INICIALIZACIÓN DE SERVICIOS BASE (Capa de Sistema)
        path_manager.ensure_directories_exist()
        self.error_handler = ErrorHandler()
        
        self.monitor_red = MonitorRed(self.error_handler)
        thread_manager.registrar_monitor_red(self.monitor_red)
        thread_manager.arrancar_monitor_red()
        
        # Limpieza de estados
        StateManager.reiniciar_estados()
        
        # 2. INICIALIZACIÓN DE SERVICIOS PERIFÉRICOS Y DE RED
        self.usb_manejador = USBManejador(self.error_handler)
        self.usb_manejador.inicializar_monitoreo()
        
        self._preparar_scheduler()
        
        # 3. CARGA DE CONFIGURACIÓN CRÍTICA
        try:
            self.sensor_profiles = ConfigManager.obtener_perfiles_sensores()
        except Exception as e:
            self.error_handler.activar_ker_sistema("301", f"Error crítico al cargar perfiles: {e}")
            sys.exit(1)
        
        # 4. LANZAMIENTO DE INTERFAZ GRÁFICA (Punto de entrada visual)
        self.login_window = LoginWindow(self.error_handler)
        self.login_window.login_success.connect(self.al_iniciar_sesion)
        self.login_window.window_closed.connect(self.quit)
        self.login_window.show()

    def _configurar_entorno_windows(self):
        """Asegura el refresco de UI y el ícono en la barra de tareas de Windows."""
        self.event_processor = QTimer()
        self.event_processor.timeout.connect(self.processEvents)
        self.event_processor.start(100)
        
        if sys.platform == 'win32':
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('TesseractLabs.TESSERACTO-UTR')
            except: 
                pass

    def _preparar_scheduler(self):
        """Instancia el planificador de envíos y lo delega al Orquestador."""
        config_transferencias = ConfigManager.cargar_config_ftp()
        config_api = ConfigManager.cargar_config_api()
        
        ftp_manager = FTPManager(config_transferencias, self.error_handler)
        email_manager = EmailManager(config_transferencias, self.error_handler)
        
        # 1. Instanciación del nuevo motor API
        self.api_manager = APIManager(config_api, self.error_handler)
        self.api_worker = APITelemetryWorker(self.api_manager, self.error_handler)
        
        # 2. Delegar ciclo de vida al Orquestador
        thread_manager.registrar_api_worker(self.api_worker)
        thread_manager.arrancar_api_worker()
        
        sched_config = {
            "hora_envio": config_transferencias.get("hora_envio", "23:59"),
            "directorio_pendientes": str(path_manager.get_pendientes_usb_path()),
            "ruta_remota": config_transferencias.get("ruta_remota", "/"),
            "enabled": config_transferencias.get("enabled", True),
            "usar_ftp": config_transferencias.get("usar_ftp", True),
            "usar_email": config_transferencias.get("usar_email", False),
            "usar_api": config_api.get("enabled", False) # Extracción de bandera API
        }
        
        # Construcción del objeto inyectando el ErrorHandler
        self.file_scheduler = FileScheduler(
            transfer_service=ftp_manager,
            email_manager=email_manager,
            api_manager=self.api_manager, # Inyección de dependencia
            config=sched_config,
            get_plantilla_fn=lambda x: {}, # Función stub para resolver el contrato
            error_handler=self.error_handler
        )
        
        # INVERSIÓN DE CONTROL: Delegación absoluta al Orquestador
        thread_manager.registrar_scheduler(self.file_scheduler)
        
        if sched_config["enabled"]:
            thread_manager.arrancar_scheduler()

    def al_iniciar_sesion(self, user):
        """Transición controlada del Login a la Ventana Principal."""
        self.main_window = MainWindow(
            user=user,
            error_handler=self.error_handler,
            sensor_profiles=self.sensor_profiles,
            file_scheduler=self.file_scheduler,
            usb_manejador=self.usb_manejador
        )
        
        if not StateManager.sistema_esta_listo():
            QMessageBox.information(
                self.main_window,
                "Configuraciones Pendientes",
                "El monitoreo está activo pero algunas funciones (FTP/Email) pueden requerir configuración."
            )
        
        self.main_window.showMaximized()
        self.login_window.close()

    def quit(self):
        """Apagado determinista (Graceful Shutdown) delegado exclusivamente al Orquestador."""
        logging.info("Iniciando apagado seguro del sistema...")
        
        if hasattr(self, 'usb_manejador'):
            self.usb_manejador.detener_monitoreo()
            
        # El Orquestador central destruye todos los hilos (Modbus, Red, Scheduler) secuencialmente
        thread_manager.detener_todos_los_procesos() 
        
        super().quit()

if __name__ == "__main__":
    app = TesseractApp(sys.argv)
    app.setWindowIcon(QIcon(str(path_manager.get_image_path('TESERACTO.ico'))))
    sys.exit(app.exec_())