# TESERACTO-UTR/GUI/Windows/FTPConaguaWindow.py

import os
import re
import time
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                            QComboBox, QPushButton, QMessageBox, QTextEdit, QGroupBox,
                            QCheckBox, QApplication, QDialog, QInputDialog, QVBoxLayout,
                            QHBoxLayout, QSpacerItem, QSizePolicy, QFrame)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QKeyEvent
from Core.System.ConfigManager import ConfigManager
from Core.System.StateManager import StateManager
from Core.DataProcessing.Services import RecordFormatter, ConfigProvider, BitmaskConverter, FileNameGenerator
from Core.Network.FTPManager import FTPManager


# ============================================================================
# DIÁLOGOS DE AUTENTICACIÓN NIP - VERSIÓN SIMPLIFICADA Y MODERNA
# ============================================================================

class NIPDialog(QDialog):
    """Diálogo base simplificado para autenticación con NIP"""
    
    def __init__(self, parent=None, titulo="Autenticación NIP", mensaje="Ingrese el NIP:"):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setModal(True)
        self.setFixedSize(400, 250)  # Tamaño compacto y moderno
        self.nip_ingresado = None
        self.setup_ui(mensaje)
        self.apply_clean_theme()
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
    
    def setup_ui(self, mensaje):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Título limpio
        title_label = QLabel(self.windowTitle())
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-size: 16px;
                font-weight: 500;
                margin-bottom: 10px;
                padding-bottom: 10px;
                border-bottom: 1px solid #404040;
            }
        """)
        layout.addWidget(title_label)
        
        # Mensaje principal - limpio y legible
        message_label = QLabel(mensaje)
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("""
            QLabel {
                color: #CCCCCC;
                font-size: 13px;
                margin: 10px 0;
                padding: 10px;
            }
        """)
        layout.addWidget(message_label)
        
        # Frame para el campo NIP
        nip_frame = QFrame()
        nip_frame.setStyleSheet("""
            QFrame {
                background-color: #2A2A2A;
                border: 1px solid #404040;
                border-radius: 6px;
                padding: 15px;
            }
        """)
        nip_layout = QVBoxLayout(nip_frame)
        
        # Etiqueta simple
        nip_label = QLabel("NIP (4 dígitos):")
        nip_label.setAlignment(Qt.AlignCenter)
        nip_label.setStyleSheet("color: #AAAAAA; font-size: 12px; margin-bottom: 8px;")
        nip_layout.addWidget(nip_label)
        
        # Campo NIP - diseño limpio
        self.nip_input = QLineEdit()
        self.nip_input.setEchoMode(QLineEdit.Password)
        self.nip_input.setMaxLength(4)
        self.nip_input.setAlignment(Qt.AlignCenter)
        self.nip_input.setStyleSheet("""
            QLineEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #505050;
                border-radius: 4px;
                padding: 12px;
                font-size: 20px;
                font-family: 'Segoe UI', sans-serif;
                font-weight: 400;
                letter-spacing: 6px;
                min-height: 50px;
            }
            QLineEdit:focus {
                border: 1px solid #0078D7;
                background-color: #252525;
            }
        """)
        self.nip_input.textChanged.connect(self.on_text_changed)
        nip_layout.addWidget(self.nip_input)
        
        layout.addWidget(nip_frame)
        
        # Indicador de teclas sutil
        keys_label = QLabel("Enter: Aceptar | Esc: Cancelar")
        keys_label.setAlignment(Qt.AlignCenter)
        keys_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 11px;
                margin-top: 8px;
            }
        """)
        layout.addWidget(keys_label)
        
        # Espaciador
        layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        # Botones limpios y modernos
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.clicked.connect(self.reject)
        self.btn_cancelar.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                color: #FFFFFF;
                border: 1px solid #505050;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: 500;
                font-size: 13px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:pressed {
                background-color: #606060;
            }
        """)
        
        self.btn_aceptar = QPushButton("Aceptar")
        self.btn_aceptar.clicked.connect(self.verificar_nip)
        self.btn_aceptar.setDefault(True)
        self.btn_aceptar.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: 500;
                font-size: 13px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #106EBE;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
            QPushButton:disabled {
                background-color: #353535;
                color: #777777;
            }
        """)
        
        btn_layout.addWidget(self.btn_cancelar)
        btn_layout.addWidget(self.btn_aceptar)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
    
    def on_text_changed(self, text):
        """Actualiza el estilo cuando el texto cambia"""
        if len(text) == 4:
            self.nip_input.setStyleSheet("""
                QLineEdit {
                    background-color: #1E1E1E;
                    color: #FFFFFF;
                    border: 1px solid #2E7D32;
                    border-radius: 4px;
                    padding: 12px;
                    font-size: 20px;
                    font-family: 'Segoe UI', sans-serif;
                    font-weight: 400;
                    letter-spacing: 6px;
                    min-height: 50px;
                }
            """)
    
    def apply_clean_theme(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #2D2D2D;
                border: 1px solid #404040;
                border-radius: 6px;
            }
        """)
    
    def verificar_nip(self):
        """Método abstracto - debe ser implementado por subclases"""
        raise NotImplementedError("Este método debe ser implementado por la subclase")
    
    def keyPressEvent(self, event: QKeyEvent):
        """Maneja teclas especiales"""
        if event.key() == Qt.Key_Escape:
            self.reject()
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.verificar_nip()
        else:
            super().keyPressEvent(event)


class ConfiguracionInicialDialog(NIPDialog):
    """Diálogo para configuración inicial de NIP - diseño limpio"""
    
    def __init__(self, parent=None):
        super().__init__(parent, "Configuración Inicial", 
                        "Para configurar por primera vez,\n"
                        "ingrese el NIP genérico o NIP Teseracto.")
    
    def verificar_nip(self):
        self.btn_aceptar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
        
        nip = self.nip_input.text().strip()
        
        if len(nip) != 4 or not nip.isdigit():
            QMessageBox.warning(self, "NIP Inválido", 
                              "El NIP debe tener 4 dígitos numéricos.")
            self.btn_aceptar.setEnabled(True)
            self.btn_cancelar.setEnabled(True)
            self.nip_input.selectAll()
            self.nip_input.setFocus()
            return
        
        # Verificar NIP genérico o Teseracto
        if (ConfigManager.validar_nip_ventana("FTPConaguaWindow", "nip_generico", nip) or
            ConfigManager.validar_nip_ventana("FTPConaguaWindow", "nip_teseracto", nip)):
            
            # NIP correcto, ahora configurar nuevo NIP Unidad de Inspección
            self.configurar_nuevo_nip()
        else:
            QMessageBox.warning(self, "NIP Incorrecto", 
                              "NIP inválido. Verifique e intente nuevamente.")
        
        self.btn_aceptar.setEnabled(True)
        self.btn_cancelar.setEnabled(True)
    
    def configurar_nuevo_nip(self):
        """Configura un nuevo NIP de Unidad de Inspección"""
        # Primer paso: Nuevo NIP
        nuevo_nip, ok = QInputDialog.getText(
            self, 
            "Nuevo NIP - Paso 1/2",
            "Ingrese el nuevo NIP de Unidad de Inspección (4 dígitos):",
            QLineEdit.Password, 
            ""
        )
        
        if not ok or not nuevo_nip:
            return
        
        if len(nuevo_nip) != 4 or not nuevo_nip.isdigit():
            QMessageBox.warning(self, "NIP Inválido", 
                              "El NIP debe tener 4 dígitos numéricos.")
            return
        
        # Segundo paso: Confirmar NIP
        confirmar_nip, ok = QInputDialog.getText(
            self,
            "Nuevo NIP - Paso 2/2",
            "Confirme el nuevo NIP:",
            QLineEdit.Password,
            ""
        )
        
        if not ok:
            return
        
        if nuevo_nip != confirmar_nip:
            QMessageBox.warning(self, "NIP No Coincide", 
                              "Los NIPs no coinciden. Intente nuevamente.")
            return
        
        # Guardar nuevo NIP
        ConfigManager.guardar_nip_ventana("FTPConaguaWindow", "nip_unidad_inspeccion", nuevo_nip)
        
        QMessageBox.information(self, "NIP Configurado", 
                              "NIP de Unidad de Inspección configurado.\n\n"
                              "Guarde este NIP en un lugar seguro.")
        
        self.nip_ingresado = nuevo_nip
        self.accept()


class AccesoDialog(NIPDialog):
    """Diálogo para acceso normal con NIP - diseño limpio"""
    
    def __init__(self, parent=None, es_cambio_nip=False):
        if es_cambio_nip:
            mensaje = "Para cambiar el NIP, ingrese el NIP Teseracto:"
        else:
            mensaje = "Para acceder a la Unidad de Inspección,\ningrese su NIP:"
        
        titulo = "Cambiar NIP" if es_cambio_nip else "Acceso a Unidad de Inspección"
        super().__init__(parent, titulo, mensaje)
        self.es_cambio_nip = es_cambio_nip
    
    def verificar_nip(self):
        self.btn_aceptar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
        
        nip = self.nip_input.text().strip()
        
        if len(nip) != 4 or not nip.isdigit():
            QMessageBox.warning(self, "NIP Inválido", 
                              "El NIP debe tener 4 dígitos numéricos.")
            self.btn_aceptar.setEnabled(True)
            self.btn_cancelar.setEnabled(True)
            self.nip_input.selectAll()
            self.nip_input.setFocus()
            return
        
        if self.es_cambio_nip:
            # Modo cambio de NIP: solo verificar NIP Teseracto
            if ConfigManager.validar_nip_ventana("FTPConaguaWindow", "nip_teseracto", nip):
                self.nip_ingresado = nip
                self.accept()
            else:
                QMessageBox.warning(self, "NIP Incorrecto", 
                                  "NIP Teseracto incorrecto.")
                self.btn_aceptar.setEnabled(True)
                self.btn_cancelar.setEnabled(True)
        else:
            # Modo acceso normal: verificar NIP Unidad de Inspección o Teseracto
            if ConfigManager.validar_nip_ventana("FTPConaguaWindow", "nip_unidad_inspeccion", nip):
                self.nip_ingresado = nip
                self.accept()
            elif ConfigManager.validar_nip_ventana("FTPConaguaWindow", "nip_teseracto", nip):
                # NIP Teseracto ingresado - preguntar si quiere cambiar NIP
                respuesta = QMessageBox.question(
                    self, 
                    "NIP Teseracto Detectado",
                    "¿Desea cambiar el NIP de Unidad de Inspección?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if respuesta == QMessageBox.Yes:
                    self.cambiar_nip_unidad_inspeccion()
                else:
                    self.nip_ingresado = nip
                    self.accept()
            else:
                QMessageBox.warning(self, "NIP Incorrecto", 
                                  "NIP incorrecto. Verifique e intente nuevamente.")
                self.btn_aceptar.setEnabled(True)
                self.btn_cancelar.setEnabled(True)
    
    def cambiar_nip_unidad_inspeccion(self):
        """Cambia el NIP de Unidad de Inspección"""
        # Pedir nuevo NIP
        nuevo_nip, ok = QInputDialog.getText(
            self, 
            "Nuevo NIP",
            "Ingrese el nuevo NIP de Unidad de Inspección (4 dígitos):",
            QLineEdit.Password, 
            ""
        )
        
        if not ok:
            return
        
        if len(nuevo_nip) != 4 or not nuevo_nip.isdigit():
            QMessageBox.warning(self, "NIP Inválido", "El NIP debe tener 4 dígitos.")
            return
        
        # Confirmar NIP
        confirmar_nip, ok = QInputDialog.getText(
            self,
            "Confirmar NIP",
            "Confirme el nuevo NIP:",
            QLineEdit.Password,
            ""
        )
        
        if not ok:
            return
        
        if nuevo_nip != confirmar_nip:
            QMessageBox.warning(self, "NIP No Coincide", "Los NIPs no coinciden.")
            return
        
        # Guardar nuevo NIP
        ConfigManager.guardar_nip_ventana("FTPConaguaWindow", "nip_unidad_inspeccion", nuevo_nip)
        
        QMessageBox.information(self, "NIP Actualizado", 
                              "NIP de Unidad de Inspección actualizado.\n\n"
                              "Guarde este NIP en un lugar seguro.")
        
        self.nip_ingresado = nuevo_nip
        self.accept()


# ============================================================================
# VENTANA PRINCIPAL FTPConaguaWindow (CON MANEJO MEJORADO)
# ============================================================================

class FTPConaguaWindow(QWidget):
    # Señal para indicar que la ventana se cerró
    window_closed = pyqtSignal()
    
    def __init__(self, error_handler):
        super().__init__()
        self.error_handler = error_handler
        self._initialized = False
        self._auth_success = False
        
        # ✅ PRIMERO: VERIFICAR AUTENTICACIÓN CON MANEJO MEJORADO
        self._auth_success = self.verificar_autenticacion()
        
        if not self._auth_success:
            # ✅ CORREGIDO: Cerrar completamente sin dejar ventanas residuales
            self.deleteLater()
            return
        
        # ✅ SEGUNDO: CONFIGURAR INTERFAZ SI AUTENTICACIÓN EXITOSA
        self._initialized = True
        self.setWindowTitle("Unidad de Inspección")
        self.setGeometry(100, 100, 600, 750)
        self.current_content = None
        self.current_filename = None
        self.setup_ui()
        self.load_ftp_config()
        self.apply_dark_theme()
        self._progress_label = None
        self._progress_timer = QTimer()
    
    def verificar_autenticacion(self):
        """Verifica la autenticación del usuario antes de mostrar la ventana"""
        try:
            # Determinar qué diálogo mostrar
            if not ConfigManager.existe_nip_unidad_inspeccion("FTPConaguaWindow"):
                # Primera vez: configuración inicial
                dialog = ConfiguracionInicialDialog(self)
                resultado = dialog.exec_()
                
                if resultado == QDialog.Accepted:
                    return True
                else:
                    # Usuario canceló - cerrar completamente
                    return False
            else:
                # Acceso normal
                dialog = AccesoDialog(self)
                resultado = dialog.exec_()
                
                if resultado == QDialog.Accepted:
                    return True
                else:
                    # Usuario canceló - cerrar completamente
                    return False
                    
        except Exception as e:
            print(f"Error en autenticación: {e}")
            return False
    
    def closeEvent(self, event):
        """Maneja el cierre de la ventana"""
        self.window_closed.emit()
        super().closeEvent(event)
    
    def setup_ui(self):
        # [El resto del código de setup_ui permanece igual]
        # ... (mismo código que antes para la interfaz principal)
        layout = QVBoxLayout()

        # Grupo para configuración FTP
        ftp_group = QGroupBox("Configuración FTP")
        ftp_layout = QVBoxLayout()

        # Campos FTP
        self.ftp_host = QLineEdit()
        self.ftp_port = QLineEdit("21")
        self.ftp_user = QLineEdit()
        self.ftp_password = QLineEdit()
        self.ftp_password.setEchoMode(QLineEdit.Password)
        self.ftp_remote_path = QLineEdit()

        ftp_layout.addWidget(QLabel("Servidor FTP:"))
        ftp_layout.addWidget(self.ftp_host)
        ftp_layout.addWidget(QLabel("Puerto:"))
        ftp_layout.addWidget(self.ftp_port)
        ftp_layout.addWidget(QLabel("Usuario:"))
        ftp_layout.addWidget(self.ftp_user)
        ftp_layout.addWidget(QLabel("Contraseña:"))
        ftp_layout.addWidget(self.ftp_password)
        ftp_layout.addWidget(QLabel("Ruta remota (opcional):"))
        ftp_layout.addWidget(self.ftp_remote_path)

        ftp_group.setLayout(ftp_layout)
        layout.addWidget(ftp_group)

        # Grupo para reporte CONAGUA
        report_group = QGroupBox("Reporte Unidad de Inspección")
        report_layout = QVBoxLayout()

        # Tipo de reporte
        report_layout.addWidget(QLabel("Tipo de reporte:"))
        self.report_type_combo = QComboBox()
        self.report_type_combo.addItems(["Medidor", "SistemaMedicion"])
        report_layout.addWidget(self.report_type_combo)

        # Clave para la Unidad de Inspección
        report_layout.addWidget(QLabel("Clave Unidad de Inspección:"))
        self.clave_conagua = QLineEdit()
        self.clave_conagua.setMaxLength(5)
        self.clave_conagua.setPlaceholderText("Ejemplo: AB123")
        report_layout.addWidget(self.clave_conagua)

        # ✅ MEJORADO: Botón para cambiar NIP con mejor diseño
        self.btn_cambiar_nip = QPushButton("🔐 Cambiar NIP de Unidad de Inspección")
        self.btn_cambiar_nip.clicked.connect(self.cambiar_nip)
        self.btn_cambiar_nip.setToolTip("Solo administradores con NIP Teseracto")
        self.btn_cambiar_nip.setStyleSheet("""
            QPushButton {
                background-color: #5a5a5a;
                color: white;
                border: 1px solid #666;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #666666;
                border: 1px solid #777;
            }
            QPushButton:pressed {
                background-color: #777777;
            }
        """)
        report_layout.addWidget(self.btn_cambiar_nip)

        # Opción de reintentos inteligentes
        self.retry_checkbox = QCheckBox("Reintentar lectura automáticamente (hasta 3 veces si falla)")
        self.retry_checkbox.setChecked(True)
        report_layout.addWidget(self.retry_checkbox)

        # Botones de generación
        btn_layout = QHBoxLayout()
        self.generate_btn = QPushButton("📊 Generar reporte para Unidad de Inspección")
        self.generate_btn.clicked.connect(self.generate_report)
        self.clear_btn = QPushButton("🗑️ Borrar reporte")
        self.clear_btn.clicked.connect(self.clear_report)
        self.clear_btn.setEnabled(False)
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addWidget(self.clear_btn)
        report_layout.addLayout(btn_layout)

        # Mostrar nombre de archivo
        report_layout.addWidget(QLabel("Nombre de archivo:"))
        self.filename_label = QLabel("")
        self.filename_label.setWordWrap(True)
        self.filename_label.setStyleSheet("color: #90caf9; font-weight: bold; padding: 5px;")
        report_layout.addWidget(self.filename_label)

        # Mostrar contenido
        report_layout.addWidget(QLabel("Contenido del reporte:"))
        self.content_text = QTextEdit()
        self.content_text.setReadOnly(True)
        self.content_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #f0f0f0;
                border: 1px solid #444;
                border-radius: 5px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }
        """)
        report_layout.addWidget(self.content_text)

        report_group.setLayout(report_layout)
        layout.addWidget(report_group)

        # Botón de enviar
        self.send_btn = QPushButton("📤 Enviar a servidor")
        self.send_btn.clicked.connect(self.send_report)
        self.send_btn.setEnabled(False)
        layout.addWidget(self.send_btn)

        self.setLayout(layout)
    
    def cambiar_nip(self):
        """Permite cambiar el NIP de Unidad de Inspección usando NIP Teseracto"""
        dialog = AccesoDialog(self, es_cambio_nip=True)
        if dialog.exec_() == QDialog.Accepted:
            # Ahora mostrar diálogo para nuevo NIP
            self.configurar_nuevo_nip_unidad_inspeccion()
    
    def configurar_nuevo_nip_unidad_inspeccion(self):
        """Configura un nuevo NIP de Unidad de Inspección con mejor diseño"""
        # Pedir nuevo NIP
        nuevo_nip, ok = QInputDialog.getText(
            self, 
            "Nuevo NIP de Unidad de Inspección",
            "Ingrese el nuevo NIP de Unidad de Inspección (4 dígitos):",
            QLineEdit.Password, 
            ""
        )
        
        if not ok:
            return
        
        if len(nuevo_nip) != 4 or not nuevo_nip.isdigit():
            QMessageBox.warning(self, "NIP Inválido", "El NIP debe tener exactamente 4 dígitos.")
            return
        
        # Confirmar NIP
        confirmar_nip, ok = QInputDialog.getText(
            self,
            "Confirmar Nuevo NIP",
            "Confirme el nuevo NIP de Unidad de Inspección:",
            QLineEdit.Password,
            ""
        )
        
        if not ok:
            return
        
        if nuevo_nip != confirmar_nip:
            QMessageBox.warning(self, "NIP No Coincide", "Los NIPs no coinciden. Intente nuevamente.")
            return
        
        # Guardar nuevo NIP
        ConfigManager.guardar_nip_ventana("FTPConaguaWindow", "nip_unidad_inspeccion", nuevo_nip)
        
        # Mensaje de éxito mejorado
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("✅ NIP Actualizado")
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setText("NIP de Unidad de Inspección actualizado exitosamente")
        msg_box.setInformativeText(
            f"Nuevo NIP configurado: ••••\n\n"
            "⚠️ IMPORTANTE:\n"
            "• Guarde este NIP en un lugar seguro\n"
            "• Compártalo solo con personal autorizado\n"
            "• El próximo acceso requerirá este NIP"
        )
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

    # ============================================================================
    # MÉTODOS EXISTENTES (SIN MODIFICACIONES SIGNIFICATIVAS)
    # ============================================================================
    
    def apply_dark_theme(self):
        dark_theme = """
            QWidget {
                background-color: #2b2b2b;
                color: #cccccc;
                font-family: Segoe UI;
            }
            QLabel {
                color: #cccccc;
                padding: 2px;
            }
            QComboBox, QLineEdit, QTextEdit {
                background-color: #3b3b3b;
                color: white;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
            }
            QComboBox:hover, QLineEdit:hover, QTextEdit:hover {
                border: 1px solid #777777;
            }
            QPushButton {
                background-color: #5a5a5a;
                color: white;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #666666;
                border: 1px solid #777777;
            }
            QPushButton:pressed {
                background-color: #777777;
            }
            QPushButton:disabled {
                background-color: #3b3b3b;
                color: #777777;
            }
            QGroupBox {
                color: #cccccc;
                background-color: #2b2b2b;
                border: 1px solid #444444;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #cccccc;
            }
            QCheckBox {
                color: #cccccc;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """
        self.setStyleSheet(dark_theme)

    def load_ftp_config(self):
        """Cargar configuración FTP existente si está disponible"""
        try:
            config = ConfigManager.cargar_config_ftp()
            self.ftp_host.setText(config.get("host", ""))
            self.ftp_port.setText(str(config.get("port", "21")))
            self.ftp_user.setText(config.get("usuario", ""))
            self.ftp_password.setText(config.get("clave", ""))
            self.ftp_remote_path.setText(config.get("ruta_remota", ""))
        except:
            pass

    def validate_clave(self, clave):
        """Validar formato de clave CONAGUA: 2 letras + 3 números"""
        if len(clave) != 5:
            return False
        if not clave[:2].isalpha():
            return False
        if not clave[2:].isdigit():
            return False
        return True

    def format_conagua_report(self, tipo_reporte: str, ker_code: str, clave: str, 
                             flujo_inst: float = 0.0, flujo_acum: float = 0.0) -> str:
        """Formatea el reporte específicamente para la Unidad de Inspección"""
        try:
            config = ConfigManager.cargar_config_general()
            now = datetime.now()
            fecha = now.strftime("%Y%m%d")
            hora = now.strftime("%H%M%S")
            ker_code_str = str(ker_code).zfill(3)
            
            if tipo_reporte == "Medidor":
                # ✅ MODIFICADO: Reemplazar NSUE por NSUT
                return (
                    f"M|{fecha}|{hora}|{config['RFC']}|{config['NSM']}|{config['NSUT']}|"
                    f"{config['Lat']}|{config['Long']}|{ker_code_str}|{clave}"
                )
            elif tipo_reporte == "SistemaMedicion":
                # ✅ MODIFICADO: Agregar NSUT después de RFC e incluir lecturas
                return (
                    f"QA|{fecha}|{hora}|{config['RFC']}|{config['NSUT']}|"
                    f"{flujo_inst:.3f}|{flujo_acum:.3f}|"
                    f"{config['Lat']}|{config['Long']}|{ker_code_str}|{clave}"
                )
            else:
                raise ValueError("Tipo de reporte inválido")
                
        except Exception as e:
            ker_code_str = str(ker_code).zfill(3)
            return f"ERR|{datetime.now().strftime('%Y%m%d|%H%M%S')}|{type(e).__name__}|{str(e)}|{ker_code_str}|{clave}"

    def generate_conagua_filename(self, tipo_reporte: str, clave: str) -> str:
        """Genera nombre de archivo específico para Unidad de Inspección con la clave incluida"""
        try:
            config_provider = ConfigProvider(ConfigManager())
            name_gen = FileNameGenerator(config_provider)
            
            base_name = name_gen.generate_daily_name(tipo_reporte)
            
            if base_name.endswith('.txt'):
                name_without_ext = base_name[:-4]
                return f"{name_without_ext}_{clave}.txt"
            else:
                return f"{base_name}_{clave}.txt"
                
        except Exception as e:
            fecha = datetime.now().strftime("%Y%m%d")
            return f"reporte_conagua_{fecha}_{clave}.txt"

    def mostrar_progreso(self, mensaje: str):
        """Muestra mensaje de progreso sin bloquear la UI"""
        if not self._progress_label:
            self._progress_label = QLabel(mensaje, self)
            self._progress_label.setAlignment(Qt.AlignCenter)
            self._progress_label.setStyleSheet("color: #FFA500; font-weight: bold;")
            self.layout().insertWidget(1, self._progress_label)
        else:
            self._progress_label.setText(mensaje)
        
        QApplication.processEvents()

    def ocultar_progreso(self):
        """Oculta la etiqueta de progreso"""
        if self._progress_label:
            self._progress_label.hide()
            self._progress_label = None
        QApplication.processEvents()

    def obtener_lecturas_confiables(self, medidor, max_intentos=3, delay_entre_intentos=1.0):
        """
        Intenta obtener lecturas válidas con reintentos inteligentes.
        Retorna: (flujo_instantaneo, flujo_acumulado, intentos_realizados, mensaje_estado)
        """
        intentos = 0
        mejores_lecturas = (0.0, 0.0)
        ultimo_error = ""
        
        hacer_reintentos = self.retry_checkbox.isChecked()
        if not hacer_reintentos:
            max_intentos = 1
        
        for intento in range(max_intentos):
            intentos += 1
            
            try:
                if intento > 0:
                    self.mostrar_progreso(f"Intento {intento+1}/{max_intentos}...")
                
                datos = medidor.leer_registros()
                
                if datos:
                    flujo_inst = datos.get("flujo_instantaneo", 0.0)
                    flujo_acum = datos.get("flujo_acumulado", 0.0)
                    
                    try:
                        flujo_inst = float(flujo_inst) if flujo_inst is not None else 0.0
                        flujo_acum = float(flujo_acum) if flujo_acum is not None else 0.0
                    except (ValueError, TypeError):
                        ultimo_error = f"Valores no numéricos en intento {intento+1}"
                        continue
                    
                    if isinstance(flujo_inst, (int, float)) and isinstance(flujo_acum, (int, float)):
                        if flujo_inst != 0.0 or flujo_acum != 0.0:
                            self.ocultar_progreso()
                            return flujo_inst, flujo_acum, intentos, f"Lectura exitosa en intento {intentos}"
                        
                        mejores_lecturas = (flujo_inst, flujo_acum)
                        ultimo_error = f"Lecturas en 0.0 en intento {intento+1}"
                else:
                    ultimo_error = f"Datos vacíos en intento {intento+1}"
            
            except Exception as e:
                ultimo_error = f"Error en intento {intento+1}: {str(e)}"
            
            if intento < max_intentos - 1 and hacer_reintentos:
                time.sleep(delay_entre_intentos)
        
        self.ocultar_progreso()
        mensaje = f"Usando valores de respaldo después de {intentos} intentos"
        if ultimo_error:
            mensaje += f" ({ultimo_error})"
        
        return mejores_lecturas[0], mejores_lecturas[1], intentos, mensaje

    def generate_report(self):
        """Generar el reporte CONAGUA con lecturas confiables"""
        clave = self.clave_conagua.text().strip()
        if not self.validate_clave(clave):
            QMessageBox.warning(self, "Clave inválida", 
                            "La clave de Unidad de Inspección debe tener exactamente 2 letras seguidas de 3 números.")
            return

        medidor = StateManager.get_state('medidor')
        if not medidor:
            QMessageBox.warning(self, "Error", "No hay medidor configurado o conectado.")
            return

        self.mostrar_progreso("Obteniendo lecturas del medidor...")
        flujo_inst, flujo_acum, intentos, mensaje_estado = self.obtener_lecturas_confiables(medidor)
        
        if intentos > 1:
            self.mostrar_progreso(mensaje_estado)
            QApplication.processEvents()
            time.sleep(1)
        
        if flujo_inst == 0.0 and flujo_acum == 0.0 and intentos >= 3:
            respuesta = QMessageBox.question(
                self, 
                "Advertencia - Lecturas en 0.0",
                "Las lecturas son 0.0 después de múltiples intentos.\n\n" +
                "Posibles causas:\n" +
                "1. El medidor está en reposo (sin flujo)\n" +
                "2. Problemas de conexión\n" +
                "3. Configuración incorrecta\n\n" +
                "¿Desea continuar con valores 0.0?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if respuesta == QMessageBox.No:
                self.ocultar_progreso()
                return
        
        ker_code = self.error_handler.get_ker_code()
        tipo_reporte = self.report_type_combo.currentText()

        try:
            if tipo_reporte == "Medidor":
                contenido = self.format_conagua_report(tipo_reporte, ker_code, clave)
            elif tipo_reporte == "SistemaMedicion":
                contenido = self.format_conagua_report(tipo_reporte, ker_code, clave, flujo_inst, flujo_acum)
            
            filename = self.generate_conagua_filename(tipo_reporte, clave)

        except Exception as e:
            self.ocultar_progreso()
            QMessageBox.warning(self, "Error", 
                            f"Error al formatear el reporte: {str(e)}")
            return

        self.filename_label.setText(filename)
        self.content_text.setPlainText(contenido)

        self.clear_btn.setEnabled(True)
        self.send_btn.setEnabled(True)

        self.current_content = contenido
        self.current_filename = filename

        self.ocultar_progreso()
        
        if intentos == 1:
            QMessageBox.information(self, "Éxito", 
                                "Reporte para Unidad de Inspección generado correctamente en 1 intento.")
        else:
            QMessageBox.information(self, "Éxito", 
                                f"Reporte generado correctamente después de {intentos} intentos.")

    def clear_report(self):
        """Limpiar el reporte generado"""
        self.filename_label.setText("")
        self.content_text.setPlainText("")
        self.current_content = None
        self.current_filename = None
        self.clear_btn.setEnabled(False)
        self.send_btn.setEnabled(False)

    def send_report(self):
        """Enviar el reporte al servidor FTP"""
        if not self.current_content or not self.current_filename:
            QMessageBox.warning(self, "Error", "No hay reporte generado para enviar.")
            return

        # Validar campos FTP
        host = self.ftp_host.text().strip()
        port = self.ftp_port.text().strip()
        user = self.ftp_user.text().strip()
        password = self.ftp_password.text().strip()
        remote_path = self.ftp_remote_path.text().strip()

        if not host or not user or not password:
            QMessageBox.warning(self, "Error", 
                            "Complete los campos obligatorios del FTP (servidor, usuario y contraseña).")
            return

        # Crear archivo temporal
        temp_path = os.path.join(os.getcwd(), self.current_filename)
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(self.current_content)
        except Exception as e:
            QMessageBox.warning(self, "Error", 
                            f"No se pudo crear el archivo temporal: {str(e)}")
            return

        # Enviar via FTP
        try:
            # Crear configuración para FTPManager
            ftp_config = {
                "host": host,
                "usuario": user,
                "clave": password,
                "port": int(port) if port else 21,
                "ruta_remota": remote_path
            }
            ftp_manager = FTPManager(ftp_config, self.error_handler)
            remote_filename = os.path.join(remote_path, self.current_filename) if remote_path else self.current_filename
            success = ftp_manager.enviar_archivo(temp_path, remote_filename)
            if success:
                QMessageBox.information(self, "Éxito", "Reporte enviado correctamente al servidor FTP.")
            else:
                QMessageBox.warning(self, "Error", "No se pudo enviar el reporte. Verifique la conexión.")
        except Exception as e:
            QMessageBox.warning(self, "Error", 
                            f"Error al enviar el reporte: {str(e)}")
        finally:
            # Eliminar archivo temporal
            try:
                os.remove(temp_path)
            except:
                pass
            self.ocultar_progreso()