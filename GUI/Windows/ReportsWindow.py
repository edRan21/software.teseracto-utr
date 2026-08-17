# TESERACTO-UTR/GUI/Windows/ReportsWindow.py

import os
import schedule
import time
import shutil
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QComboBox, QPushButton, QLabel, 
                            QGroupBox, QMessageBox, QHBoxLayout, QLineEdit, QTextEdit)
from PyQt5.QtCore import QTimer, Qt

from Core.System.ConfigManager import ConfigManager
from Core.System.StateManager import StateManager
from Core.System.ErrorHandler import ErrorHandler
from Core.System.PathManager import path_manager
from Core.DataProcessing.Services import RecordFormatter, ConfigProvider, BitmaskConverter, FileNameGenerator
from Core.DataProcessing.DataProcessor import DataProcessor
from Core.System.ThreadManager import thread_manager

class ReportsWindow(QWidget):
    def __init__(self, error_handler: ErrorHandler):
        super().__init__()
        self.error_handler = error_handler
        
        self.data_processor = DataProcessor(self.error_handler)
        
        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: #cccccc; font-family: Segoe UI; }
            QLabel { color: #cccccc; padding: 2px; }
            QComboBox { background-color: #3b3b3b; color: white; border: 1px solid #555555; border-radius: 3px; padding: 5px; }
            QPushButton { background-color: #5a5a5a; color: white; border: 1px solid #555555; border-radius: 3px; padding: 5px 10px; }
            QPushButton:hover { background-color: #2E86C1; border: 1px solid #2874A6; }
            QPushButton:disabled { background-color: #3b3b3b; color: #777; border: 1px solid #444; }
            QGroupBox { color: #cccccc; background-color: #2b2b2b; border: 1px solid #444444; border-radius: 5px; margin-top: 1ex; padding-top: 10px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px; color: #cccccc; }
            QLineEdit, QTextEdit { background-color: #3b3b3b; color: white; border: 1px solid #555555; border-radius: 3px; padding: 5px; }
            QLineEdit:read-only, QTextEdit:read-only { background-color: #333333; color: #4fc3f7; font-weight: bold; }
        """)
        
        # Widgets
        self.combo_formato = QComboBox()
        self.combo_formato.addItems(["Medidor", "SistemaMedicion"])
        
        # Sincronizar el combobox con el valor guardado
        config = ConfigManager.cargar_config_general()
        formato_guardado = config.get("report_type", "Medidor")
        idx = self.combo_formato.findText(formato_guardado)
        if idx >= 0:
            self.combo_formato.setCurrentIndex(idx)
            
        self.btn_generar = QPushButton("Generar TXT Manual")
        self.btn_generar.setMinimumHeight(35)
        self.lbl_status = QLabel("Seleccione formato y pulse Generar")
        
        self.texto_vista_previa = QTextEdit()
        self.texto_vista_previa.setReadOnly(True)
        self.texto_vista_previa.setMinimumHeight(80)
        self.texto_vista_previa.setStyleSheet("background-color: #1e1e1e; color: #81c784; font-family: Consolas; font-size: 11pt;")
        
        # Layout principal
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        titulo = QLabel("Gestión de Reportes Diarios")
        titulo.setStyleSheet("font-size: 16pt; font-weight: bold; color: #ffffff;")
        titulo.setAlignment(Qt.AlignCenter)
        layout.addWidget(titulo)
        
        config_group = QGroupBox("Configuración y Vista Previa")
        config_layout = QVBoxLayout()
        config_layout.addWidget(QLabel("Formato de Reporte:"))
        config_layout.addWidget(self.combo_formato)
        config_layout.addWidget(self.btn_generar)
        config_layout.addWidget(self.lbl_status)
        config_layout.addWidget(self.texto_vista_previa)
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # Sección USB (Automática)
        historical_group = QGroupBox("COPIADO DE REPORTE TXT HISTÓRICO A USB")
        historical_layout = QVBoxLayout()

        historical_path_layout = QHBoxLayout()
        historical_path_layout.addWidget(QLabel("Ruta local del histórico:"))
        self.historical_path_edit = QLineEdit()
        self.historical_path_edit.setReadOnly(True)
        historical_path_layout.addWidget(self.historical_path_edit)
        historical_layout.addLayout(historical_path_layout)

        usb_layout = QHBoxLayout()
        usb_layout.addWidget(QLabel("Estado de USB:"))
        self.usb_path_edit = QLineEdit()
        self.usb_path_edit.setReadOnly(True)
        self.usb_path_edit.setText("Buscando unidad USB...")
        usb_layout.addWidget(self.usb_path_edit)
        historical_layout.addLayout(usb_layout)

        self.copy_btn = QPushButton("Copiar histórico a la USB detectada")
        self.copy_btn.setMinimumHeight(35)
        self.copy_btn.setEnabled(False) # Deshabilitado hasta que haya USB
        self.copy_btn.clicked.connect(self.copy_historical_txt)
        historical_layout.addWidget(self.copy_btn)

        historical_group.setLayout(historical_layout)
        layout.addWidget(historical_group)
        
        layout.addStretch()
        self.setLayout(layout)
        
        # Conexiones y Timers
        self.btn_generar.clicked.connect(self.iniciar_proceso_reportes)
        self.combo_formato.currentIndexChanged.connect(self.update_historical_path)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.verificar_tareas_programadas)
        self.timer.start(60000)
        
        # Timer para escanear USB usando la información del orquestador
        self.usb_ui_timer = QTimer()
        self.usb_ui_timer.timeout.connect(self.actualizar_estado_usb)
        self.usb_ui_timer.start(2000)

        self.update_historical_path()

    def actualizar_estado_usb(self):
        """Verifica las unidades extraíbles disponibles en Windows."""
        import string
        import ctypes
        
        drive = None
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                # Comprobar si es extraíble (DRIVE_REMOVABLE = 2)
                if ctypes.windll.kernel32.GetDriveTypeW(f"{letter}:\\") == 2:
                    drive = f"{letter}:\\"
                    break
            bitmask >>= 1
            
        if drive:
            self.usb_path_edit.setText(f"USB Detectada en: {drive}")
            self.copy_btn.setEnabled(True)
            self.copy_btn.setText(f"Copiar histórico a {drive}")
        else:
            self.usb_path_edit.setText("Esperando conexión USB...")
            self.copy_btn.setEnabled(False)
            self.copy_btn.setText("Conecte una USB para copiar")

    def update_historical_path(self):
        try:
            config = ConfigManager.cargar_config_general()
            storage_path = config.get("storage_path", "")
            
            # Siempre leer el combobox actual
            report_type = self.combo_formato.currentText()
            
            if storage_path and report_type:
                config_provider = ConfigProvider(ConfigManager())
                name_gen = FileNameGenerator(config_provider, self.error_handler)
                historical_name = name_gen.generate_historic_name(report_type)
                historical_full_path = os.path.join(storage_path, historical_name)
                self.historical_path_edit.setText(historical_full_path)
            else:
                self.historical_path_edit.setText("No configurado")
        except Exception as e:
            self.historical_path_edit.setText("Error al cargar la ruta")
            self.error_handler.log_error("305", f"Error actualizando ruta de reporte histórico: {e}", es_error_sistema=True)

    def copy_historical_txt(self):
        historical_path = self.historical_path_edit.text()
        
        if not historical_path or historical_path == "No configurado" or not os.path.exists(historical_path):
            QMessageBox.warning(self, "Error", "La ruta del reporte histórico no es válida o no existe.")
            return
            
        usb_text = self.usb_path_edit.text()
        if "Esperando" in usb_text:
            QMessageBox.warning(self, "Error", "La USB fue desconectada.")
            return
            
        # Extraer la letra de la unidad del texto (ej: "USB Detectada en: E:\")
        usb_dest_path = usb_text.split(": ")[1] if ": " in usb_text else None
        
        if not usb_dest_path:
            return
            
        try:
            filename = os.path.basename(historical_path)
            dest_file = os.path.join(usb_dest_path, filename)
            shutil.copy2(historical_path, dest_file)
            QMessageBox.information(self, "Éxito", f"Reporte histórico copiado a:\n{dest_file}")
            self.error_handler.log_evento("Respaldo histórico guardado en USB exitosamente")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al copiar: {str(e)}")
            self.error_handler.log_error("305", f"Error copiando reporte histórico a USB: {e}", es_error_sistema=True)

    def iniciar_proceso_reportes(self):
        try:
            self.btn_generar.setEnabled(False)
            self.btn_generar.setText("Generando...")
            
            config = ConfigManager.cargar_config_general()
            hora_programada = config.get("hora_reporte", "23:00")
            
            tipo_reporte = self.combo_formato.currentText()
            config["report_type"] = tipo_reporte
            ConfigManager.guardar_config_general(config)
            
            self.update_historical_path()

            self.programar_tarea_diaria(hora_programada)
            self.generar_reporte_diario()
            
            self.lbl_status.setText("✅ Reporte generado exitosamente.")
            
        except Exception as e:
            self.lbl_status.setText(f"❌ Error: {str(e)}")
            self.error_handler.log_error("305", f"Fallo al iniciar proceso de reportes: {str(e)}", es_error_sistema=True)
        finally:
            self.btn_generar.setText("Generar TXT Manual")
            self.btn_generar.setEnabled(True)

    def programar_tarea_diaria(self, hora: str):
        schedule.clear()
        schedule.every().day.at(hora).do(self.generar_reporte_diario)

    def generar_reporte_diario(self):
        try:
            config = ConfigManager.cargar_config_general()
            tipo_reporte = config.get("report_type", "Medidor")
            usb_path = config.get("storage_path", "")
            
            poller = thread_manager.modbus_poller
            if not poller or not poller.medidor:
                raise ValueError("Medidor no configurado o motor Modbus inactivo.")
            
            # ========== LECTURA DESDE RAM (No bloqueante) ==========
            paquete = poller.obtener_ultimo_paquete()
            datos_crudos = paquete.get("datos_crudos", {})
            
            if not datos_crudos or not paquete.get("estado_conexion", False):
                self.error_handler.log_error("007", "No hay datos de memoria RAM confiables para el reporte", es_error_sistema=True)
                datos_crudos = {"flujo_instantaneo": 0.0, "flujo_acumulado": 0.0}
            else:
                if "flujo_instantaneo" not in datos_crudos or datos_crudos["flujo_instantaneo"] is None:
                    datos_crudos["flujo_instantaneo"] = 0.0
                if "flujo_acumulado" not in datos_crudos or datos_crudos["flujo_acumulado"] is None:
                    datos_crudos["flujo_acumulado"] = 0.0
                    
            perfil = poller.medidor.perfil
            
            # Procesamiento matemático de los datos
            datos_procesados = self.data_processor.process(datos_crudos, perfil)

            # Obtención del código de error unificado
            ker_code = self.error_handler.obtener_ker_para_reporte()
            
            # Generar contenido usando los servicios
            config_provider = ConfigProvider(ConfigManager())
            bitmask_converter = BitmaskConverter()
            formatter = RecordFormatter(config_provider, bitmask_converter, self.error_handler)
            
            contenido = formatter.format(tipo_reporte, datos_procesados, perfil, ker_code)
            
            # Mostrar vista previa
            self.texto_vista_previa.setPlainText(contenido)
            
            name_gen = FileNameGenerator(config_provider, self.error_handler)
            
            # 1. Archivo historico (Guardado Localmente en storage_path)
            nombre_historico = name_gen.generate_historic_name(tipo_reporte)
            ruta_historico = os.path.join(usb_path, nombre_historico)
            with open(ruta_historico, 'a', encoding='utf-8') as f:
                f.write(contenido + "\n")
            
            # 2. Archivo diario de envío (Para FTP/Email)
            nombre_diario = name_gen.generate_daily_name(tipo_reporte)
            
            pendientes_dir = str(path_manager.get_pendientes_usb_path())
            os.makedirs(pendientes_dir, exist_ok=True)
            
            ruta_diario = os.path.join(pendientes_dir, nombre_diario)
            ruta_temp = ruta_diario + ".tmp"
            
            # Escritura atómica
            with open(ruta_temp, 'w', encoding='utf-8') as f:
                f.write(contenido)
            
            os.replace(ruta_temp, ruta_diario)
                
        except Exception as e:
            self.error_handler.log_error("304", f"ERROR CRÍTICO generando reporte diario: {str(e)}", es_error_sistema=True)
            ker_code = self.error_handler.obtener_ker_para_reporte()
            error_content = f"ERR|{datetime.now().strftime('%Y%m%d|%H%M%S')}|{type(e).__name__}|{str(e)}|{ker_code}"
            
            try:
                with open(os.path.join(usb_path, "error_report.txt"), 'a', encoding='utf-8') as f:
                    f.write(error_content + "\n")
            except: pass
                
            try:
                pendientes_dir = str(path_manager.get_pendientes_usb_path())
                os.makedirs(pendientes_dir, exist_ok=True)
                with open(os.path.join(pendientes_dir, "error_report.txt"), 'w', encoding='utf-8') as f:
                    f.write(error_content)
            except: pass
    
    def verificar_tareas_programadas(self):
        schedule.run_pending()