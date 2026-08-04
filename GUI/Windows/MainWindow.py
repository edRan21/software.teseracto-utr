# TESERACTO-UTR/GUI/Windows/MainWindow.py

from PyQt5.QtWidgets import QTabWidget, QMessageBox, QStatusBar, QVBoxLayout, QHBoxLayout, QPushButton, QWidget
from PyQt5.QtCore import QTimer

# Importaciones de la arquitectura renovada
from Core.Hardware.ModbusPoller import ModbusPoller
from Core.System.ThreadManager import thread_manager
from Core.System.ConfigManager import ConfigManager
from Core.Hardware.ModbusRTU_Manager import FabricaMedidores

# Ventanas de la interfaz
from GUI.Windows.BaseWindow import FramelessWindow
from GUI.Windows.DashboardWindow import DashboardWindow
from GUI.Windows.ConfigWindow import ConfigWindow
from GUI.Windows.ReportsWindow import ReportsWindow
from GUI.Windows.ErrorConsoleWindow import ErrorConsoleWindow
from GUI.Windows.FTPConaguaWindow import FTPConaguaWindow
from GUI.Windows.SettingsWindow import SettingsWindow
from GUI.Windows.FTPEmailConfigWindow import FTPEmailConfigWindow
from GUI.Windows.SMSConfigWindow import SMSConfigWindow

