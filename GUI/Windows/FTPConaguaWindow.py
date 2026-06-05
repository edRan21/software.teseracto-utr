# TESERACTO-UTR/GUI/Windows/FTPConaguaWindow.py

import os
import time
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                            QComboBox, QPushButton, QMessageBox, QTextEdit, QGroupBox,
                            QCheckBox, QApplication, QDialog, QInputDialog,
                            QSpacerItem, QSizePolicy, QFrame, QFormLayout, QScrollArea, QGridLayout)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QKeyEvent
from Core.System.ConfigManager import ConfigManager
from Core.System.StateManager import StateManager
from Core.DataProcessing.Services import RecordFormatter, ConfigProvider, BitmaskConverter, FileNameGenerator
from Core.Network.FTPManager import FTPManager
from Core.DataProcessing.DataProcessor import DataProcessor
from Core.DataProcessing.Services import UnitConverter

# ============================================================================
# DIÁLOGOS DE AUTENTICACIÓN NIP 
# ============================================================================

class NIPDialog(QDialog):
    """Diálogo base para autenticación con NIP"""
    
    def __init__(self, parent=None, titulo="Autenticación NIP", mensaje="Ingrese el NIP:"):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        
        # ✅ SOLUCIÓN DEFINITIVA AL COLAPSO GEOMÉTRICO: 
        # setFixedSize obliga a la pantalla táctil a respetar el área. No se apachurrará.
        self.setFixedSize(450, 280)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b; 
                color: #cccccc; 
                border: 2px solid #555; 
                border-radius: 8px;
            }
            QLabel {
                color: #cccccc;
                font-size: 12pt;
            }
            QLineEdit {
                background-color: #1e1e1e;
                color: #4fc3f7;
                border: 1px solid #555;
                border-radius: 4px;
                font-size: 18pt;
                font-weight: bold;
                letter-spacing: 5px;
            }
            QPushButton {
                background-color: #5a5a5a;
                color: white;
                border: 1px solid #666;
                border-radius: 4px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #2E86C1;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        lbl_mensaje = QLabel(mensaje)
        lbl_mensaje.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_mensaje)
        
        self.nip_input = QLineEdit()
        self.nip_input.setEchoMode(QLineEdit.Password)
        self.nip_input.setMaxLength(4)
        self.nip_input.setFixedSize(160, 45) 
        self.nip_input.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.nip_input, 0, Qt.AlignCenter)
        
        # Espaciador para empujar los botones abajo
        layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        btn_layout = QHBoxLayout()
        self.btn_aceptar = QPushButton("Aceptar")
        self.btn_aceptar.setMinimumHeight(45) 
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setMinimumHeight(45)
        
        btn_layout.addWidget(self.btn_cancelar)
        btn_layout.addWidget(self.btn_aceptar)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        self.btn_aceptar.clicked.connect(self.verificar_nip)
        self.btn_cancelar.clicked.connect(self.reject)

    def verificar_nip(self):
        raise NotImplementedError("Este método debe ser implementado por la subclase")
    
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.reject()
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.verificar_nip()
        else:
            super().keyPressEvent(event)

