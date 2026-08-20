# GUI/Windows/BaseWindow.py

import os
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QLabel, 
                            QSpacerItem, QSizePolicy, QVBoxLayout)
from PyQt5.QtCore import Qt, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QColor

class FramelessWindow(QWidget):
    window_closed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint)
        
        self.dragging = False
        self.drag_position = QPoint()
        self.is_maximized = True
        self.previous_geometry = None
        
        self.setStyleSheet("""
            FramelessWindow {
                background-color: #2b2b2b;
                border-radius: 8px;
            }
            QScrollArea { border: none; background-color: transparent; }
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 16px; 
                margin: 0px 0px 0px 0px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #5a5a5a; 
                min-height: 30px;
                border-radius: 8px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover { background-color: #2E86C1; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
            
            QScrollBar:horizontal {
                background-color: #2b2b2b;
                height: 16px;
                margin: 0px 0px 0px 0px;
                border: none;
            }
            QScrollBar::handle:horizontal {
                background-color: #5a5a5a;
                min-width: 30px;
                border-radius: 8px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover { background-color: #2E86C1; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
        """)
    
    # Se mantiene el parámetro 'show_maximize' en la firma para compatibilidad,
    # pero internamente se ignora para garantizar la barra completamente limpia.
    def setup_title_bar(self, title, show_maximize=True):
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
        
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(15, 0, 10, 0)
        title_layout.setSpacing(5)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: white; font-weight: bold; font-size: 12px; padding: 5px;")
        
        spacer = QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        title_layout.addWidget(title_label)
        title_layout.addItem(spacer)
        
        # Eliminación estricta de la botonería visual
        self.title_bar.setLayout(title_layout)
        
        self.title_bar.mousePressEvent = self.title_mouse_press_event
        self.title_bar.mouseMoveEvent = self.title_mouse_move_event
        self.title_bar.mouseReleaseEvent = self.title_mouse_release_event
        
        # El doble clic sigue activo para la funcionalidad requerida
        self.title_bar.mouseDoubleClickEvent = self.title_double_click_event
        
        return self.title_bar
    
    def title_double_click_event(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_maximize()
        event.accept()
    
    def toggle_maximize(self):
        if self.is_maximized:
            self.showNormal()
            if self.previous_geometry:
                self.setGeometry(self.previous_geometry)
            self.is_maximized = False
        else:
            self.previous_geometry = self.geometry()
            self.showMaximized()
            self.is_maximized = True
        self.update_rounded_corners()
    
    def update_rounded_corners(self):
        if self.is_maximized:
            self.setStyleSheet("FramelessWindow { background-color: #2b2b2b; border-radius: 0px; }")
        else:
            self.setStyleSheet("FramelessWindow { background-color: #2b2b2b; border-radius: 8px; }")
        self.update()
    
    def title_mouse_press_event(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def title_mouse_move_event(self, event):
        if event.buttons() == Qt.LeftButton and self.dragging:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
    
    def title_mouse_release_event(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            event.accept()
    
    def close_window(self):
        self.window_closed.emit()
        self.close()
    
    def set_content_layout(self, layout):
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        if hasattr(self, 'title_bar'):
            main_layout.addWidget(self.title_bar)
        
        main_layout.addLayout(layout)
        main_widget.setLayout(main_layout)
        self.setLayout(main_layout)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(43, 43, 43))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 8, 8)