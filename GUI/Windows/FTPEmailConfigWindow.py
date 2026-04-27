# TESERACTO-UTR/GUI/Windows/FTPEmailConfigWindow.py
# VERSIÓN SIMPLIFICADA - 100% FUNCIONAL

import json
import os
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, QLineEdit,
    QPushButton, QTimeEdit, QCheckBox, QLabel, QMessageBox,
    QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QTextEdit, QSplitter, QApplication, QProgressDialog
)
from PyQt5.QtCore import QTime, Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QBrush

from Core.Network.FTPManager import FTPManager
from Core.System.ErrorHandler import ErrorHandler
from Core.System.StateManager import StateManager
from Core.System.PathManager import path_manager

class WorkerActualizacion(QThread):
    """Worker para actualizaciones en segundo plano"""
    estado_obtenido = pyqtSignal(dict)
    archivos_obtenidos = pyqtSignal(list)
    
    def __init__(self, file_scheduler):
        super().__init__()
        self.file_scheduler = file_scheduler
    
    def run(self):
        try:
            estado = self.file_scheduler.obtener_estado()
            self.estado_obtenido.emit(estado)
            
            archivos = self.file_scheduler.obtener_detalle_archivos_pendientes()
            self.archivos_obtenidos.emit(archivos)
            
        except Exception as e:
            print(f"Error en worker: {e}")

class WorkerEnvioManual(QThread):
    """Worker para enviar archivos manualmente sin congelar la interfaz gráfica"""
    resultado_obtenido = pyqtSignal(dict)
    
    def __init__(self, file_scheduler):
        super().__init__()
        self.file_scheduler = file_scheduler
    
    def run(self):
        try:
            # Ejecuta la función real de envío y emite el resultado a la UI
            resultado = self.file_scheduler.forzar_envio_inmediato()
            self.resultado_obtenido.emit(resultado)
        except Exception as e:
            self.resultado_obtenido.emit({
                "exitosos": 0, "fallidos": 0, "total": 0, 
                "mensaje": f"Fallo en hilo de ejecución: {str(e)}"
            })

