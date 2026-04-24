# TESERACTO-UTR/GUI/Windows/ReportsWindow.py 

import os
import schedule
import time
import shutil
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QComboBox, QPushButton, QLabel, 
                            QGroupBox, QMessageBox, QHBoxLayout, QLineEdit)
from PyQt5.QtCore import QTimer
from Core.System.ConfigManager import ConfigManager
from Core.System.StateManager import StateManager
from Core.System.ErrorHandler import ErrorHandler
from Core.System.PathManager import path_manager
from Core.DataProcessing.Services import RecordFormatter, ConfigProvider, BitmaskConverter, FileNameGenerator, UnitConverter
from Core.DataProcessing.DataProcessor import DataProcessor

class ReportsWindow(QWidget):
    def __init__(self, medidor, error_handler: ErrorHandler, usb_manejador=None):
        super().__init__()
        self.medidor = medidor
        self.error_handler = error_handler
        self.usb_manejador = usb_manejador
        
        # APORTACIÓN: Instanciar el DataProcessor
        self.data_processor = DataProcessor(UnitConverter())
        
        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: #cccccc; font-family: Segoe UI; }
            QLabel { color: #cccccc; padding: 2px; }
            QComboBox { background-color: #3b3b3b; color: white; border: 1px solid #555555; border-radius: 3px; padding: 5px; }
            QPushButton { background-color: #5a5a5a; color: white; border: 1px solid #555555; border-radius: 3px; padding: 5px 10px; }
            QPushButton:hover { background-color: #2E86C1; border: 1px solid #2874A6; }
            QPushButton:disabled { background-color: #3b3b3b; color: #777; border: 1px solid #444; }
            QGroupBox { color: #cccccc; background-color: #2b2b2b; border: 1px solid #444444; border-radius: 5px; margin-top: 1ex; padding-top: 10px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px; color: #cccccc; }
            QLineEdit { background-color: #3b3b3b; color: white; border: 1px solid #555555; border-radius: 3px; padding: 5px; }
            QLineEdit:read-only { background-color: #333333; color: #4fc3f7; font-weight: bold; }
        """)
        
        # Widgets
        self.combo_formato = QComboBox()
        self.combo_formato.addItems(["Medidor", "SistemaMedicion"])
        self.btn_generar = QPushButton("Generar TXT Manual")
        self.lbl_status = QLabel("Seleccione formato y pulse Generar")
        
        # Layout principal
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Formato de Reporte:"))
        layout.addWidget(self.combo_formato)
        layout.addWidget(self.btn_generar)
        layout.addWidget(self.lbl_status)
        
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
        self.copy_btn.setEnabled(False) # Deshabilitado hasta que haya USB
        self.copy_btn.clicked.connect(self.copy_historical_txt)
        historical_layout.addWidget(self.copy_btn)

        historical_group.setLayout(historical_layout)
        layout.addWidget(historical_group)
        self.setLayout(layout)
        
        # Conexiones y Timers
        self.btn_generar.clicked.connect(self.iniciar_proceso_reportes)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.verificar_tareas_programadas)
        self.timer.start(60000)
        
        # APORTACIÓN: Timer para escanear USB visualmente
        self.usb_ui_timer = QTimer()
        self.usb_ui_timer.timeout.connect(self.actualizar_estado_usb)
        self.usb_ui_timer.start(2000)

        self.update_historical_path()

    def actualizar_estado_usb(self):
        """Revisa si el manejador encontró una USB y actualiza la UI"""
        if self.usb_manejador:
            drive = self.usb_manejador._get_first_usb_drive()
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
            report_type = config.get("report_type", "Medidor")
            
            if storage_path and report_type:
                config_provider = ConfigProvider(ConfigManager())
                name_gen = FileNameGenerator(config_provider)
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
        
        if not self.usb_manejador:
            QMessageBox.critical(self, "Error", "El servicio USB no está disponible.")
            return
            
        usb_dest_path = self.usb_manejador._get_first_usb_drive()
        
        if not historical_path or historical_path == "No configurado" or not os.path.exists(historical_path):
            QMessageBox.warning(self, "Error", "La ruta del reporte histórico no es válida o no existe.")
            return
            
        if not usb_dest_path:
            QMessageBox.warning(self, "Error", "La USB fue desconectada.")
            return
        
        try:
            filename = os.path.basename(historical_path)
            dest_file = os.path.join(usb_dest_path, filename)
            shutil.copy2(historical_path, dest_file)
            QMessageBox.information(self, "Éxito", f"Reporte histórico copiado a:\\n{dest_file}")
            self.error_handler.log_evento("Respaldo histórico guardado en USB exitosamente")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al copiar: {str(e)}")
            self.error_handler.log_error("305", f"Error copiando reporte histórico a USB: {e}", es_error_sistema=True)

    def iniciar_proceso_reportes(self):
        try:
            config = ConfigManager.cargar_config_general()
            hora_programada = config.get("hora_reporte", "23:00")
            
            tipo_reporte = self.combo_formato.currentText()
            config["report_type"] = tipo_reporte
            ConfigManager.guardar_config_general(config)
            
            self.update_historical_path()

            self.programar_tarea_diaria(hora_programada)
            self.generar_reporte_diario()
            self.lbl_status.setText("✅ Reporte generado y programado")
            
        except Exception as e:
            self.lbl_status.setText(f"❌ Error: {str(e)}")
            self.error_handler.log_error("305", f"Fallo al iniciar proceso de reportes: {str(e)}", es_error_sistema=True)

    def programar_tarea_diaria(self, hora: str):
        schedule.clear()
        schedule.every().day.at(hora).do(self.generar_reporte_diario)

    def generar_reporte_diario(self):
        try:
            config = ConfigManager.cargar_config_general()
            tipo_reporte = config.get("report_type", "Medidor")
            usb_path = config.get("storage_path", "")
            
            medidor = StateManager.get_state('medidor')
            if not medidor:
                raise ValueError("Medidor no configurado")
            
            # ========== LECTURA ROBUSTA ==========
            datos_crudos = {}
            max_intentos = 3
            
            for intento in range(max_intentos):
                try:
                    if not medidor.client.connected:
                        if not medidor.conectar(): continue
                    
                    datos_crudos = medidor.leer_registros()
                    if datos_crudos and any(v is not None for v in datos_crudos.values()):
                        break
                    elif intento < max_intentos - 1:
                        time.sleep(2)
                except Exception as e:
                    self.error_handler.log_error("007", f"Error en intento de lectura {intento + 1}: {str(e)}", es_error_sistema=True)
                    if intento < max_intentos - 1: time.sleep(2)
            
            if not datos_crudos or all(v is None for v in datos_crudos.values()):
                self.error_handler.log_error("007", "No se pudieron obtener datos del medidor para el reporte", es_error_sistema=True)
                datos_crudos = {"flujo_instantaneo": 0.0, "flujo_acumulado": 0.0}
            else:
                if "flujo_instantaneo" not in datos_crudos or datos_crudos["flujo_instantaneo"] is None:
                    datos_crudos["flujo_instantaneo"] = 0.0
                if "flujo_acumulado" not in datos_crudos or datos_crudos["flujo_acumulado"] is None:
                    datos_crudos["flujo_acumulado"] = 0.0
                    
            perfil = medidor.perfil
            
            # APORTACIÓN: Procesar matemáticamente los datos crudos
            datos_procesados = self.data_processor.process(datos_crudos, perfil)

            ker_code = self.error_handler.get_ker_code()
            
            # Generar contenido usando los datos procesados
            config_provider = ConfigProvider(ConfigManager())
            bitmask_converter = BitmaskConverter()
            formatter = RecordFormatter(config_provider, bitmask_converter)
            
            # ¡La magia ocurre aquí! Se usa datos_procesados
            contenido = formatter.format(tipo_reporte, datos_procesados, perfil, ker_code)
            name_gen = FileNameGenerator(config_provider)
            
            # 1. Archivo historico (Guardado Localmente en storage_path)
            nombre_historico = name_gen.generate_historic_name(tipo_reporte)
            ruta_historico = os.path.join(usb_path, nombre_historico)
            with open(ruta_historico, 'a', encoding='utf-8') as f:
                f.write(contenido + "\n")
            
            # 2. Archivo diario de envío (Enviado a pendientes_usb para FTP/Email y USB Automático)
            # ✅ REFACTORIZACIÓN: ESCRITURA ATÓMICA
            nombre_diario = name_gen.generate_daily_name(tipo_reporte)
            
            # -> LÍNEAS RESTAURADAS: Definir la variable pendientes_dir y asegurar que el directorio exista
            pendientes_dir = str(path_manager.get_pendientes_usb_path())
            os.makedirs(pendientes_dir, exist_ok=True)
            
            # Ahora sí se puede armar la ruta correctamente
            ruta_diario = os.path.join(pendientes_dir, nombre_diario)
            ruta_temp = ruta_diario + ".tmp"
            
            # Escribimos en un archivo temporal (.tmp) que el Scheduler ignora
            with open(ruta_temp, 'w', encoding='utf-8') as f:
                f.write(contenido)
            
            # El renombrado es atómico: el archivo aparece en la carpeta solo cuando está 100% escrito
            os.rename(ruta_temp, ruta_diario)
                
        except Exception as e:
            self.error_handler.log_error("304", f"ERROR CRÍTICO generando reporte diario: {str(e)}", es_error_sistema=True)
            ker_code = self.error_handler.get_ker_code()
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