# TESERACTO-UTR/GUI/Windows/FTPEmailConfigWindow.py

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
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QTime, Qt, QTimer, pyqtSignal, QThread

from Core.Network.FTPManager import FTPManager
from Core.System.ErrorHandler import ErrorHandler
from Core.System.StateManager import StateManager
from Core.System.PathManager import path_manager
from Core.System.ConfigManager import ConfigManager

class WorkerActualizacion(QThread):
    """Worker para actualizaciones en segundo plano (Consumidor Pasivo)"""
    estado_obtenido = pyqtSignal(dict)
    archivos_obtenidos = pyqtSignal(list)
    
    def __init__(self, file_scheduler):
        super().__init__()
        self.file_scheduler = file_scheduler
    
    def run(self):
        try:
            # Consumo estricto mediante endpoints oficiales (Cero lógica duplicada)
            estado = self.file_scheduler.obtener_estado()
            self.estado_obtenido.emit(estado)
            
            archivos = self.file_scheduler.obtener_detalle_archivos_pendientes()
            self.archivos_obtenidos.emit(archivos)
            
        except Exception as e:
            import logging
            logging.error(f"Error en worker de reconstrucción pasiva UI: {e}")

class WorkerEnvioManual(QThread):
    """Worker para ejecutar forzado manual aislando la UI."""
    resultado_obtenido = pyqtSignal(dict)
    
    def __init__(self, file_scheduler):
        super().__init__()
        self.file_scheduler = file_scheduler
    
    def run(self):
        try:
            ruta_pendientes = path_manager.get_pendientes_usb_path()
            pendientes_antes = len([f for f in os.listdir(ruta_pendientes) if f.endswith('.txt')]) if os.path.exists(ruta_pendientes) else 0
            
            # Forzar ejecución invocando el método matemático interno del Orquestador de red
            if hasattr(self.file_scheduler, 'forzar_envio_inmediato'):
                self.file_scheduler.forzar_envio_inmediato()
            
            pendientes_despues = len([f for f in os.listdir(ruta_pendientes) if f.endswith('.txt')]) if os.path.exists(ruta_pendientes) else 0
            exitosos = max(0, pendientes_antes - pendientes_despues)
            
            self.resultado_obtenido.emit({
                "exitosos": exitosos, 
                "fallidos": pendientes_despues, 
                "total": pendientes_antes, 
                "mensaje": "Ejecución manual de red completada."
            })
        except Exception as e:
            self.resultado_obtenido.emit({
                "exitosos": 0, "fallidos": 0, "total": 0, 
                "mensaje": f"Fallo en hilo de ejecución manual: {str(e)}"
            })

