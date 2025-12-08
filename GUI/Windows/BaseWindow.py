# GUI/Windows/BaseWindow.py

import os
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QLabel, QPushButton, 
                            QSpacerItem, QSizePolicy, QVBoxLayout)
from PyQt5.QtCore import Qt, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QColor

class FramelessWindow(QWidget):
    # Señal personalizada para cerrar la ventana
    window_closed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint)
        # Eliminamos WA_TranslucentBackground para evitar transparencias no deseadas
        
        # Variables para el arrastre de la ventana
        self.dragging = False
        self.drag_position = QPoint()
        self.is_maximized = False
        self.previous_geometry = None
        
        # Configurar estilo base solo para esta ventana
        self.setStyleSheet("""
            FramelessWindow {
                background-color: #2b2b2b;
                border-radius: 8px;
            }
        """)
    
    def setup_title_bar(self, title, show_maximize=True):
        """Configura la barra de título personalizada"""
        # Crear widget de barra de título
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(35)
        self.title_bar.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border-bottom: 1px solid #444;
            }
        """)
        
        # Layout de la barra de título
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(15, 0, 10, 0)
        title_layout.setSpacing(5)
        
        # Título de la ventana
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: bold;
                font-size: 12px;
                padding: 5px;
            }
        """)
        
        # Espaciador
        spacer = QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        # Botones de la barra de título
        minimize_btn = QPushButton("−")
        minimize_btn.setFixedSize(25, 25)
        minimize_btn.clicked.connect(self.showMinimized)
        minimize_btn.setToolTip("Minimizar")
        
        self.maximize_btn = QPushButton("□")
        self.maximize_btn.setFixedSize(25, 25)
        self.maximize_btn.clicked.connect(self.toggle_maximize)
        self.maximize_btn.setToolTip("Maximizar")
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(25, 25)
        close_btn.clicked.connect(self.close_window)
        close_btn.setToolTip("Cerrar")
        
        # Ocultar botón de maximizar si se solicita
        if not show_maximize:
            self.maximize_btn.setVisible(False)
        
        # Estilo para los botones
        button_style = """
            QPushButton {
                color: white;
                background-color: transparent;
                border: none;
                font-weight: bold;
                font-size: 14px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #444;
            }
            QPushButton:pressed {
                background-color: #555;
            }
        """
        
        # Estilo especial para el botón de cerrar
        close_style = """
            QPushButton {
                color: white;
                background-color: transparent;
                border: none;
                font-weight: bold;
                font-size: 14px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #e81123;
            }
            QPushButton:pressed {
                background-color: #f1707a;
            }
        """
        
        minimize_btn.setStyleSheet(button_style)
        self.maximize_btn.setStyleSheet(button_style)
        close_btn.setStyleSheet(close_style)
        
        # Agregar elementos a la barra de título
        title_layout.addWidget(title_label)
        title_layout.addItem(spacer)
        title_layout.addWidget(minimize_btn)
        title_layout.addWidget(self.maximize_btn)
        title_layout.addWidget(close_btn)
        
        self.title_bar.setLayout(title_layout)
        
        # Conectar eventos de ratón para arrastrar
        self.title_bar.mousePressEvent = self.title_mouse_press_event
        self.title_bar.mouseMoveEvent = self.title_mouse_move_event
        self.title_bar.mouseReleaseEvent = self.title_mouse_release_event
        
        # Conectar doble clic para maximizar
        self.title_bar.mouseDoubleClickEvent = self.title_double_click_event
        
        return self.title_bar
    
    def title_double_click_event(self, event):
        """Maneja el doble clic en la barra de título para maximizar/restaurar"""
        if event.button() == Qt.LeftButton:
            self.toggle_maximize()
        event.accept()
    
    def toggle_maximize(self):
        """Alterna entre maximizado y normal"""
        if self.is_maximized:
            self.showNormal()
            if self.previous_geometry:
                self.setGeometry(self.previous_geometry)
            self.maximize_btn.setText("□")
            self.is_maximized = False
        else:
            self.previous_geometry = self.geometry()
            self.showMaximized()
            self.maximize_btn.setText("❐")
            self.is_maximized = True
        
        # Actualizar bordes redondeados según el estado
        self.update_rounded_corners()
    
    def update_rounded_corners(self):
        """Actualizar los bordes redondeados según el estado de la ventana"""
        if self.is_maximized:
            # Sin bordes redondeados cuando está maximizada
            self.setStyleSheet("""
                FramelessWindow {
                    background-color: #2b2b2b;
                    border-radius: 0px;
                }
                """)
        else:
            # Bordes redondeados cuando no está maximizada
            self.setStyleSheet("""
                FramelessWindow {
                    background-color: #2b2b2b;
                    border-radius: 8px
                }
            """)
        
        # Forzar actualización
        self.update()
    
    def title_mouse_press_event(self, event):
        """Maneja el evento de clic del mouse en la barra de título"""
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def title_mouse_move_event(self, event):
        """Maneja el evento de movimiento del mouse en la barra de título"""
        if event.buttons() == Qt.LeftButton and self.dragging:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
    
    def title_mouse_release_event(self, event):
        """Maneja el evento de liberación del mouse en la barra de título"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            event.accept()
    
    def close_window(self):
        """Cierra la ventana y emite la señal"""
        self.window_closed.emit()
        self.close()
    
    def set_content_layout(self, layout):
        """Establece el layout del contenido principal"""
        # Crear widget contenedor principal
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Agregar barra de título si existe
        if hasattr(self, 'title_bar'):
            main_layout.addWidget(self.title_bar)
        
        # Agregar contenido principal
        main_layout.addLayout(layout)
        
        main_widget.setLayout(main_layout)
        self.setLayout(main_layout)
    
    def paintEvent(self, event):
        """Pinta el fondo de la ventana con bordes redondeados"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(43, 43, 43))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 8, 8)