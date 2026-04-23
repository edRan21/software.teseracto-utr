# Tesseract/GUI/Windows/MainWindow.py

from PyQt5.QtWidgets import QTabWidget, QMessageBox, QStatusBar, QVBoxLayout, QHBoxLayout, QPushButton, QWidget, QApplication
from Core.Hardware.ModbusRTU_Manager import MedidorAguaBase
from Core.System.ErrorHandler import ErrorHandler
from GUI.Windows.FTPEmailConfigWindow import FTPEmailConfigWindow
from GUI.Windows.SettingsWindow import SettingsWindow
from Core.System.StateManager import StateManager
from GUI.Windows.SMSConfigWindow import SMSConfigWindow
from GUI.Windows.BaseWindow import FramelessWindow
from GUI.Windows.DashboardWindow import DashboardWindow
from GUI.Windows.ConfigWindow import ConfigWindow
from GUI.Windows.ReportsWindow import ReportsWindow
from GUI.Windows.ErrorConsoleWindow import ErrorConsoleWindow
from GUI.Windows.FTPConaguaWindow import FTPConaguaWindow
from Core.System.ConfigManager import ConfigManager
from PyQt5.QtCore import QTimer

class MainWindow(FramelessWindow):
    # 1. Actualiza el __init__
    def __init__(self, user, error_handler, sensor_profiles, file_scheduler, usb_manejador=None):
        super().__init__()
        self.user = user
        self.error_handler = error_handler
        self.sensor_profiles = sensor_profiles
        self.file_scheduler = file_scheduler
        self.usb_manejador = usb_manejador # <--- Lo guardamos
        
        # AGREGAR ESTA LÍNEA: Obtener el rol dinámicamente
        self.rol_usuario = ConfigManager.obtener_rol_usuario(self.user)

        self.setWindowTitle(f"TESSERACTO - UTR - {self.user}")
        self.resize(1000, 700)
        self.setup_title_bar(f"TESSERACTO - UTR", show_maximize=True)
        
        self.setup_ui()
        self._init_subsystems()
        self.setup_basic_monitoring()
        
    def setup_ui(self):
        """Configura todos los componentes de UI primero"""
        # Crear el widget de pestañas
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.setStyleSheet("""
            QTabWidget#mainTabs::pane {
                border: 1px solid #444;
                background: #2b2b2b;
                border-radius: 0 0 5px 5px;
            }
            QTabBar::tab {
                background: #3b3b3b;
                color: #ccc;
                padding: 8px 12px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                border: 1px solid #444;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background: #2b2b2b;
                color: white;
                border-bottom: 1px solid #2b2b2b;
            }
            QTabBar::tab:hover:!selected {
                background: #4b4b4b;
            }
        """)
        
        # Crear ventanas con placeholders (medidor=None)
        self.dashboard_window = DashboardWindow(None, self.error_handler)
        self.config_window = ConfigWindow(None, self.error_handler)
        
        self.tabs.addTab(self.dashboard_window, "Dashboard")
        
        # INYECCIÓN: Solo el admin ve la pestaña de Hardware Modbus
        if self.rol_usuario == "admin":
            self.tabs.addTab(self.config_window, "Configuración Hardware")
            
        # APORTACIÓN: Le pasamos el usb_manejador a ReportsWindow    
        self.tabs.addTab(ReportsWindow(None, self.error_handler, self.usb_manejador), "Reportes")
        self.tabs.addTab(ErrorConsoleWindow(self.error_handler), "Errores")
        
        # Crear barra de menú personalizada
        self.menu_bar = self.create_custom_menu_bar()
        
        # Configurar barra de estado
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #3b3b3b;
                color: white;
                padding: 5px;
                border-top: 1px solid #444;
                border-radius: 0 0 5px 5px;
            }
        """)
        
        # Crear widget de contenido principal
        content_widget = QWidget()
        content_widget.setObjectName("contentWidget")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Agregar barra de menú personalizada
        content_layout.addWidget(self.menu_bar)
        
        # Agregar pestañas
        content_layout.addWidget(self.tabs, 1)  # El 1 es el factor de estiramiento
        
        # Agregar barra de estado
        content_layout.addWidget(self.status_bar)
        
        # Layout principal
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.title_bar)
        main_layout.addWidget(content_widget)
        
        self.setLayout(main_layout)
        
    def create_custom_menu_bar(self):
        """Crea una barra de menú personalizada"""
        menu_bar = QWidget()
        menu_bar.setFixedHeight(35)
        menu_bar.setStyleSheet("""
            QWidget {
                background-color: #3b3b3b;
                border-bottom: 1px solid #444;
            }
            QPushButton {
                color: white;
                background-color: transparent;
                border: none;
                padding: 8px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #555;
            }
            QPushButton:pressed {
                background-color: #666;
            }
        """)
        
        menu_layout = QHBoxLayout()
        menu_layout.setContentsMargins(10, 0, 10, 0)
        menu_layout.setSpacing(5)
        
        # Botones de menú personalizados
        
        
        system_btn = QPushButton("Configuración Sistema")
        system_btn.clicked.connect(self.show_system_settings)
        
        ftp_btn = QPushButton("Configuración FTP/Email")
        ftp_btn.clicked.connect(self.show_ftp_email_config)
        
        sms_btn = QPushButton("Configuración SMS")
        sms_btn.clicked.connect(self.show_sms_config)

        # Botón para FTP CONAGUA
        conagua_btn = QPushButton("FTP Unidad de Inspección")
        conagua_btn.clicked.connect(self.show_ftp_conagua)
        
        # ANCLA (PUNTO 3): Nuevo botón de Cambio de Sesión
        cambiar_sesion_btn = QPushButton("🔄 Cambiar Sesión")
        cambiar_sesion_btn.setStyleSheet("background-color: #E67E22; color: white; font-weight: bold;")
        cambiar_sesion_btn.clicked.connect(self.cambiar_sesion)
        
        menu_layout.addWidget(system_btn)
        menu_layout.addWidget(ftp_btn)
        menu_layout.addWidget(sms_btn)
        menu_layout.addWidget(conagua_btn)
        menu_layout.addWidget(cambiar_sesion_btn) # Agregar al layout visual
        
        menu_layout.addStretch()  # Espaciador para alinear a la izquierda
        
        menu_bar.setLayout(menu_layout)
        return menu_bar
    
    def show_warning(self, message):
        self.status_bar.showMessage(f"⚠️ {message}", 5000)
    
    
    def show_system_settings(self):
        # INYECCIÓN: Validar rol antes de abrir
        if self.rol_usuario != "admin":
            QMessageBox.warning(self, "Acceso Denegado", "Solo el Técnico (Admin) puede modificar la configuración del sistema.")
            return
            
        self.settings_win = SettingsWindow(self.error_handler)
        self.settings_win.config_updated.connect(self.handle_config_update)
        self.settings_win.show()
    
    def handle_config_update(self):
        # Actualizar conversión de unidades en el dashboard
        if hasattr(self, 'dashboard_window'):
            self.dashboard_window.refresh_unit_config()
    
    def show_sms_config(self):
        """Muestra la ventana de configuración SMS"""
        # ANCLA (PUNTO 2): Validación de rol para SMS
        if self.rol_usuario != "admin":
            QMessageBox.warning(self, "Acceso Denegado", "Solo el Técnico (Admin) puede configurar los SMS.")
            return
            
        self.sms_window = SMSConfigWindow(self.error_handler)
        self.sms_window.show()
        
    # ANCLA (PUNTO 3): Lógica de cambio de sesión CORREGIDA - sin matar los procesos de una sesión ni creación de directorios temporales
    def cambiar_sesion(self):
        from PyQt5.QtWidgets import QInputDialog, QLineEdit, QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QMessageBox
        from Core.System.ConfigManager import ConfigManager
        
        # 1. Validación con Contraseña Maestra para autorizar la acción
        pwd, ok = QInputDialog.getText(
            self, 
            "Autorización de Cambio", 
            "Ingrese Contraseña Maestra para autorizar el cambio de sesión:", 
            QLineEdit.Password
        )
        
        if not ok or not pwd:
            return
            
        if not ConfigManager.validar_password_maestra(pwd):
            QMessageBox.critical(self, "Acceso Denegado", "Contraseña Maestra incorrecta.")
            return

        # 2. Diálogo de "Cambio en Caliente" (Sin cerrar el sistema)
        dialog = QDialog(self)
        dialog.setWindowTitle("Seleccionar Nueva Sesión")
        dialog.setFixedSize(300, 150)
        dialog.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: white; }
            QLabel { color: white; font-weight: bold; }
            QComboBox { background-color: #3b3b3b; color: white; padding: 5px; border: 1px solid #555; }
            QPushButton { background-color: #E67E22; color: white; padding: 8px; font-weight: bold; }
            QPushButton:hover { background-color: #D35400; }
        """)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Seleccione el usuario destino:"))

        cmb_usuarios = QComboBox()
        usuarios = ConfigManager.obtener_lista_usuarios()
        for u in usuarios:
            cmb_usuarios.addItem(f"{u['usuario']} ({u['rol']})", u['usuario'])
        layout.addWidget(cmb_usuarios)

        btn_cambiar = QPushButton("Aplicar Cambio en ejecución...")
        layout.addWidget(btn_cambiar)

        def aplicar():
            nuevo_usuario = cmb_usuarios.currentData()
            self.user = nuevo_usuario
            self.rol_usuario = ConfigManager.obtener_rol_usuario(nuevo_usuario)
            
            # Ejecutar el cambio visual SIN tocar el backend
            self.aplicar_restricciones_rol()
            dialog.accept()
            self.show_warning(f"🔄 Sesión cambiada a: {nuevo_usuario}")

        btn_cambiar.clicked.connect(aplicar)
        dialog.exec_()
          
    def aplicar_restricciones_rol(self):
        """Aplica o remueve restricciones visuales en tiempo real sin reiniciar el sistema"""
        # 1. Actualizar el título de la ventana
        self.setWindowTitle(f"TESERACTO - UTR - {self.user}")
        if hasattr(self, 'title_bar') and hasattr(self.title_bar, 'title_label'):
            self.title_bar.title_label.setText(f"TESERACTO - UTR - {self.user}")

        # 2. Buscar si la pestaña de Hardware existe actualmente
        idx_hardware = -1
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "Configuración Hardware":
                idx_hardware = i
                break

        # 3. Aplicar lógica visual según el nuevo rol
        if self.rol_usuario == "admin":
            # Si es admin y la pestaña está oculta, se la devolvemos
            if idx_hardware == -1:
                self.tabs.insertTab(1, self.config_window, "Configuración Hardware")
        else:
            # Si es operador y la pestaña está visible, se la quitamos (bloqueo)
            if idx_hardware != -1:
                # Si el técnico estaba viendo esa pestaña, lo forzamos a ver el Dashboard
                if self.tabs.currentIndex() == idx_hardware:
                    self.tabs.setCurrentIndex(0)
                self.tabs.removeTab(idx_hardware)
    
    def show_ftp_conagua(self):
        """Mostrar ventana de FTP CONAGUA con manejo mejorado"""
        try:
            self.ftp_conagua_window = FTPConaguaWindow(self.error_handler)
            
            # ✅ CORREGIDO: Usar show_warning en lugar de mostrar_estado
            self.ftp_conagua_window.window_closed.connect(
                lambda: self.show_warning("Ventana FTP Conagua cerrada")
            )
            
            # Verificar si la ventana se inicializó correctamente
            if hasattr(self.ftp_conagua_window, '_initialized') and self.ftp_conagua_window._initialized:
                self.ftp_conagua_window.show()
            else:
                # La ventana no se pudo inicializar (probablemente canceló autenticación)
                self.ftp_conagua_window.deleteLater()
                
        except Exception as e:
            print(f"Error al abrir ventana FTP Conagua: {e}")
            self.show_warning(f"No se pudo abrir la ventana: {str(e)}")
    
    def show_ftp_email_config(self):
        """Muestra la ventana de configuración FTP/Email"""
        from GUI.Windows.FTPEmailConfigWindow import FTPEmailConfigWindow
        
        # CORRECCIÓN: Usar una variable única (self.ftp_email_window) 
        # para no sobreescribir self.config_window (Hardware)
        self.ftp_email_window = FTPEmailConfigWindow(
            file_scheduler=self.file_scheduler,
            error_handler=self.error_handler
        )
        self.ftp_email_window.show()

    def _init_subsystems(self):
        if not self.sensor_profiles:
            # APORTACIÓN 1: Uso del código oficial "301" en lugar de "HW-001"
            self.error_handler.log_error("301", "No hay perfiles de sensor disponibles en la configuración", es_error_sistema=True)
            return
        
        # Encontrar el perfil activo
        active_profile = None
        for profile in self.sensor_profiles:
            if profile.get("habilitado", True):
                active_profile = profile
                break
                
        if not active_profile:
            # APORTACIÓN 1: Uso del código oficial "301" en lugar de "HW-001"
            self.error_handler.log_error("301", "Todos los perfiles de sensor están deshabilitados", es_error_sistema=True)
            return
        
        # Crear el medidor con el perfil activo
        self.medidor = MedidorAguaBase(
            perfil_sensor=active_profile,
            error_handler=self.error_handler
        )
        
        StateManager.set_state('medidor', self.medidor)
        
        # Establecer estados esenciales como completados (omitir comprobaciones por ahora)
        StateManager.set_ready('settings')
        StateManager.set_ready('ftp_email')
        StateManager.set_ready('report_templates')
        StateManager.set_ready('meter_config')
        
        # Actualizar ventanas con el medidor real
        self.dashboard_window.medidor = self.medidor
        self.config_window.medidor = self.medidor
        
        if hasattr(self.dashboard_window, 'setup_timers'):
            self.dashboard_window.setup_timers()
        
        # Cargar configuración inicial en la ventana de configuración
        if hasattr(self.config_window, 'load_initial_config'):
            self.config_window.load_initial_config()
        
        # Mostrar estado
        self.show_warning("✅ Sistema operativo iniciado")
        
    
    # Añadir estos métodos a la clase MainWindow
    def setup_basic_monitoring(self):
        """Configura la verificación básica del estado del medidor"""
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.verificar_estado_medidor)
        # Cambiar de 60000 ms (60 segundos) a 40000 ms (40 segundos)
        self.monitor_timer.start(40000)  # 40 segundos en lugar de 60 segundos

    def verificar_estado_medidor(self):
        """Verificación básica del estado del medidor"""
        try:
            if hasattr(self, 'medidor') and self.medidor:
                estado = self.medidor.leer_estado_medidor()
                if estado and estado.get('meter_status', 0) == 0:
                    # ✅ SI EL MEDIDOR ESTÁ BIEN, LIMPIAR KER
                    if hasattr(self.error_handler, 'reset_ker_normal'):
                        self.error_handler.reset_ker_normal()
                    self.show_warning("✅ Sistema operativo")
                else:
                    # ❌ SI HAY ERROR, REGISTRARLO
                    self.error_handler.log_meter_error(estado['meter_status'])
                    self.show_warning("⚠️ Error en medidor")
        except Exception as e:
            self.error_handler.log_error("007", f"Error verificando estado medidor: {str(e)}")

    # Modificar el método closeEvent para detener el timer
    def closeEvent(self, event):
        """Maneja el cierre de la aplicación"""
        # Detener el timer de monitoreo
        if hasattr(self, 'monitor_timer'):
            self.monitor_timer.stop()
            
        # Cerrar conexión con el medidor
        if hasattr(self, 'medidor'):
            self.medidor.desconectar()
            
        # Aceptar el evento de cierre
        event.accept()