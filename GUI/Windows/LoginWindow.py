# TESERACTO-UTR/GUI/Windows/LoginWindow.py

import os
from PyQt5.QtWidgets import QLineEdit, QPushButton, QVBoxLayout, QLabel, QHBoxLayout, QSpacerItem, QSizePolicy, QWidget
from PyQt5.QtCore import pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QInputDialog, QMessageBox, QComboBox, QFormLayout)
from Core.System.ConfigManager import ConfigManager
from Core.System.PathManager import path_manager  # ✅ Importar PathManager
from GUI.Windows.BaseWindow import FramelessWindow

class GestionUsuariosDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestión de Usuarios (Maestro)")
        self.setFixedSize(500, 400)
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: white; }
            QLabel { color: white; font-weight: bold; }
            QLineEdit, QComboBox { background-color: #3b3b3b; color: white; padding: 5px; border: 1px solid #555; }
            QPushButton { background-color: #2E86C1; color: white; padding: 5px; font-weight: bold; }
            QPushButton:hover { background-color: #2874A6; }
            QTableWidget { background-color: #3b3b3b; color: white; gridline-color: #555; }
            QHeaderView::section { background-color: #1e1e1e; color: white; padding: 5px; }
        """)
        self.setup_ui()
        self.cargar_usuarios()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Tabla de usuarios
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(2)
        self.tabla.setHorizontalHeaderLabels(["Usuario", "Rol"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tabla)
        
        # Formulario para nuevo usuario
        form_layout = QFormLayout()
        self.txt_nuevo_user = QLineEdit()
        self.txt_nuevo_pass = QLineEdit()
        self.txt_nuevo_pass.setEchoMode(QLineEdit.Password)
        self.cmb_rol = QComboBox()
        self.cmb_rol.addItems(["operador", "admin"])
        
        form_layout.addRow("Nuevo Usuario:", self.txt_nuevo_user)
        form_layout.addRow("Contraseña:", self.txt_nuevo_pass)
        form_layout.addRow("Rol:", self.cmb_rol)
        layout.addLayout(form_layout)
        
        # Botones de acción
        btn_layout = QHBoxLayout()
        self.btn_agregar = QPushButton("Agregar / Actualizar")
        self.btn_eliminar = QPushButton("Eliminar Seleccionado")
        self.btn_eliminar.setStyleSheet("background-color: #E74C3C;")
        
        self.btn_agregar.clicked.connect(self.agregar_usuario)
        self.btn_eliminar.clicked.connect(self.eliminar_usuario)
        
        btn_layout.addWidget(self.btn_agregar)
        btn_layout.addWidget(self.btn_eliminar)
        layout.addLayout(btn_layout)

    def cargar_usuarios(self):
        usuarios = ConfigManager.obtener_lista_usuarios()
        self.tabla.setRowCount(len(usuarios))
        for row, data in enumerate(usuarios):
            self.tabla.setItem(row, 0, QTableWidgetItem(data["usuario"]))
            self.tabla.setItem(row, 1, QTableWidgetItem(data["rol"]))

    def agregar_usuario(self):
        user = self.txt_nuevo_user.text().strip()
        pwd = self.txt_nuevo_pass.text()
        rol = self.cmb_rol.currentText()
        
        if not user or not pwd:
            QMessageBox.warning(self, "Error", "Usuario y contraseña son obligatorios.")
            return
            
        ConfigManager.crear_usuario(user, pwd, rol)
        self.txt_nuevo_user.clear()
        self.txt_nuevo_pass.clear()
        self.cargar_usuarios()
        QMessageBox.information(self, "Éxito", f"Usuario '{user}' guardado correctamente.")

    def eliminar_usuario(self):
        row = self.tabla.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Error", "Seleccione un usuario de la tabla.")
            return
            
        user = self.tabla.item(row, 0).text()
        if ConfigManager.eliminar_usuario(user):
            self.cargar_usuarios()
            QMessageBox.information(self, "Éxito", f"Usuario '{user}' eliminado.")
        else:
            QMessageBox.critical(self, "Error", f"No se puede eliminar al usuario base '{user}'.")

class LoginWindow(FramelessWindow):
    login_success = pyqtSignal(str)  # Señal con nombre de usuario

    def __init__(self, error_handler):
        super().__init__()
        self.error_handler = error_handler
        
        # Configurar ventana
        self.setWindowTitle("Login - TESSERACTO UTR")
        self.resize(800, 600) # Tamaño base, pero se maximizará
        self.setMinimumSize(500, 350) # Tamaño mínimo
        
        # Configurar barra de título (CON botón de maximizar)
        self.setup_title_bar("Login - TESSERACTO UTR", show_maximize=True)
        
        # Cargar imagen de fondo
        self.background_image = self.load_background_image()
        
        # Widgets
        self.txt_user = QLineEdit(placeholderText="Usuario")
        self.txt_pass = QLineEdit(placeholderText="Contraseña", echoMode=QLineEdit.Password)
        self.btn_login = QPushButton("Iniciar Sesión")
        self.btn_gestion = QPushButton("⚙️ Gestión de Usuarios") # NUEVO BOTÓN
        self.btn_gestion.setObjectName("btn_gestion")  
        self.lbl_status = QLabel()
        
        # Hacer los campos de texto y botón más grandes
        self.txt_user.setMinimumHeight(40)
        self.txt_pass.setMinimumHeight(40)
        self.btn_login.setMinimumHeight(45)
        
        # Crear widget de contenido principal
        self.content_widget = QWidget()
        self.content_widget.setObjectName("contentWidget")
        
        # Configurar layout de contenido
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(40, 30, 40, 30)
        
        # Espaciador superior
        content_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        # Layout horizontal para centrar el formulario
        form_container = QHBoxLayout()
        form_container.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        # Layout del formulario
        form_layout = QVBoxLayout()
        
        # Título de la aplicación
        app_title = QLabel("TESSERACTO UTR")
        app_title.setAlignment(Qt.AlignCenter)
        app_title.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: bold;
                font-size: 24px;
                background-color: rgba(0, 0, 0, 120);
                padding: 10px;
                border-radius: 5px;
                margin-bottom: 20px;
            }
        """)
        form_layout.addWidget(app_title)
        
        form_layout.addWidget(QLabel("Usuario:"))
        form_layout.addWidget(self.txt_user)
        form_layout.addWidget(QLabel("Contraseña:"))
        form_layout.addWidget(self.txt_pass)
        form_layout.addWidget(self.btn_login)
        form_layout.addWidget(self.btn_gestion) # AGREGAR AL LAYOUT
        form_layout.addWidget(self.lbl_status)
        
        # Establecer espaciado
        form_layout.setSpacing(15)
        
        form_container.addLayout(form_layout)
        form_container.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        content_layout.addLayout(form_container)
        
        # Espaciador inferior
        content_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        # Estilo para mejorar visibilidad sobre la imagen de fondo
        self.apply_styles()
        
        # Layout principal
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.title_bar)
        main_layout.addWidget(self.content_widget)
        
        self.setLayout(main_layout)
        
        # Conexiones
        self.btn_login.clicked.connect(self.authenticate)
        self.txt_pass.returnPressed.connect(self.authenticate)
        self.btn_gestion.clicked.connect(self.abrir_gestion_usuarios) # CONEXIÓN NUEVA
        
        # Mostrar la ventana maximizada
        QTimer.singleShot(100, self.showMaximized)

    def load_background_image(self):
        """Carga la imagen de fondo desde la carpeta images"""
        try:
            # Usar PathManager para obtener ruta absoluta a la imagen
            image_path = path_manager.get_image_path("LOGO_V2.png")
            
            if image_path.exists():
                return QPixmap(str(image_path))
            else:
                self.error_handler.log_error(
                    "LOGIN_WINDOW", 
                    f"Imagen de fondo no encontrada: {image_path}"
                )
                return None
        except Exception as e:
            self.error_handler.log_error("LOGIN_WINDOW", f"Error cargando imagen: {str(e)}")
            return None

    def paintEvent(self, event):
        """Método para dibujar la imagen de fondo manteniendo la relación de aspecto"""
        # Primero pintar el fondo de la ventana base
        super().paintEvent(event)
        
        # Luego pintar la imagen de fondo
        if self.background_image:
            painter = QPainter(self)
            # Escalar imagen manteniendo la relación de aspecto
            scaled_pixmap = self.background_image.scaled(
                self.size(), 
                aspectRatioMode=1,  # KeepAspectRatio - mantener relación de aspecto
                transformMode=1     # SmoothTransformation
            )
            
            # Centrar la imagen en la ventana
            x = int((self.width() - scaled_pixmap.width()) / 2)
            y = int((self.height() - scaled_pixmap.height()) / 2)
            
            painter.drawPixmap(x, y, scaled_pixmap)

    def apply_styles(self):
        """Aplica estilos para mejorar la visibilidad de los elementos sobre la imagen"""
        style = """
            #contentWidget {
                background-color: transparent;
            }
            QLineEdit {
                background-color: rgba(255, 255, 255, 220);
                border: 2px solid #555;
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
                color: #333;
            }
            QPushButton {
                background-color: rgba(70, 130, 180, 220);
                color: white;
                font-weight: bold;
                border: 2px solid #555;
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(100, 160, 210, 220);
            }
            QLabel#status {
                background-color: rgba(0, 0, 0, 180);
                color: white;
                padding: 8px;
                border-radius: 5px;
                font-size: 12px;
            }
            QLabel {
                color: white;
                font-weight: bold;
                background-color: rgba(0, 0, 0, 120);
                padding: 3px;
                border-radius: 3px;
                font-size: 14px;
            }
            QPushButton#btn_gestion {
                background-color: rgba(100, 100, 100, 180);
            }
        """
        self.content_widget.setStyleSheet(style)
        self.lbl_status.setObjectName("status")

    def authenticate(self):
        user = self.txt_user.text().strip()
        password = self.txt_pass.text()
        
        if ConfigManager.validar_credenciales(user, password):
            self.login_success.emit(user)
        else:
            self.lbl_status.setText("❌ Credenciales inválidas")
            # APORTACIÓN 2: Corrección de orden de parámetros y código de evento
            self.error_handler.log_evento(f"Intento fallido de inicio de sesión para usuario: {user}", "401")
    
    def abrir_gestion_usuarios(self):
        """Solicita contraseña maestra y abre el panel de gestión si es correcta"""
        pwd, ok = QInputDialog.getText(
            self, 
            "Autenticación Maestra", 
            "Ingrese la Contraseña Maestra del Sistema:", 
            QLineEdit.Password
        )
        
        if ok and pwd:
            if ConfigManager.validar_password_maestra(pwd):
                dialog = GestionUsuariosDialog(self)
                dialog.exec_()
            else:
                self.error_handler.log_evento("Intento de acceso maestro fallido", "401")
                QMessageBox.critical(self, "Acceso Denegado", "Contraseña maestra incorrecta.")