class MainWindow(FramelessWindow):
    def __init__(self, user, error_handler, sensor_profiles, file_scheduler, usb_manejador=None):
        super().__init__()
        self.user = user
        self.error_handler = error_handler
        self.sensor_profiles = sensor_profiles
        self.file_scheduler = file_scheduler
        self.usb_manejador = usb_manejador
        
        self.rol_usuario = ConfigManager.obtener_rol_usuario(self.user)

        self.setWindowTitle(f"TESSERACTO - UTR - {self.user}")
        self.resize(1000, 700)
        self.setup_title_bar(f"TESSERACTO - UTR", show_maximize=True)
        
        self.configurar_interfaz()
        self._inicializar_subsistemas()
        self.configurar_monitoreo_basico()
        
    def configurar_interfaz(self):
        """Configura todos los componentes de UI con nomenclatura limpia."""
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.setStyleSheet("""
            QTabWidget#mainTabs::pane { border: 1px solid #444; background: #2b2b2b; border-radius: 0 0 5px 5px; }
            QTabBar::tab { background: #3b3b3b; color: #ccc; padding: 8px 12px; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; border: 1px solid #444; border-bottom: none; }
            QTabBar::tab:selected { background: #2b2b2b; color: white; border-bottom: 1px solid #2b2b2b; }
            QTabBar::tab:hover:!selected { background: #4b4b4b; }
        """)
        
        # Instanciación limpia sin parámetros de hardware
        self.dashboard_window = DashboardWindow(self.error_handler)
        self.config_window = ConfigWindow(self.error_handler)
        self.reports_window = ReportsWindow(self.error_handler)
        
        self.tabs.addTab(self.dashboard_window, "Dashboard")
        
        if self.rol_usuario == "admin":
            self.tabs.addTab(self.config_window, "Configuración Hardware")
            
        self.tabs.addTab(self.reports_window, "Reportes")
        self.tabs.addTab(ErrorConsoleWindow(self.error_handler), "Errores")
        
        self.menu_bar = self.crear_barra_menu()
        
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("QStatusBar { background-color: #3b3b3b; color: white; padding: 5px; border-top: 1px solid #444; border-radius: 0 0 5px 5px; }")
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        content_layout.addWidget(self.menu_bar)
        content_layout.addWidget(self.tabs, 1)
        content_layout.addWidget(self.status_bar)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.title_bar)
        main_layout.addWidget(content_widget)
        
        self.setLayout(main_layout)
        
    def crear_barra_menu(self):
        menu_bar = QWidget()
        menu_bar.setFixedHeight(35)
        menu_bar.setStyleSheet("""
            QWidget { background-color: #3b3b3b; border-bottom: 1px solid #444; }
            QPushButton { color: white; background-color: transparent; border: none; padding: 8px 12px; border-radius: 3px; }
            QPushButton:hover { background-color: #555; }
            QPushButton:pressed { background-color: #666; }
        """)
        
        menu_layout = QHBoxLayout()
        menu_layout.setContentsMargins(10, 0, 10, 0)
        menu_layout.setSpacing(5)
        
        system_btn = QPushButton("Configuración Sistema")
        system_btn.clicked.connect(self.mostrar_configuracion_sistema)
        
        ftp_btn = QPushButton("Configuración FTP/Email")
        ftp_btn.clicked.connect(self.mostrar_configuracion_ftp)
        
        sms_btn = QPushButton("Configuración SMS")
        sms_btn.clicked.connect(self.mostrar_configuracion_sms)

        conagua_btn = QPushButton("FTP Unidad de Inspección")
        conagua_btn.clicked.connect(self.mostrar_ftp_conagua)
        
        cambiar_sesion_btn = QPushButton("🔄 Cambiar Sesión")
        cambiar_sesion_btn.setStyleSheet("background-color: #E67E22; color: white; font-weight: bold;")
        cambiar_sesion_btn.clicked.connect(self.cambiar_sesion)
        
        menu_layout.addWidget(system_btn)
        menu_layout.addWidget(ftp_btn)
        menu_layout.addWidget(sms_btn)
        menu_layout.addWidget(conagua_btn)
        menu_layout.addWidget(cambiar_sesion_btn)
        menu_layout.addStretch()
        
        menu_bar.setLayout(menu_layout)
        return menu_bar
    
    def mostrar_alerta_estado(self, mensaje):
        self.status_bar.showMessage(f"⚠️ {mensaje}", 5000)
    
    def mostrar_configuracion_sistema(self):
        if self.rol_usuario != "admin":
            QMessageBox.warning(self, "Acceso Denegado", "Solo el Técnico (Admin) puede modificar la configuración del sistema.")
            return
            
        self.settings_win = SettingsWindow(self.error_handler)
        self.settings_win.config_updated.connect(self.procesar_actualizacion_config)
        self.settings_win.show()
    
    def procesar_actualizacion_config(self):
        if hasattr(self, 'dashboard_window'):
            self.dashboard_window.actualizar_configuracion_unidades()
    
    def mostrar_configuracion_sms(self):
        if self.rol_usuario != "admin":
            QMessageBox.warning(self, "Acceso Denegado", "Solo el Técnico (Admin) puede configurar los SMS.")
            return
        self.sms_window = SMSConfigWindow(self.error_handler)
        self.sms_window.show()
        
    def cambiar_sesion(self):
        from PyQt5.QtWidgets import QInputDialog, QLineEdit, QDialog, QLabel, QComboBox
        
        pwd, ok = QInputDialog.getText(self, "Autorización de Cambio", "Ingrese Contraseña Maestra para autorizar el cambio de sesión:", QLineEdit.Password)
        if not ok or not pwd: return
        if not ConfigManager.validar_password_maestra(pwd):
            QMessageBox.critical(self, "Acceso Denegado", "Contraseña Maestra incorrecta.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Seleccionar Nueva Sesión")
        dialog.setFixedSize(300, 150)
        dialog.setStyleSheet("QDialog { background-color: #2b2b2b; color: white; } QLabel { color: white; font-weight: bold; } QComboBox { background-color: #3b3b3b; color: white; padding: 5px; border: 1px solid #555; } QPushButton { background-color: #E67E22; color: white; padding: 8px; font-weight: bold; } QPushButton:hover { background-color: #D35400; }")

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Seleccione el usuario destino:"))

        cmb_usuarios = QComboBox()
        for u in ConfigManager.obtener_lista_usuarios():
            cmb_usuarios.addItem(f"{u['usuario']} ({u['rol']})", u['usuario'])
        layout.addWidget(cmb_usuarios)

        btn_cambiar = QPushButton("Aplicar Cambio en ejecución...")
        layout.addWidget(btn_cambiar)

        def aplicar():
            nuevo_usuario = cmb_usuarios.currentData()
            self.user = nuevo_usuario
            self.rol_usuario = ConfigManager.obtener_rol_usuario(nuevo_usuario)
            self.aplicar_restricciones_rol()
            dialog.accept()
            self.mostrar_alerta_estado(f"🔄 Sesión cambiada a: {nuevo_usuario}")

        btn_cambiar.clicked.connect(aplicar)
        dialog.exec_()
          
    def aplicar_restricciones_rol(self):
        self.setWindowTitle(f"TESERACTO - UTR - {self.user}")
        if hasattr(self, 'title_bar') and hasattr(self.title_bar, 'title_label'):
            self.title_bar.title_label.setText(f"TESERACTO - UTR - {self.user}")

        idx_hardware = -1
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "Configuración Hardware":
                idx_hardware = i
                break

        if self.rol_usuario == "admin":
            if idx_hardware == -1:
                self.tabs.insertTab(1, self.config_window, "Configuración Hardware")
        else:
            if idx_hardware != -1:
                if self.tabs.currentIndex() == idx_hardware:
                    self.tabs.setCurrentIndex(0)
                self.tabs.removeTab(idx_hardware)
    
    def mostrar_ftp_conagua(self):
        try:
            self.ftp_conagua_window = FTPConaguaWindow(self.error_handler)
            self.ftp_conagua_window.window_closed.connect(lambda: self.mostrar_alerta_estado("Ventana FTP Conagua cerrada"))
            if hasattr(self.ftp_conagua_window, '_initialized') and self.ftp_conagua_window._initialized:
                self.ftp_conagua_window.show()
            else:
                self.ftp_conagua_window.deleteLater()
        except Exception as e:
            self.mostrar_alerta_estado(f"No se pudo abrir la ventana: {str(e)}")
    
    def mostrar_configuracion_ftp(self):
        self.ftp_email_window = FTPEmailConfigWindow(file_scheduler=self.file_scheduler, error_handler=self.error_handler)
        self.ftp_email_window.show()

    def _inicializar_subsistemas(self):
        """Instancia el Hardware, el ModbusPoller y los registra en el Orquestador."""
        if not self.sensor_profiles:
            self.error_handler.log_error("301", "No hay perfiles de sensor disponibles en la configuración", es_error_sistema=True)
            return
        
        active_profile = next((p for p in self.sensor_profiles if p.get("habilitado", True)), None)
        if not active_profile:
            self.error_handler.log_error("301", "Todos los perfiles de sensor están deshabilitados", es_error_sistema=True)
            return
        
        # 1. Creación del medidor físico
        self.medidor = FabricaMedidores.crear_medidor(active_profile, self.error_handler)
        
        # 2. Creación e inyección del Gobernador de Hardware (Productor)
        self.poller = ModbusPoller(self.medidor, self.error_handler)
        
        # 3. Registro en el Orquestador
        thread_manager.registrar_poller(self.poller)
        
        # Inicialización segura de ventanas
        if hasattr(self.config_window, 'load_initial_config'):
            self.config_window.load_initial_config()
        
        self.mostrar_alerta_estado("✅ Sistema operativo iniciado")

    def actualizar_medidor_global(self, nuevo_perfil):
        """Reconstruye el Productor de hardware de forma segura en tiempo real orquestado."""
        # 1. Detener procesos actuales mediante el Orquestador
        thread_manager.detener_hardware()
        
        if hasattr(self.dashboard_window, '_pausar_telemetria'):
            self.dashboard_window._pausar_telemetria()
            
        if hasattr(self, 'medidor') and self.medidor:
            self.medidor.desconectar()

        # 2. Recrear el motor
        self.medidor = FabricaMedidores.crear_medidor(nuevo_perfil, self.error_handler)
        
        # 3. Actualizar la referencia del medidor dentro del poller orquestado
        if thread_manager.modbus_poller:
            thread_manager.modbus_poller.medidor = self.medidor
            
        return self.medidor
        
    def configurar_monitoreo_basico(self):
        """Configura el reloj de supervisión de interfaz."""
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.verificar_estado_medidor)
        self.monitor_timer.start(40000)

    def verificar_estado_medidor(self):
        """
        Lectura asíncrona (Consumidor).
        Extrae datos de la RAM sin bloquear el hilo principal ni tocar el puerto COM.
        """
        try:
            if hasattr(self.dashboard_window, 'temporizador_interfaz') and not self.dashboard_window.temporizador_interfaz.isActive():
                return 
            
            poller = thread_manager.modbus_poller
            if poller:
                paquete = poller.obtener_ultimo_paquete()
                estado_conexion = paquete.get("estado_conexion", False)
                codigo_error = paquete.get("codigo_error", "000")
                
                if estado_conexion and codigo_error == "000":
                    if hasattr(self.error_handler, 'reset_ker_normal'):
                        self.error_handler.reset_ker_normal()
                    self.mostrar_alerta_estado("✅ Sistema operativo")
                else:
                    self.mostrar_alerta_estado("⚠️ Error en comunicación del medidor")
        except Exception as e:
            self.error_handler.log_error("010", f"Error crítico consultando RAM: {str(e)}")

    def closeEvent(self, event):
        """Limpieza al cerrar la ventana principal."""
        if hasattr(self, 'monitor_timer'):
            self.monitor_timer.stop()
        event.accept()