class FTPEmailConfigWindow(QWidget):
    """Ventana de configuración FTP/Email - VERSIÓN SIMPLIFICADA"""
    
    def __init__(self, file_scheduler, error_handler: ErrorHandler):
        super().__init__()
        self.file_scheduler = file_scheduler
        self.error_handler = error_handler
        self.progress_dialog = None
        
        self.setWindowTitle("🚀 Configuración FTP/Email - Sistema Automático")
        self.setMinimumSize(1000, 800)
        
        # Configurar UI
        self._setup_ui()
        self._setup_conexiones()
        
        # Cargar configuración
        self._cargar_configuracion()
        
        # Iniciar monitoreo
        self._iniciar_monitoreo()
        
        # Estado inicial
        self._actualizar_estado_ui()
    
    # ========== MÉTODOS PRIVADOS DE UI (IGUALES A LOS TUYOS) ==========
    
    def _setup_ui(self):
        """Configura la interfaz de usuario"""
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(15, 15, 15, 15)
        layout_principal.setSpacing(10)
        
        # Panel de estado
        panel_estado = QGroupBox("📊 ESTADO DEL SISTEMA AUTOMÁTICO")
        panel_estado.setFont(QFont("Arial", 10, QFont.Bold))
        layout_estado = QHBoxLayout()
        
        self.lbl_estado_scheduler = QLabel("🔄 Iniciando...")
        self.lbl_estado_scheduler.setFont(QFont("Arial", 11, QFont.Bold))
        self.lbl_hora_programada = QLabel("Hora: --:--")
        self.lbl_proxima_ejecucion = QLabel("Próxima: --:--")
        self.lbl_ultimo_exito = QLabel("Último éxito: Nunca")
        self.lbl_archivos_pendientes = QLabel("Pendientes: 0")
        
        for lbl in [self.lbl_hora_programada, self.lbl_proxima_ejecucion, 
                    self.lbl_ultimo_exito, self.lbl_archivos_pendientes]:
            lbl.setFont(QFont("Arial", 9))
        
        layout_estado.addWidget(self.lbl_estado_scheduler, 2)
        layout_estado.addWidget(self.lbl_hora_programada, 1)
        layout_estado.addWidget(self.lbl_proxima_ejecucion, 1)
        layout_estado.addWidget(self.lbl_ultimo_exito, 1)
        layout_estado.addWidget(self.lbl_archivos_pendientes, 1)
        panel_estado.setLayout(layout_estado)
        layout_principal.addWidget(panel_estado)
        
        # Tabs principales
        self.tabs = QTabWidget()
        
        # Tab 1: Configuración
        tab_config = self._crear_tab_configuracion()
        # Tab 2: Monitoreo
        tab_monitor = self._crear_tab_monitoreo()
        # Tab 3: Logs
        tab_logs = self._crear_tab_logs()
        
        self.tabs.addTab(tab_config, "⚙️ CONFIGURACIÓN")
        self.tabs.addTab(tab_monitor, "📈 MONITOREO")
        self.tabs.addTab(tab_logs, "📝 REGISTROS")
        
        layout_principal.addWidget(self.tabs, 1)
        
        # Barra de acciones
        barra_acciones = QHBoxLayout()
        
        self.btn_guardar = QPushButton("💾 GUARDAR CONFIGURACIÓN")
        self.btn_guardar.setFont(QFont("Arial", 10, QFont.Bold))
        self.btn_guardar.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.btn_guardar.clicked.connect(self.guardar_configuracion)
        
        self.btn_probar_ftp = QPushButton("🔍 PROBAR FTP")
        self.btn_probar_ftp.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px;
                border-radius: 5px;
            }
        """)
        self.btn_probar_ftp.clicked.connect(self._probar_conexion_ftp_safe)
        
        self.btn_probar_email = QPushButton("📧 PROBAR EMAIL")
        self.btn_probar_email.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 8px;
                border-radius: 5px;
            }
        """)
        self.btn_probar_email.clicked.connect(self._probar_email_safe)
        
        self.btn_forzar_envio = QPushButton("⚡ ENVÍO INMEDIATO")
        self.btn_forzar_envio.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                padding: 8px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #7B1FA2; }
        """)
        self.btn_forzar_envio.clicked.connect(self._forzar_envio_inmediato_safe)
        self.btn_forzar_envio.setToolTip("Envía TODOS los archivos pendientes ahora mismo")
        
        barra_acciones.addWidget(self.btn_guardar, 2)
        barra_acciones.addWidget(self.btn_probar_ftp, 1)
        barra_acciones.addWidget(self.btn_probar_email, 1)
        barra_acciones.addWidget(self.btn_forzar_envio, 1)
        
        layout_principal.addLayout(barra_acciones)
    
    def _crear_tab_configuracion(self):
        """Crea tab de configuración (IGUAL A TU VERSIÓN)"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        splitter = QSplitter(Qt.Horizontal)
        
        # Panel FTP
        panel_ftp = QGroupBox("🔌 CONFIGURACIÓN FTP")
        layout_ftp = QFormLayout()
        self.txt_host = QLineEdit()
        self.txt_host.setPlaceholderText("medidores.conagua.gob.mx")
        self.txt_usuario = QLineEdit()
        self.txt_usuario.setPlaceholderText("prueba18")
        self.txt_clave = QLineEdit()
        self.txt_clave.setEchoMode(QLineEdit.Password)
        self.txt_clave.setPlaceholderText("Contraseña FTP")
        self.txt_ruta_remota = QLineEdit()
        self.txt_ruta_remota.setPlaceholderText("/Prueba/")
        
        layout_ftp.addRow("Servidor FTP:", self.txt_host)
        layout_ftp.addRow("Usuario:", self.txt_usuario)
        layout_ftp.addRow("Contraseña:", self.txt_clave)
        layout_ftp.addRow("Ruta Remota:", self.txt_ruta_remota)
        panel_ftp.setLayout(layout_ftp)
        
        # Panel Email
        panel_email = QGroupBox("📧 CONFIGURACIÓN EMAIL")
        layout_email = QFormLayout()
        self.txt_smtp = QLineEdit()
        self.txt_smtp.setPlaceholderText("smtp.gmail.com")
        self.txt_puerto = QLineEdit()
        self.txt_puerto.setPlaceholderText("587")
        self.txt_remitente = QLineEdit()
        self.txt_remitente.setPlaceholderText("teseractohgf@gmail.com")
        self.txt_destinatarios = QLineEdit()
        self.txt_destinatarios.setPlaceholderText("email1@gmail.com, email2@gmail.com")
        self.txt_asunto = QLineEdit()
        self.txt_asunto.setPlaceholderText("Reporte Diario Tesseract UTR")
        self.txt_usuario_smtp = QLineEdit()
        self.txt_usuario_smtp.setPlaceholderText("Usuario SMTP")
        self.txt_clave_smtp = QLineEdit()
        self.txt_clave_smtp.setEchoMode(QLineEdit.Password)
        self.txt_clave_smtp.setPlaceholderText("Contraseña SMTP")
        
        layout_email.addRow("Servidor SMTP:", self.txt_smtp)
        layout_email.addRow("Puerto:", self.txt_puerto)
        layout_email.addRow("Remitente:", self.txt_remitente)
        layout_email.addRow("Destinatarios:", self.txt_destinatarios)
        layout_email.addRow("Asunto:", self.txt_asunto)
        layout_email.addRow("Usuario SMTP:", self.txt_usuario_smtp)
        layout_email.addRow("Contraseña SMTP:", self.txt_clave_smtp)
        panel_email.setLayout(layout_email)
        
        splitter.addWidget(panel_ftp)
        splitter.addWidget(panel_email)
        layout.addWidget(splitter, 1)
        
        # Panel programación
        panel_prog = QGroupBox("⏰ PROGRAMACIÓN AUTOMÁTICA")
        layout_prog = QFormLayout()
        self.time_envio = QTimeEdit()
        self.time_envio.setDisplayFormat("HH:mm")
        self.time_envio.setTime(QTime(23, 59))
        self.chk_habilitado = QCheckBox("HABILITAR ENVÍO AUTOMÁTICO DIARIO")
        self.chk_habilitado.setChecked(True)
        self.chk_habilitado.setFont(QFont("Arial", 9, QFont.Bold))
        
        layout_prog.addRow("Hora de envío automático:", self.time_envio)
        layout_prog.addRow(self.chk_habilitado)
        
        info_label = QLabel(
            "💡 El sistema enviará automáticamente todos los reportes a la hora programada.\n"
            "Archivos pendientes por fallos previos se incluirán en el próximo ciclo automático."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        layout_prog.addRow(info_label)
        panel_prog.setLayout(layout_prog)
        layout.addWidget(panel_prog)
        
        return tab
    
    def _crear_tab_monitoreo(self):
        """Crea tab de monitoreo (IGUAL A TU VERSIÓN)"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        panel_detalle = QGroupBox("📈 ESTADO DETALLADO")
        layout_detalle = QFormLayout()
        self.lbl_detalle_estado = QLabel("--")
        self.lbl_detalle_hora = QLabel("--")
        self.lbl_detalle_proxima = QLabel("--")
        self.lbl_detalle_ultimo = QLabel("--")
        self.lbl_detalle_pendientes = QLabel("--")
        self.lbl_detalle_fallidos = QLabel("--")
        self.lbl_detalle_fallos_consec = QLabel("--")
        
        layout_detalle.addRow("Estado:", self.lbl_detalle_estado)
        layout_detalle.addRow("Hora programada:", self.lbl_detalle_hora)
        layout_detalle.addRow("Próxima ejecución:", self.lbl_detalle_proxima)
        layout_detalle.addRow("Último éxito:", self.lbl_detalle_ultimo)
        layout_detalle.addRow("Archivos pendientes:", self.lbl_detalle_pendientes)
        layout_detalle.addRow("Emails fallidos:", self.lbl_detalle_fallidos)
        layout_detalle.addRow("Fallos consecutivos:", self.lbl_detalle_fallos_consec)
        panel_detalle.setLayout(layout_detalle)
        layout.addWidget(panel_detalle)
        
        panel_tabla = QGroupBox("📂 ARCHIVOS PENDIENTES")
        layout_tabla = QVBoxLayout()
        self.tabla_archivos = QTableWidget()
        self.tabla_archivos.setColumnCount(6)
        self.tabla_archivos.setHorizontalHeaderLabels([
            "ARCHIVO", "TAMAÑO", "MODIFICADO", "ANTIGÜEDÁD", "ESTADO", "PRIORIDAD"
        ])
        
        header = self.tabla_archivos.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        
        self.tabla_archivos.setAlternatingRowColors(True)
        self.tabla_archivos.setSortingEnabled(True)
        layout_tabla.addWidget(self.tabla_archivos)
        panel_tabla.setLayout(layout_tabla)
        layout.addWidget(panel_tabla, 1)
        
        return tab
    
    def _crear_tab_logs(self):
        """Crea tab de logs (IGUAL A TU VERSIÓN)"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setFont(QFont("Courier New", 9))
        layout.addWidget(self.txt_logs)
        return tab
    
    def _setup_conexiones(self):
        """Configura conexiones internas"""
        self.timer_monitoreo = QTimer()
        self.timer_monitoreo.timeout.connect(self._actualizar_estado_ui)
        
        self.worker = WorkerActualizacion(self.file_scheduler)
        self.worker.estado_obtenido.connect(self._procesar_estado_actualizado)
        self.worker.archivos_obtenidos.connect(self._procesar_archivos_actualizados)
    
    def _cargar_configuracion(self):
        """Carga configuración desde archivos"""
        try:
            # Cargar FTP
            ftp_config_path = path_manager.get_config_path("ftp_config.json")
            if ftp_config_path.exists():
                with open(ftp_config_path, 'r', encoding='utf-8') as f:
                    ftp_config = json.load(f)
                
                self.txt_host.setText(ftp_config.get('host', ''))
                self.txt_usuario.setText(ftp_config.get('usuario', ''))
                self.txt_clave.setText(ftp_config.get('clave', ''))
                self.txt_ruta_remota.setText(ftp_config.get('ruta_remota', ''))
                
                if 'hora_envio' in ftp_config:
                    try:
                        hora, minuto = map(int, ftp_config['hora_envio'].split(':'))
                        self.time_envio.setTime(QTime(hora, minuto))
                    except:
                        pass
            
            # Cargar Email
            email_config_path = path_manager.get_config_path("email_config.json")
            if email_config_path.exists():
                with open(email_config_path, 'r', encoding='utf-8') as f:
                    email_config = json.load(f)
                
                self.txt_smtp.setText(email_config.get('smtp_server', ''))
                self.txt_puerto.setText(str(email_config.get('smtp_port', 587)))
                self.txt_remitente.setText(email_config.get('from', ''))
                self.txt_destinatarios.setText(','.join(email_config.get('to', [])))
                self.txt_asunto.setText(email_config.get('subject', ''))
                self.txt_usuario_smtp.setText(email_config.get('username', ''))
                self.txt_clave_smtp.setText(email_config.get('password', ''))
                
        except Exception as e:
            self.error_handler.log_error("CONFIG-LOAD", f"Error cargando configuración: {e}")
            self._agregar_log(f"❌ Error cargando configuración: {e}")
    
    def _iniciar_monitoreo(self):
        """Inicia monitoreo automático"""
        self.timer_monitoreo.start(10000)
    
    def _actualizar_estado_ui(self):
        """Actualiza estado de UI"""
        if not self.worker.isRunning():
            self.worker.start()
    
    def _procesar_estado_actualizado(self, estado):
        """Procesa estado actualizado del scheduler"""
        try:
            if estado.get("activo"):
                self.lbl_estado_scheduler.setText("✅ SCHEDULER ACTIVO")
                self.lbl_estado_scheduler.setStyleSheet("color: green;")
            else:
                self.lbl_estado_scheduler.setText("❌ SCHEDULER INACTIVO")
                self.lbl_estado_scheduler.setStyleSheet("color: red;")
            
            self.lbl_hora_programada.setText(f"Hora: {estado.get('hora_programada', '--:--')}")
            self.lbl_proxima_ejecucion.setText(f"Próxima: {estado.get('proxima_ejecucion', '--:--')}")
            self.lbl_ultimo_exito.setText(f"Último éxito: {estado.get('ultimo_exito', 'Nunca')}")
            self.lbl_archivos_pendientes.setText(f"Pendientes: {estado.get('archivos_pendientes', 0)}")
            
            self.lbl_detalle_estado.setText("ACTIVO" if estado.get("activo") else "INACTIVO")
            self.lbl_detalle_hora.setText(estado.get("hora_programada", "--:--"))
            self.lbl_detalle_proxima.setText(estado.get("proxima_ejecucion", "--:--"))
            self.lbl_detalle_ultimo.setText(estado.get("ultimo_exito", "Nunca"))
            self.lbl_detalle_pendientes.setText(str(estado.get("archivos_pendientes", 0)))
            self.lbl_detalle_fallidos.setText(str(estado.get("archivos_fallidos_email", 0)))
            self.lbl_detalle_fallos_consec.setText(str(estado.get("fallos_consecutivos", 0)))
            
            if estado.get("activo"):
                self._agregar_log(f"🔄 Scheduler activo - Próximo: {estado.get('proxima_ejecucion', '--:--')}")
                
        except Exception as e:
            # APORTACIÓN 1: Código oficial "010"
            self.error_handler.log_error("010", f"Error actualizando estado UI del scheduler: {e}", es_error_sistema=True)
    
    def _procesar_archivos_actualizados(self, archivos):
        """Procesa lista actualizada de archivos"""
        try:
            self.tabla_archivos.setRowCount(len(archivos))
            
            for i, archivo in enumerate(archivos):
                item_nombre = QTableWidgetItem(archivo["nombre"])
                item_tamano = QTableWidgetItem(f"{archivo['tamano_kb']} KB")
                item_modificado = QTableWidgetItem(archivo["modificado"])
                
                antiguedad = archivo["antiguedad_dias"]
                item_antiguedad = QTableWidgetItem(f"{antiguedad} días")
                
                if antiguedad >= 3:
                    item_antiguedad.setForeground(QBrush(QColor(255, 0, 0)))
                    item_nombre.setForeground(QBrush(QColor(255, 0, 0)))
                elif antiguedad >= 1:
                    item_antiguedad.setForeground(QBrush(QColor(255, 165, 0)))
                    item_nombre.setForeground(QBrush(QColor(255, 165, 0)))
                
                estado = archivo["estado"]
                item_estado = QTableWidgetItem(estado)
                if estado == "email_pendiente":
                    item_estado.setForeground(QBrush(QColor(255, 0, 0)))
                
                item_prioridad = QTableWidgetItem(archivo["prioridad"])
                if archivo["prioridad"] == "ALTA":
                    item_prioridad.setForeground(QBrush(QColor(255, 0, 0)))
                elif archivo["prioridad"] == "MEDIA":
                    item_prioridad.setForeground(QBrush(QColor(255, 165, 0)))
                
                self.tabla_archivos.setItem(i, 0, item_nombre)
                self.tabla_archivos.setItem(i, 1, item_tamano)
                self.tabla_archivos.setItem(i, 2, item_modificado)
                self.tabla_archivos.setItem(i, 3, item_antiguedad)
                self.tabla_archivos.setItem(i, 4, item_estado)
                self.tabla_archivos.setItem(i, 5, item_prioridad)
                
        except Exception as e:
            # APORTACIÓN 1: Código oficial "010"
            self.error_handler.log_error("010", f"Error actualizando lista de archivos en UI: {e}", es_error_sistema=True)
    
    def _agregar_log(self, mensaje):
        """Agrega un mensaje al log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_logs.append(f"[{timestamp}] {mensaje}")
        
        lines = self.txt_logs.toPlainText().split('\n')
        if len(lines) > 1000:
            self.txt_logs.setPlainText('\n'.join(lines[-1000:]))
    
    # ========== MÉTODOS CORREGIDOS PARA EVITAR CONGELAMIENTO ==========
    
    def _probar_conexion_ftp_safe(self):
        """Prueba conexión FTP SIN bloquear UI (versión corregida)"""
        self.btn_probar_ftp.setEnabled(False)
        self.btn_probar_ftp.setText("Probando...")
        
        # Configuración
        ftp_config = {
            "host": self.txt_host.text().strip(),
            "usuario": self.txt_usuario.text().strip(),
            "clave": self.txt_clave.text(),
            "ruta_remota": self.txt_ruta_remota.text().strip() or "/",
            "timeout": 15,
            "secure": False
        }
        
        # Función que se ejecutará en hilo separado
        def test_ftp():
            try:
                ftp_manager = FTPManager(ftp_config, self.error_handler)
                success = ftp_manager.verificar_conexion()
                return success, "Conexión FTP establecida correctamente." if success else "No se pudo establecer conexión FTP."
            except Exception as e:
                return False, f"Error en prueba: {str(e)}"
        
        # Usar QTimer para ejecutar en hilo separado
        from PyQt5.QtCore import QTimer
        def execute_test():
            try:
                success, message = test_ftp()
                
                # Restaurar botón
                self.btn_probar_ftp.setEnabled(True)
                self.btn_probar_ftp.setText("🔍 PROBAR FTP")
                
                # Mostrar resultado
                if success:
                    self._agregar_log("✅ Prueba FTP exitosa")
                    QMessageBox.information(self, "✅ Éxito", message)
                else:
                    self._agregar_log("❌ Prueba FTP fallida")
                    QMessageBox.warning(self, "❌ Fallo", message)
                    # APORTACIÓN 2: Notificar fallo al centro de mensajes
                    self.error_handler.log_error("FTP-TEST", f"Prueba FTP fallida: {message}", es_error_sistema=True)
                    
            except Exception as e:
                self.btn_probar_ftp.setEnabled(True)
                self.btn_probar_ftp.setText("🔍 PROBAR FTP")
                self._agregar_log(f"❌ Error prueba FTP: {e}")
                # APORTACIÓN 2: Notificar excepción
                self.error_handler.log_error("FTP-TEST", f"Excepción durante prueba FTP: {e}", es_error_sistema=True)
        
        # Ejecutar después de 100ms para no bloquear UI
        QTimer.singleShot(100, execute_test)
    
    def _probar_email_safe(self):
        """Prueba envío de email SIN bloquear UI (versión corregida)"""
        # Validar campos
        if not all([
            self.txt_smtp.text().strip(),
            self.txt_puerto.text().strip(),
            self.txt_remitente.text().strip(),
            self.txt_destinatarios.text().strip()
        ]):
            QMessageBox.warning(self, "Validación", "Complete los campos obligatorios del email")
            return
        
        self.btn_probar_email.setEnabled(False)
        self.btn_probar_email.setText("Enviando...")
        
        # Función que se ejecutará en hilo separado
        def test_email():
            try:
                msg = MIMEMultipart()
                msg['From'] = self.txt_remitente.text().strip()
                msg['To'] = self.txt_destinatarios.text().strip()
                msg['Subject'] = "Prueba - Sistema Tesseract UTR"
                
                cuerpo = f"Prueba de configuración SMTP\nEnviado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                msg.attach(MIMEText(cuerpo, 'plain'))
                
                server = smtplib.SMTP(
                    self.txt_smtp.text().strip(), 
                    int(self.txt_puerto.text())
                )
                server.starttls()
                
                if self.txt_usuario_smtp.text().strip():
                    server.login(
                        self.txt_usuario_smtp.text().strip(),
                        self.txt_clave_smtp.text()
                    )
                
                server.send_message(msg)
                server.quit()
                
                return True, "Correo de prueba enviado exitosamente."
                
            except Exception as e:
                return False, f"Error enviando correo:\n{str(e)}"
        
        # Usar QTimer para ejecutar en hilo separado
        from PyQt5.QtCore import QTimer
        def execute_test():
            try:
                success, message = test_email()
                
                # Restaurar botón
                self.btn_probar_email.setEnabled(True)
                self.btn_probar_email.setText("📧 PROBAR EMAIL")
                
                # Mostrar resultado
                if success:
                    self._agregar_log("✅ Prueba email exitosa")
                    QMessageBox.information(self, "✅ Éxito", message)
                else:
                    self._agregar_log("❌ Error prueba email")
                    QMessageBox.critical(self, "❌ Error", message)
                    # APORTACIÓN 2: Notificar fallo al centro de mensajes
                    self.error_handler.log_error("EMAIL-TEST", f"Prueba Email fallida: {message}", es_error_sistema=True)
                    
            except Exception as e:
                self.btn_probar_email.setEnabled(True)
                self.btn_probar_email.setText("📧 PROBAR EMAIL")
                self._agregar_log(f"❌ Error prueba email: {e}")
                # APORTACIÓN 2: Notificar excepción
                self.error_handler.log_error("EMAIL-TEST", f"Excepción durante prueba Email: {e}", es_error_sistema=True)
        
        # Ejecutar después de 100ms para no bloquear UI
        QTimer.singleShot(100, execute_test)
    
    def _forzar_envio_inmediato_safe(self):
        """Fuerza envío inmediato usando un Worker (Hilo) para no bloquear UI"""
        respuesta = QMessageBox.question(
            self,
            "⚠️ Envío Inmediato",
            "¿Está seguro de enviar TODOS los archivos pendientes AHORA?\n\n"
            "Esto ejecutará el proceso completo de envío fuera del horario programado.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if respuesta != QMessageBox.Yes:
            return
            
        try:
            # Verificamos si ya hay un envío de fondo trabajando para no empalmar
            estado_actual = self.file_scheduler.obtener_estado()
            if estado_actual.get("archivos_pendientes", 0) == 0 and estado_actual.get("archivos_fallidos_email", 0) == 0:
                QMessageBox.information(self, "Aviso", "No hay archivos pendientes para enviar.")
                return

            # Mostrar progreso visual
            self.progress_dialog = QProgressDialog(
                "Enviando archivos al servidor... Por favor espere.", 
                "Cancelar", 0, 0, self
            )
            self.progress_dialog.setWindowTitle("⚡ Procesando Envío")
            self.progress_dialog.setWindowModality(Qt.WindowModal)
            self.progress_dialog.setMinimumDuration(500)
            self.progress_dialog.setValue(0)
            self.progress_dialog.show()
            
            # Lanzamos el Worker real
            self.worker_envio = WorkerEnvioManual(self.file_scheduler)
            self.worker_envio.resultado_obtenido.connect(self._on_envio_manual_terminado)
            self.worker_envio.start()
            
        except Exception as e:
            self.error_handler.log_error("010", f"Fallo al iniciar envío inmediato: {e}", es_error_sistema=True)
            if self.progress_dialog:
                self.progress_dialog.close()
            QMessageBox.critical(self, "Error", f"Error:\n{str(e)}")

    def _on_envio_manual_terminado(self, resultado):
        """Recibe la respuesta del Worker cuando termina de enviar todo"""
        # Cerrar ventana de carga
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
            
        # Refrescar la tabla visualmente
        self._actualizar_estado_ui()
        
        mensaje = resultado.get("mensaje", "")
        exitosos = resultado.get("exitosos", 0)
        fallidos = resultado.get("fallidos", 0)
        
        if exitosos > 0:
            QMessageBox.information(self, "✅ Envío Finalizado", 
                f"Reportes transferidos con éxito: {exitosos}\n"
                f"Reportes fallidos en cola: {fallidos}\n\n"
                f"Revise la pestaña de REGISTROS.")
            self.error_handler.log_evento("Reporte enviado manualmente con éxito", "200")
        elif fallidos > 0:
            QMessageBox.warning(self, "⚠️ Envío Fallido", 
                f"No se pudo enviar los archivos ({fallidos} siguen pendientes).\n"
                f"Revise su conexión a internet o los logs de error.")
        else:
            QMessageBox.information(self, "Información", mensaje)
    
    # ========== MÉTODOS EXISTENTES QUE FUNCIONAN BIEN ==========
    
    def guardar_configuracion(self):
        """Guarda configuración y actualiza todos los servicios en ejecución"""
        try:
            # Validación
            if not self.txt_host.text().strip():
                QMessageBox.warning(self, "Validación", "El servidor FTP es obligatorio")
                return
            
            hora = self.time_envio.time()
            hora_str = f"{hora.hour():02d}:{hora.minute():02d}"
            
            # Configuración FTP
            ftp_config = {
                "host": self.txt_host.text().strip(),
                "usuario": self.txt_usuario.text().strip(),
                "clave": self.txt_clave.text(),
                "ruta_remota": self.txt_ruta_remota.text().strip(),
                "hora_envio": hora_str,
                "timeout": 60,
                "secure": False,
                "puerto": 21
            }
            
            # Configuración Email
            email_config = None
            if self.txt_smtp.text().strip():
                email_config = {
                    "smtp_server": self.txt_smtp.text().strip(),
                    "smtp_port": int(self.txt_puerto.text() or 587),
                    "from": self.txt_remitente.text().strip(),
                    "to": [t.strip() for t in self.txt_destinatarios.text().split(',') if t.strip()],
                    "subject": self.txt_asunto.text().strip() or "Reporte Tesseract UTR",
                    "username": self.txt_usuario_smtp.text().strip(),
                    "password": self.txt_clave_smtp.text()
                }
            
            # ✅ USAR ConfigManager PARA GUARDAR (COHERENCIA)
            from Core.System.ConfigManager import ConfigManager
            ConfigManager.guardar_config_ftp(ftp_config)
            if email_config:
                ConfigManager.guardar_config_email(email_config)
            
            # ✅ ACTUALIZAR FTPManager EN TIEMPO DE EJECUCIÓN
            if hasattr(self.file_scheduler.transfer_service, 'actualizar_configuracion'):
                self.file_scheduler.transfer_service.actualizar_configuracion(ftp_config)
            
            # ✅ ACTUALIZAR CONFIGURACIÓN EMAIL EN FileScheduler
            if email_config and hasattr(self.file_scheduler, '_actualizar_config_email'):
                self.file_scheduler._actualizar_config_email(email_config)
            
            # ✅ ACTUALIZAR HORA DE ENVÍO
            if hasattr(self.file_scheduler, 'actualizar_hora_envio'):
                self.file_scheduler.actualizar_hora_envio(hora_str)
            
            # ✅ REINICIAR SCHEDULER SI ESTÁ HABILITADO
            if self.chk_habilitado.isChecked():
                if hasattr(self.file_scheduler, 'detener'):
                    self.file_scheduler.detener()
                time.sleep(1)
                if hasattr(self.file_scheduler, 'iniciar'):
                    self.file_scheduler.iniciar()
            
            StateManager.set_ready("ftp_email")
            
            QMessageBox.information(
                self,
                "✅ Configuración Guardada",
                f"Configuración actualizada y aplicada a todos los servicios:\n\n"
                f"• Servidor FTP: {ftp_config['host']}\n"
                f"• Hora automática: {hora_str}\n"
                f"• Destinatarios: {len(email_config['to']) if email_config else 0}\n"
                f"• Modo: {'ACTIVO' if self.chk_habilitado.isChecked() else 'INACTIVO'}"
            )
            
            self._agregar_log(f"✅ Configuración guardada y aplicada - Hora: {hora_str}")
            self._actualizar_estado_ui()
            
        except Exception as e:
            self.error_handler.log_error("CONFIG-SAVE", f"Error guardando: {e}")
            QMessageBox.critical(self, "❌ Error", f"Error al guardar:\n{str(e)}")
            self._agregar_log(f"❌ Error guardando: {e}")
    
    def closeEvent(self, event):
        """Maneja cierre de ventana"""
        if hasattr(self, 'timer_monitoreo'):
            self.timer_monitoreo.stop()
        
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait(1000)
        
        super().closeEvent(event)