# TESERACTO-UTR/GUI/Windows/LoginWindow.py

import os
from PyQt5.QtWidgets import QLineEdit, QPushButton, QVBoxLayout, QLabel, QHBoxLayout, QSpacerItem, QSizePolicy, QWidget
from PyQt5.QtCore import pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtCore import Qt
from Core.System.ConfigManager import ConfigManager
from Core.System.PathManager import path_manager  # ✅ Importar PathManager
from GUI.Windows.BaseWindow import FramelessWindow

class LoginWindow(FramelessWindow):
    login_success = pyqtSignal(str)  # Señal con nombre de usuario

    def __init__(self, error_handler):
        super().__init__()
        self.error_handler = error_handler
        
        # Configurar ventana
        self.setWindowTitle("Login - TESERACTO UTR")
        self.resize(800, 600) # Tamaño base, pero se maximizará
        self.setMinimumSize(500, 350) # Tamaño mínimo
        
        # Configurar barra de título (CON botón de maximizar)
        self.setup_title_bar("Login - TESERACTO UTR", show_maximize=True)
        
        # Cargar imagen de fondo
        self.background_image = self.load_background_image()
        
        # Widgets
        self.txt_user = QLineEdit(placeholderText="Usuario")
        self.txt_pass = QLineEdit(placeholderText="Contraseña", echoMode=QLineEdit.Password)
        self.btn_login = QPushButton("Iniciar Sesión")
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
        app_title = QLabel("TESERACTO UTR")
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
            self.error_handler.log_evento("LOGIN_FAIL", f"Intento fallido para usuario: {user}")