class FTPEmailConfigWindow(QWidget):
    
    def __init__(self, file_scheduler, error_handler: ErrorHandler):
        super().__init__()
        self.file_scheduler = file_scheduler
        self.error_handler = error_handler
        self.progress_dialog = None
        
        self.setWindowTitle("🚀 Configuración FTP/Email - Sistema Automático")
        self.setMinimumSize(1000, 800)
        
        self._setup_ui()
        self._setup_conexiones()
        self._cargar_configuracion()
        self._iniciar_monitoreo()
        self._actualizar_estado_ui()
    
    def _setup_ui(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(15, 15, 15, 15)
        layout_principal.setSpacing(10)
        
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
        
        self.tabs = QTabWidget()
        self.tabs.addTab(self._crear_tab_configuracion(), "⚙️ CONFIGURACIÓN")
        self.tabs.addTab(self._crear_tab_monitoreo(), "📈 MONITOREO")
        self.tabs.addTab(self._crear_tab_logs(), "📝 REGISTROS")
        layout_principal.addWidget(self.tabs, 1)
        
        barra_acciones = QHBoxLayout()
        
        self.btn_guardar = QPushButton("💾 GUARDAR CONFIGURACIÓN")
        self.btn_guardar.setFont(QFont("Arial", 10, QFont.Bold))
        self.btn_guardar.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; padding: 10px; border-radius: 5px; }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.btn_guardar.clicked.connect(self.guardar_configuracion)
        
        self.btn_probar_ftp = QPushButton("🔍 PROBAR FTP")
        self.btn_probar_ftp.setStyleSheet("QPushButton { background-color: #2196F3; color: white; padding: 8px; border-radius: 5px; }")
        self.btn_probar_ftp.clicked.connect(self._probar_conexion_ftp_safe)
        
        self.btn_probar_email = QPushButton("📧 PROBAR EMAIL")
        self.btn_probar_email.setStyleSheet("QPushButton { background-color: #FF9800; color: white; padding: 8px; border-radius: 5px; }")
        self.btn_probar_email.clicked.connect(self._probar_email_safe)
        
        self.btn_forzar_envio = QPushButton("⚡ ENVÍO INMEDIATO")
        self.btn_forzar_envio.setStyleSheet("""
            QPushButton { background-color: #9C27B0; color: white; padding: 8px; border-radius: 5px; font-weight: bold; }
            QPushButton:hover { background-color: #7B1FA2; }
        """)
        self.btn_forzar_envio.clicked.connect(self._forzar_envio_inmediato_safe)
        
        barra_acciones.addWidget(self.btn_guardar, 2)
        barra_acciones.addWidget(self.btn_probar_ftp, 1)
        barra_acciones.addWidget(self.btn_probar_email, 1)
        barra_acciones.addWidget(self.btn_forzar_envio, 1)
        layout_principal.addLayout(barra_acciones)
    
    def _crear_tab_configuracion(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        splitter = QSplitter(Qt.Horizontal)
        
        panel_ftp = QGroupBox("🔌 CONFIGURACIÓN FTP")
        layout_ftp = QFormLayout()
        self.txt_host = QLineEdit()
        self.txt_usuario = QLineEdit()
        self.txt_clave = QLineEdit()
        self.txt_clave.setEchoMode(QLineEdit.Password)
        self.txt_ruta_remota = QLineEdit()
        
        layout_ftp.addRow("Servidor FTP:", self.txt_host)
        layout_ftp.addRow("Usuario:", self.txt_usuario)
        layout_ftp.addRow("Contraseña:", self.txt_clave)
        layout_ftp.addRow("Ruta Remota:", self.txt_ruta_remota)
        panel_ftp.setLayout(layout_ftp)
        
        panel_email = QGroupBox("📧 CONFIGURACIÓN EMAIL")
        layout_email = QFormLayout()
        self.txt_smtp = QLineEdit()
        self.txt_puerto = QLineEdit()
        self.txt_remitente = QLineEdit()
        self.txt_destinatarios = QLineEdit()
        self.txt_asunto = QLineEdit()
        self.txt_usuario_smtp = QLineEdit()
        self.txt_clave_smtp = QLineEdit()
        self.txt_clave_smtp.setEchoMode(QLineEdit.Password)
        
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
        panel_prog.setLayout(layout_prog)
        layout.addWidget(panel_prog)
        
        return tab
    
    def _crear_tab_monitoreo(self):
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
        self.tabla_archivos.setHorizontalHeaderLabels(["ARCHIVO", "TAMAÑO", "MODIFICADO", "ANTIGÜEDÁD", "ESTADO", "PRIORIDAD"])
        
        header = self.tabla_archivos.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 6):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        self.tabla_archivos.setAlternatingRowColors(True)
        self.tabla_archivos.setSortingEnabled(True)
        layout_tabla.addWidget(self.tabla_archivos)
        panel_tabla.setLayout(layout_tabla)
        layout.addWidget(panel_tabla, 1)
        
        return tab
    
    def _crear_tab_logs(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setFont(QFont("Courier New", 9))
        layout.addWidget(self.txt_logs)
        return tab
    
    def _setup_conexiones(self):
        self.timer_monitoreo = QTimer()
        self.timer_monitoreo.timeout.connect(self._actualizar_estado_ui)
        
        self.worker = WorkerActualizacion(self.file_scheduler)
        self.worker.estado_obtenido.connect(self._procesar_estado_actualizado)
        self.worker.archivos_obtenidos.connect(self._procesar_archivos_actualizados)
    
    def _cargar_configuracion(self):
        try:
            # Llamada a ConfigManager para detonar el copiado de plantilla FTP si no existe
            ftp_config = ConfigManager.cargar_config_ftp()
            
            self.txt_host.setText(ftp_config.get('host', ''))
            self.txt_usuario.setText(ftp_config.get('usuario', ''))
            self.txt_clave.setText(ftp_config.get('clave', ''))
            self.txt_ruta_remota.setText(ftp_config.get('ruta_remota', ''))
            
            if 'hora_envio' in ftp_config:
                try:
                    hora, minuto = map(int, ftp_config['hora_envio'].split(':'))
                    self.time_envio.setTime(QTime(hora, minuto))
                except: pass
            
            # Llamada a ConfigManager para detonar el copiado de plantilla Email si no existe
            email_config = ConfigManager.cargar_config_email()
            
            self.txt_smtp.setText(email_config.get('smtp_server', ''))
            self.txt_puerto.setText(str(email_config.get('smtp_port', 587)))
            self.txt_remitente.setText(email_config.get('from', ''))
            self.txt_destinatarios.setText(','.join(email_config.get('to', [])))
            self.txt_asunto.setText(email_config.get('subject', ''))
            self.txt_usuario_smtp.setText(email_config.get('email_usuario', email_config.get('username', '')))
            self.txt_clave_smtp.setText(email_config.get('email_clave', email_config.get('password', '')))
            
        except Exception as e:
            self.error_handler.log_error("CONFIG-LOAD", f"Error cargando configuración: {e}")
            self._agregar_log(f"❌ Error cargando configuración: {e}")
    
    def _iniciar_monitoreo(self):
        self.timer_monitoreo.start(10000)
    
    def _actualizar_estado_ui(self):
        if not self.worker.isRunning():
            self.worker.start()
    
    def _procesar_estado_actualizado(self, estado):
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
                
        except Exception as e:
            self.error_handler.log_error("010", f"Error actualizando estado UI del scheduler: {e}", es_error_sistema=True)
    
    def _procesar_archivos_actualizados(self, archivos):
        try:
            self.tabla_archivos.setRowCount(len(archivos))
            for i, archivo in enumerate(archivos):
                self.tabla_archivos.setItem(i, 0, QTableWidgetItem(archivo["nombre"]))
                self.tabla_archivos.setItem(i, 1, QTableWidgetItem(f"{archivo['tamano_kb']} KB"))
                self.tabla_archivos.setItem(i, 2, QTableWidgetItem(archivo["modificado"]))
                self.tabla_archivos.setItem(i, 3, QTableWidgetItem(f"{archivo['antiguedad_dias']} días"))
                self.tabla_archivos.setItem(i, 4, QTableWidgetItem(archivo["estado"]))
                self.tabla_archivos.setItem(i, 5, QTableWidgetItem(archivo["prioridad"]))
        except Exception as e:
            self.error_handler.log_error("010", f"Error actualizando lista de archivos en UI: {e}", es_error_sistema=True)
    
    def _agregar_log(self, mensaje):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_logs.append(f"[{timestamp}] {mensaje}")
        lines = self.txt_logs.toPlainText().split('\n')
        if len(lines) > 1000:
            self.txt_logs.setPlainText('\n'.join(lines[-1000:]))
    
    def _probar_conexion_ftp_safe(self):
        self.btn_probar_ftp.setEnabled(False)
        self.btn_probar_ftp.setText("Probando...")
        
        ftp_config = {
            "host": self.txt_host.text().strip(),
            "usuario": self.txt_usuario.text().strip(),
            "clave": self.txt_clave.text(),
            "ruta_remota": self.txt_ruta_remota.text().strip() or "/",
            "timeout": 15,
            "secure": False
        }
        
        def execute_test():
            try:
                ftp_manager = FTPManager(ftp_config, self.error_handler)
                success = ftp_manager.verificar_conexion()
                self.btn_probar_ftp.setEnabled(True)
                self.btn_probar_ftp.setText("🔍 PROBAR FTP")
                
                if success:
                    self._agregar_log("✅ Prueba FTP exitosa")
                    QMessageBox.information(self, "✅ Éxito", "Conexión FTP establecida correctamente.")
                else:
                    self._agregar_log("❌ Prueba FTP fallida")
                    QMessageBox.warning(self, "❌ Fallo", "No se pudo establecer conexión FTP.")
            except Exception as e:
                self.btn_probar_ftp.setEnabled(True)
                self.btn_probar_ftp.setText("🔍 PROBAR FTP")
                self._agregar_log(f"❌ Error prueba FTP: {e}")
        
        QTimer.singleShot(100, execute_test)
    
    def _probar_email_safe(self):
        if not all([self.txt_smtp.text().strip(), self.txt_puerto.text().strip(), 
                    self.txt_remitente.text().strip(), self.txt_destinatarios.text().strip()]):
            QMessageBox.warning(self, "Validación", "Complete los campos obligatorios del email")
            return
        
        self.btn_probar_email.setEnabled(False)
        self.btn_probar_email.setText("Enviando...")
        
        def execute_test():
            try:
                msg = MIMEMultipart()
                msg['From'] = self.txt_remitente.text().strip()
                msg['To'] = self.txt_destinatarios.text().strip()
                msg['Subject'] = "Prueba - Sistema Tesseract UTR"
                msg.attach(MIMEText(f"Prueba de configuración SMTP\nEnviado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 'plain'))
                
                server = smtplib.SMTP(self.txt_smtp.text().strip(), int(self.txt_puerto.text()))
                server.starttls()
                if self.txt_usuario_smtp.text().strip():
                    server.login(self.txt_usuario_smtp.text().strip(), self.txt_clave_smtp.text())
                
                server.send_message(msg)
                server.quit()
                
                self.btn_probar_email.setEnabled(True)
                self.btn_probar_email.setText("📧 PROBAR EMAIL")
                self._agregar_log("✅ Prueba email exitosa")
                QMessageBox.information(self, "✅ Éxito", "Correo de prueba enviado exitosamente.")
            except Exception as e:
                self.btn_probar_email.setEnabled(True)
                self.btn_probar_email.setText("📧 PROBAR EMAIL")
                self._agregar_log(f"❌ Error prueba email: {e}")
                QMessageBox.critical(self, "❌ Error", f"Error enviando correo:\n{str(e)}")
        
        QTimer.singleShot(100, execute_test)
    
    def _forzar_envio_inmediato_safe(self):
        respuesta = QMessageBox.question(
            self, "⚠️ Envío Inmediato",
            "¿Está seguro de enviar TODOS los archivos pendientes AHORA?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if respuesta != QMessageBox.Yes: return
            
        try:
            self.progress_dialog = QProgressDialog("Enviando archivos al servidor...", "Cancelar", 0, 0, self)
            self.progress_dialog.setWindowTitle("⚡ Procesando Envío")
            self.progress_dialog.setWindowModality(Qt.WindowModal)
            self.progress_dialog.show()
            
            self.worker_envio = WorkerEnvioManual(self.file_scheduler)
            self.worker_envio.resultado_obtenido.connect(self._on_envio_manual_terminado)
            self.worker_envio.start()
        except Exception as e:
            if self.progress_dialog: self.progress_dialog.close()
            QMessageBox.critical(self, "Error", f"Error:\n{str(e)}")

    def _on_envio_manual_terminado(self, resultado):
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
            
        self._actualizar_estado_ui()
        
        exitosos = resultado.get("exitosos", 0)
        fallidos = resultado.get("fallidos", 0)
        
        if exitosos > 0:
            QMessageBox.information(self, "✅ Envío Finalizado", f"Reportes transferidos: {exitosos}\nReportes fallidos en cola: {fallidos}")
        elif fallidos > 0:
            QMessageBox.warning(self, "⚠️ Envío Fallido", f"No se pudo enviar ({fallidos} siguen pendientes).")
        else:
            QMessageBox.information(self, "Información", resultado.get("mensaje", ""))
    
    def guardar_configuracion(self):
        try:
            if not self.txt_host.text().strip():
                QMessageBox.warning(self, "Validación", "El servidor FTP es obligatorio")
                return
            
            hora = self.time_envio.time()
            hora_str = f"{hora.hour():02d}:{hora.minute():02d}"
            
            # 1. Empaquetado Estricto: Protocolo FTP
            ftp_config = {
                "host": self.txt_host.text().strip(),
                "usuario": self.txt_usuario.text().strip(),
                "clave": self.txt_clave.text(),
                "ruta_remota": self.txt_ruta_remota.text().strip(),
                "hora_envio": hora_str,
                "timeout": 60,
                "secure": False,
                "puerto": 21,
                "enabled": self.chk_habilitado.isChecked() # <--- CRÍTICO PARA LA PERSISTENCIA
            }
            
            # 2. Empaquetado Estricto: Protocolo SMTP
            email_config = None
            if self.txt_smtp.text().strip():
                destinos = [t.strip() for t in self.txt_destinatarios.text().split(',') if t.strip()]
                email_config = {
                    "smtp_host": self.txt_smtp.text().strip(),
                    "smtp_server": self.txt_smtp.text().strip(),
                    "smtp_port": int(self.txt_puerto.text() or 587),
                    "email_usuario": self.txt_usuario_smtp.text().strip(),
                    "email_clave": self.txt_clave_smtp.text(),
                    "from": self.txt_remitente.text().strip(),
                    "to": destinos,
                    "destinatarios": destinos,
                    "subject": self.txt_asunto.text().strip() or "Reporte Tesseract UTR",
                    "asunto": self.txt_asunto.text().strip() or "Reporte Tesseract UTR",
                    "username": self.txt_usuario_smtp.text().strip(),
                    "password": self.txt_clave_smtp.text()
                }
            
            # 3. Persistencia en Disco
            ConfigManager.guardar_config_ftp(ftp_config)
            if email_config:
                ConfigManager.guardar_config_email(email_config)
            
            # 4. Sincronización Arquitectónica con el Orquestador (Corrección de Inyección)
            # Pasamos los diccionarios separados como lo dicta la firma del método en FileScheduler
            self.file_scheduler.actualizar_configuracion_completa(ftp_config, email_config)
            
            # 5. Gobernabilidad de Ciclo de Vida
            if self.chk_habilitado.isChecked():
                self.file_scheduler.iniciar()
            else:
                self.file_scheduler.detener()
            
            StateManager.marcar_completado("ftp_email")
            QMessageBox.information(self, "✅ Configuración Guardada", "Configuración actualizada y aplicada a los motores de red.")
            self._agregar_log(f"✅ Configuración aplicada. Motor Automático: {'ACTIVO' if self.chk_habilitado.isChecked() else 'INACTIVO'}")
            
        except Exception as e:
            self.error_handler.log_error("CONFIG-SAVE", f"Error guardando: {e}")
            QMessageBox.critical(self, "❌ Error", f"Error al guardar:\n{str(e)}")
    
    def closeEvent(self, event):
        if hasattr(self, 'timer_monitoreo'):
            self.timer_monitoreo.stop()
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait(1000)
        super().closeEvent(event)