class ConfiguracionInicialDialog(NIPDialog):
    def __init__(self, parent=None):
        super().__init__(parent, "Configuración Inicial", 
                        "Para configurar por primera vez,\ningrese el NIP genérico o NIP Teseracto.")
    
    def verificar_nip(self):
        self.btn_aceptar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
        
        nip = self.nip_input.text().strip()
        
        if len(nip) != 4 or not nip.isdigit():
            QMessageBox.warning(self, "NIP Inválido", "El NIP debe tener 4 dígitos numéricos.")
            self.btn_aceptar.setEnabled(True)
            self.btn_cancelar.setEnabled(True)
            self.nip_input.selectAll()
            self.nip_input.setFocus()
            return
        
        if (ConfigManager.validar_nip_ventana("FTPConaguaWindow", "nip_generico", nip) or
            ConfigManager.validar_nip_ventana("FTPConaguaWindow", "nip_teseracto", nip)):
            self.configurar_nuevo_nip()
        else:
            QMessageBox.warning(self, "NIP Incorrecto", "NIP inválido. Verifique e intente nuevamente.")
        
        self.btn_aceptar.setEnabled(True)
        self.btn_cancelar.setEnabled(True)
    
    def configurar_nuevo_nip(self):
        nuevo_nip, ok = QInputDialog.getText(self, "Nuevo NIP - Paso 1/2",
            "Ingrese el nuevo NIP de Unidad de Inspección (4 dígitos):", QLineEdit.Password, "")
        
        if not ok or not nuevo_nip: return
        if len(nuevo_nip) != 4 or not nuevo_nip.isdigit():
            QMessageBox.warning(self, "NIP Inválido", "El NIP debe tener 4 dígitos numéricos.")
            return
            
        confirmar_nip, ok = QInputDialog.getText(self, "Nuevo NIP - Paso 2/2",
            "Confirme el nuevo NIP:", QLineEdit.Password, "")
            
        if not ok: return
        if nuevo_nip != confirmar_nip:
            QMessageBox.warning(self, "NIP No Coincide", "Los NIPs no coinciden. Intente nuevamente.")
            return
            
        ConfigManager.guardar_nip_ventana("FTPConaguaWindow", "nip_unidad_inspeccion", nuevo_nip)
        QMessageBox.information(self, "NIP Configurado", "NIP de Unidad de Inspección configurado.\nGuarde este NIP en un lugar seguro.")
        
        self.nip_ingresado = nuevo_nip
        self.accept()

class AccesoDialog(NIPDialog):
    def __init__(self, parent=None, es_cambio_nip=False):
        mensaje = "Para cambiar el NIP, ingrese el NIP Teseracto:" if es_cambio_nip else "Para acceder a la Unidad de Inspección,\ningrese su NIP:"
        titulo = "Cambiar NIP" if es_cambio_nip else "Acceso a Unidad de Inspección"
        super().__init__(parent, titulo, mensaje)
        self.es_cambio_nip = es_cambio_nip
    
    def verificar_nip(self):
        self.btn_aceptar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
        nip = self.nip_input.text().strip()
        
        if len(nip) != 4 or not nip.isdigit():
            QMessageBox.warning(self, "NIP Inválido", "El NIP debe tener 4 dígitos numéricos.")
            self.btn_aceptar.setEnabled(True)
            self.btn_cancelar.setEnabled(True)
            return
            
        if self.es_cambio_nip:
            if ConfigManager.validar_nip_ventana("FTPConaguaWindow", "nip_teseracto", nip):
                self.nip_ingresado = nip
                self.accept()
            else:
                QMessageBox.warning(self, "NIP Incorrecto", "NIP Teseracto incorrecto.")
                self.btn_aceptar.setEnabled(True)
                self.btn_cancelar.setEnabled(True)
        else:
            if ConfigManager.validar_nip_ventana("FTPConaguaWindow", "nip_unidad_inspeccion", nip):
                self.nip_ingresado = nip
                self.accept()
            elif ConfigManager.validar_nip_ventana("FTPConaguaWindow", "nip_teseracto", nip):
                respuesta = QMessageBox.question(self, "NIP Teseracto Detectado",
                    "¿Desea cambiar el NIP de Unidad de Inspección?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if respuesta == QMessageBox.Yes:
                    self.cambiar_nip_unidad_inspeccion()
                else:
                    self.nip_ingresado = nip
                    self.accept()
            else:
                QMessageBox.warning(self, "NIP Incorrecto", "NIP incorrecto. Verifique e intente nuevamente.")
                self.btn_aceptar.setEnabled(True)
                self.btn_cancelar.setEnabled(True)
                
    def cambiar_nip_unidad_inspeccion(self):
        nuevo_nip, ok = QInputDialog.getText(self, "Nuevo NIP", "Ingrese el nuevo NIP (4 dígitos):", QLineEdit.Password, "")
        if not ok: 
            # ✅ REPARACIÓN: Volver a activar botones si el usuario cancela
            self.btn_aceptar.setEnabled(True)
            self.btn_cancelar.setEnabled(True)
            return
            
        if len(nuevo_nip) != 4 or not nuevo_nip.isdigit():
            QMessageBox.warning(self, "NIP Inválido", "El NIP debe tener 4 dígitos.")
            self.btn_aceptar.setEnabled(True)
            self.btn_cancelar.setEnabled(True)
            return
            
        confirmar_nip, ok = QInputDialog.getText(self, "Confirmar NIP", "Confirme el nuevo NIP:", QLineEdit.Password, "")
        if not ok: 
            self.btn_aceptar.setEnabled(True)
            self.btn_cancelar.setEnabled(True)
            return
            
        if nuevo_nip != confirmar_nip:
            QMessageBox.warning(self, "NIP No Coincide", "Los NIPs no coinciden.")
            self.btn_aceptar.setEnabled(True)
            self.btn_cancelar.setEnabled(True)
            return
            
        ConfigManager.guardar_nip_ventana("FTPConaguaWindow", "nip_unidad_inspeccion", nuevo_nip)
        QMessageBox.information(self, "NIP Actualizado", "NIP actualizado exitosamente.")
        self.nip_ingresado = nuevo_nip
        self.accept()
# ============================================================================
# VENTANA PRINCIPAL FTPConaguaWindow
# ============================================================================

class FTPConaguaWindow(QWidget):
    window_closed = pyqtSignal()
    
    def __init__(self, error_handler):
        super().__init__()
        self.error_handler = error_handler
        self._initialized = False
        self._auth_success = False
        self.data_processor = DataProcessor(UnitConverter())
        
        self._auth_success = self.verificar_autenticacion()
        
        if not self._auth_success:
            self.deleteLater()
            return
            
        self._initialized = True
        self.setWindowTitle("Unidad de Inspección")
        self.setGeometry(100, 100, 600, 750)
        self.current_content = None
        self.current_filename = None
        
        # ✅ AHORA EL SETUP DE LA UI ESTÁ ALINEADO CON TUS VARIABLES ORIGINALES
        self.setup_ui()
        self.load_ftp_config()
        self.apply_dark_theme()
        
        self._progress_label = None
        self._progress_timer = QTimer()
        
    def solicitar_acceso(self) -> bool:
        if not self._auth_success:
            self._auth_success = self.verificar_autenticacion()
        return self._auth_success
    
    def verificar_autenticacion(self):
        try:
            if not ConfigManager.existe_nip_unidad_inspeccion("FTPConaguaWindow"):
                dialog = ConfiguracionInicialDialog(self)
            else:
                dialog = AccesoDialog(self)
                
            return dialog.exec_() == QDialog.Accepted
        except Exception as e:
            if hasattr(self, 'error_handler') and self.error_handler:
                self.error_handler.log_error("010", f"Error en sistema de autenticación NIP: {e}", es_error_sistema=True)
            return False
            
    def closeEvent(self, event):
        self.window_closed.emit()
        super().closeEvent(event)
    
    def setup_ui(self):
        window_layout = QVBoxLayout()
        window_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        content_widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("Transmisión FTP de Unidad de Inspección")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        ftp_group = QGroupBox("Credenciales y Ruta FTP")
        ftp_layout = QFormLayout()
        
        # ✅ SE RESPETAN TUS NOMBRES EXACTOS PARA QUE NO TRUENE EL ENVÍO
        self.ftp_host = QLineEdit()
        self.ftp_host.setPlaceholderText("Ej: ftp.conagua.gob.mx")
        ftp_layout.addRow("Servidor (Host):", self.ftp_host)
        
        self.ftp_user = QLineEdit()
        ftp_layout.addRow("Usuario:", self.ftp_user)
        
        self.ftp_password = QLineEdit()
        self.ftp_password.setEchoMode(QLineEdit.Password)
        ftp_layout.addRow("Contraseña:", self.ftp_password)
        
        self.ftp_port = QLineEdit("21")
        ftp_layout.addRow("Puerto:", self.ftp_port)
        
        self.ftp_remote_path = QLineEdit("/")
        ftp_layout.addRow("Ruta Remota:", self.ftp_remote_path)
        
        ftp_group.setLayout(ftp_layout)
        layout.addWidget(ftp_group)
        
        rep_group = QGroupBox("Parámetros del Reporte")
        rep_layout = QFormLayout()
        
        # ✅ SE RESPETA TU VARIABLE report_type_combo
        self.report_type_combo = QComboBox()
        self.report_type_combo.addItems(["Medidor", "SistemaMedicion"])
        rep_layout.addRow("Formato:", self.report_type_combo)
        
        # ✅ SE RECUPERÓ TU VARIABLE clave_conagua
        self.clave_conagua = QLineEdit()
        self.clave_conagua.setPlaceholderText("Ej: AB123")
        rep_layout.addRow("Clave Unidad de Inspección:", self.clave_conagua)
        
        # ✅ SE RECUPERÓ TU VARIABLE retry_checkbox
        self.retry_checkbox = QCheckBox("Reintentar lecturas automáticamente")
        self.retry_checkbox.setChecked(True)
        rep_layout.addRow("", self.retry_checkbox)
        
        rep_group.setLayout(rep_layout)
        layout.addWidget(rep_group)
        
        # ✅ SE RECUPERARON TUS VARIABLES DE VISTA PREVIA
        self.filename_label = QLabel()
        self.filename_label.setStyleSheet("color: #4fc3f7; font-weight: bold;")
        layout.addWidget(self.filename_label)
        
        self.content_text = QTextEdit()
        self.content_text.setReadOnly(True)
        self.content_text.setMinimumHeight(150)
        self.content_text.setFont(QFont("Courier New", 10))
        layout.addWidget(self.content_text)
        
        btn_layout = QGridLayout()
        btn_layout.setSpacing(10)
        
        preview_btn = QPushButton("🔍 Generar reporte Unidad de Inspección")
        preview_btn.setMinimumHeight(45)
        preview_btn.clicked.connect(self.generate_report)
        
        self.clear_btn = QPushButton("🗑️ Limpiar")
        self.clear_btn.setMinimumHeight(45)
        self.clear_btn.setEnabled(False)
        self.clear_btn.clicked.connect(self.clear_report)
        
        self.send_btn = QPushButton("📤 Enviar Reporte")
        self.send_btn.setMinimumHeight(45)
        self.send_btn.setEnabled(False)
        self.send_btn.setStyleSheet("background-color: #2E86C1; color: white; font-weight: bold;")
        self.send_btn.clicked.connect(self.send_report)
        
        self.btn_cambiar_nip = QPushButton("🔑 Cambiar NIP")
        self.btn_cambiar_nip.setMinimumHeight(45)
        self.btn_cambiar_nip.clicked.connect(self.cambiar_nip)
        
        # Inyectar botones en la cuadrícula (Fila, Columna)
        btn_layout.addWidget(preview_btn, 0, 0)         # Arriba izquierda
        btn_layout.addWidget(self.clear_btn, 0, 1)      # Arriba derecha
        btn_layout.addWidget(self.send_btn, 1, 0)       # Abajo izquierda
        btn_layout.addWidget(self.btn_cambiar_nip, 1, 1)# Abajo derecha
        
        # ✅ Aseguramos que se añada UNA SOLA VEZ al layout principal
        layout.addLayout(btn_layout)
        
        # ==========================================================
        # CIERRE DEL SCROLLAREA
        # ==========================================================
        content_widget.setLayout(layout)
        scroll.setWidget(content_widget)
        window_layout.addWidget(scroll)
        
        self.setLayout(window_layout)
        
    
    def cambiar_nip(self):
        """Permite cambiar el NIP de Unidad de Inspección usando NIP Teseracto"""
        dialog = AccesoDialog(self, es_cambio_nip=True)
        if dialog.exec_() == QDialog.Accepted:
            # Ahora mostrar diálogo para nuevo NIP
            self.configurar_nuevo_nip_unidad_inspeccion()

    def configurar_nuevo_nip_unidad_inspeccion(self):
        """Configura un nuevo NIP de Unidad de Inspección con mejor diseño"""
        nuevo_nip, ok = QInputDialog.getText(
            self, "Nuevo NIP de Unidad de Inspección",
            "Ingrese el nuevo NIP de Unidad de Inspección (4 dígitos):", QLineEdit.Password, "")
        
        if not ok: return
        if len(nuevo_nip) != 4 or not nuevo_nip.isdigit():
            QMessageBox.warning(self, "NIP Inválido", "El NIP debe tener exactamente 4 dígitos.")
            return
            
        confirmar_nip, ok = QInputDialog.getText(
            self, "Confirmar Nuevo NIP",
            "Confirme el nuevo NIP de Unidad de Inspección:", QLineEdit.Password, "")
            
        if not ok: return
        if nuevo_nip != confirmar_nip:
            QMessageBox.warning(self, "NIP No Coincide", "Los NIPs no coinciden. Intente nuevamente.")
            return
            
        ConfigManager.guardar_nip_ventana("FTPConaguaWindow", "nip_unidad_inspeccion", nuevo_nip)
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("✅ NIP Actualizado")
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setText("NIP de Unidad de Inspección actualizado exitosamente")
        msg_box.setInformativeText("Nuevo NIP configurado: ••••\n\n⚠️ IMPORTANTE:\n• Guarde este NIP en un lugar seguro\n• Compártalo solo con personal autorizado\n• El próximo acceso requerirá este NIP")
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()
    

    def apply_dark_theme(self):
        dark_theme = """
            QWidget { background-color: #2b2b2b; color: #cccccc; font-family: Segoe UI; }
            QLabel { color: #cccccc; padding: 2px; }
            QComboBox, QLineEdit, QTextEdit { background-color: #3b3b3b; color: white; border: 1px solid #555555; border-radius: 3px; padding: 5px; }
            QPushButton { background-color: #5a5a5a; color: white; border: 1px solid #555555; border-radius: 3px; padding: 5px 10px; }
            QPushButton:hover { background-color: #666666; border: 1px solid #777777; }
            QPushButton:disabled { background-color: #3b3b3b; color: #777777; }
            QGroupBox { color: #cccccc; border: 1px solid #444444; border-radius: 5px; margin-top: 1ex; padding-top: 10px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """
        self.setStyleSheet(dark_theme)

    # ============================================================================
    # TUS MÉTODOS ORIGINALES INTACTOS
    # ============================================================================

    def load_ftp_config(self):
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
        if len(clave) != 5: return False
        if not clave[:2].isalpha(): return False
        if not clave[2:].isdigit(): return False
        return True

    def format_conagua_report(self, tipo_reporte: str, ker_code: str, clave: str, flujo_inst: float = 0.0, flujo_acum: float = 0.0) -> str:
        try:
            config = ConfigManager.cargar_config_general()
            now = datetime.now()
            fecha = now.strftime("%Y%m%d")
            hora = now.strftime("%H%M%S")
            ker_code_str = str(ker_code).zfill(3)
            
            if tipo_reporte == "Medidor":
                return f"M|{fecha}|{hora}|{config['RFC']}|{config['NSM']}|{config['NSUT']}|{config['Lat']}|{config['Long']}|{ker_code_str}|{clave}"
            elif tipo_reporte == "SistemaMedicion":
                return f"QA|{fecha}|{hora}|{config['RFC']}|{config['NSUT']}|{flujo_inst:.3f}|{flujo_acum:.3f}|{config['Lat']}|{config['Long']}|{ker_code_str}|{clave}"
            else:
                raise ValueError("Tipo de reporte inválido")
        except Exception as e:
            self.error_handler.log_error("304", f"Fallo al formatear reporte Conagua: {e}", es_error_sistema=True)
            return f"ERR|{datetime.now().strftime('%Y%m%d|%H%M%S')}|{type(e).__name__}|{str(e)}|{str(ker_code).zfill(3)}|{clave}"

    def generate_conagua_filename(self, tipo_reporte: str, clave: str) -> str:
        try:
            config_provider = ConfigProvider(ConfigManager())
            name_gen = FileNameGenerator(config_provider)
            base_name = name_gen.generate_daily_name(tipo_reporte)
            
            if base_name.endswith('.txt'):
                return f"{base_name[:-4]}_{clave}.txt"
            return f"{base_name}_{clave}.txt"
        except Exception as e:
            self.error_handler.log_error("305", f"Fallo generando nombre para archivo Conagua: {e}", es_error_sistema=True)
            return f"reporte_conagua_{datetime.now().strftime('%Y%m%d')}_{clave}.txt"

    def mostrar_progreso(self, mensaje: str):
        if not self._progress_label:
            self._progress_label = QLabel(mensaje, self)
            self._progress_label.setAlignment(Qt.AlignCenter)
            self._progress_label.setStyleSheet("color: #FFA500; font-weight: bold;")
            self.layout().insertWidget(1, self._progress_label)
        else:
            self._progress_label.setText(mensaje)
        QApplication.processEvents()

    def ocultar_progreso(self):
        if self._progress_label:
            self._progress_label.hide()
            self._progress_label = None
        QApplication.processEvents()

    def obtener_lecturas_confiables(self, medidor, max_intentos=3, delay_entre_intentos=1.0):
        intentos = 0
        mejores_lecturas = (0.0, 0.0)
        ultimo_error = ""
        hacer_reintentos = self.retry_checkbox.isChecked()
        if not hacer_reintentos: max_intentos = 1
        
        for intento in range(max_intentos):
            intentos += 1
            try:
                if intento > 0: self.mostrar_progreso(f"Intento {intento+1}/{max_intentos}...")
                datos_crudos = medidor.leer_registros()
                
                if datos_crudos:
                    datos_procesados = self.data_processor.process(datos_crudos, medidor.perfil)
                    flujo_inst = datos_procesados.get("flujo_instantaneo", 0.0)
                    flujo_acum = datos_procesados.get("flujo_acumulado", 0.0)
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
        if ultimo_error: mensaje += f" ({ultimo_error})"
        return mejores_lecturas[0], mejores_lecturas[1], intentos, mensaje

    def generate_report(self):
        clave = self.clave_conagua.text().strip()
        if not self.validate_clave(clave):
            QMessageBox.warning(self, "Clave inválida", "La clave no coincide con ningún formato de Unidad de Inspección.")
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
            respuesta = QMessageBox.question(self, "Advertencia - Lecturas en 0.0",
                "Las lecturas son 0.0 después de múltiples intentos.\n\n¿Desea continuar con valores 0.0?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
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
            QMessageBox.warning(self, "Error", f"Error al formatear el reporte: {str(e)}")
            return

        self.filename_label.setText(filename)
        self.content_text.setPlainText(contenido)
        self.clear_btn.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.current_content = contenido
        self.current_filename = filename
        self.ocultar_progreso()

    def clear_report(self):
        self.filename_label.setText("")
        self.content_text.setPlainText("")
        self.current_content = None
        self.current_filename = None
        self.clear_btn.setEnabled(False)
        self.send_btn.setEnabled(False)

    def send_report(self):
        if not self.current_content or not self.current_filename:
            QMessageBox.warning(self, "Error", "No hay reporte generado para enviar.")
            return

        host = self.ftp_host.text().strip()
        port = self.ftp_port.text().strip()
        user = self.ftp_user.text().strip()
        password = self.ftp_password.text().strip()
        remote_path = self.ftp_remote_path.text().strip()

        if not host or not user or not password:
            QMessageBox.warning(self, "Error", "Complete los campos obligatorios del FTP (servidor, usuario y contraseña).")
            return

        temp_path = os.path.join(os.getcwd(), self.current_filename)
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(self.current_content)
        except Exception as e:
            self.error_handler.log_error("305", f"No se pudo crear archivo temporal FTP: {e}", es_error_sistema=True)
            QMessageBox.warning(self, "Error", f"No se pudo crear el archivo temporal: {str(e)}")
            return

        try:
            ftp_config = {
                "host": host,
                "usuario": user,
                "clave": password,
                "puerto": int(port) if port else 21,
                "ruta_remota": remote_path
            }
            ftp_manager = FTPManager(ftp_config, self.error_handler)
            remote_filename = os.path.join(remote_path, self.current_filename) if remote_path else self.current_filename
            
            success, server_msg = ftp_manager.enviar_archivo(temp_path, remote_filename)
            
            if success:
                QMessageBox.information(self, "Éxito", f"Reporte enviado correctamente.\nRespuesta: {server_msg}")
                self.error_handler.log_evento("Reporte Unidad de Inspección enviado con éxito", "200")
            else:
                QMessageBox.warning(self, "Error de Envío", f"No se pudo enviar el reporte.\nRazón: {server_msg}")
                
        except Exception as e:
            self.error_handler.log_error("FTP-UPLOAD", f"Excepción crítica al enviar reporte: {e}", es_error_sistema=True)
            QMessageBox.warning(self, "Error", f"Error al enviar el reporte: {str(e)}")
        finally:
            try:
                os.remove(temp_path)
            except: pass
            self.ocultar_progreso()