# TESERACTO-UTR/GUI/Windows/ReportsWindow.py 

import os
import json
import schedule
import threading
import time
import shutil
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QComboBox, QPushButton, QLabel, 
                            QGroupBox, QFileDialog, QMessageBox, QHBoxLayout, QLineEdit)
from PyQt5.QtCore import QTimer
from Core.System.ConfigManager import ConfigManager
from Core.System.StateManager import StateManager
from Core.System.ErrorHandler import ErrorHandler
from Core.System.PathManager import path_manager
from Core.DataProcessing.Services import RecordFormatter, ConfigProvider, BitmaskConverter, FileNameGenerator

class ReportsWindow(QWidget):
    def __init__(self, medidor, error_handler: ErrorHandler):
        super().__init__()
        self.medidor = medidor
        self.error_handler = error_handler
        
        # Aplicar estilo consistente con MainWindow
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #cccccc;
                font-family: Segoe UI;
            }
            QLabel {
                color: #cccccc;
                padding: 2px;
            }
            QComboBox {
                background-color: #3b3b3b;
                color: white;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
                min-height: 20px;
            }
            QComboBox:hover {
                border: 1px solid #777777;
            }
            QComboBox:drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left-width: 1px;
                border-left-color: #555555;
                border-left-style: solid;
            }
            QComboBox QAbstractItemView {
                background-color: #3b3b3b;
                color: white;
                selection-background-color: #555555;
            }
            QPushButton {
                background-color: #5a5a5a;
                color: white;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px 10px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #666666;
                border: 1px solid #777777;
            }
            QPushButton:pressed {
                background-color: #777777;
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
            QLineEdit {
                background-color: #3b3b3b;
                color: white;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
            }
            QLineEdit:read-only {
                background-color: #333333;
                color: #aaaaaa;
            }
        """)
        
        # Widgets
        self.combo_formato = QComboBox()
        self.combo_formato.addItems(["Medidor", "SistemaMedicion"])
        self.btn_generar = QPushButton("Generar TXT")
        self.lbl_status = QLabel("Seleccione formato y pulse Generar")
        
        # Layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Formato de Reporte:"))
        layout.addWidget(self.combo_formato)
        layout.addWidget(self.btn_generar)
        layout.addWidget(self.lbl_status)
        
        # Sección para copiar reporte histórico
        historical_group = QGroupBox("COPIADO DE REPORTE TXT HISTORICO")
        historical_layout = QVBoxLayout()

        # Ruta del reporte histórico
        historical_path_layout = QHBoxLayout()
        historical_path_label = QLabel("Ruta del reporte histórico:")
        self.historical_path_edit = QLineEdit()
        self.historical_path_edit.setReadOnly(True)
        historical_path_layout.addWidget(historical_path_label)
        historical_path_layout.addWidget(self.historical_path_edit)
        historical_layout.addLayout(historical_path_layout)

        # Ruta USB destino
        usb_layout = QHBoxLayout()
        usb_label = QLabel("Ruta USB destino:")
        self.usb_path_edit = QLineEdit()
        self.usb_path_edit.setPlaceholderText("Seleccione la ruta de la USB")
        usb_browse_btn = QPushButton("Examinar")
        usb_browse_btn.clicked.connect(self.select_usb_path)
        usb_layout.addWidget(usb_label)
        usb_layout.addWidget(self.usb_path_edit)
        usb_layout.addWidget(usb_browse_btn)
        historical_layout.addLayout(usb_layout)

        # Botón para copiar
        self.copy_btn = QPushButton("Copiar txt acumulativo a USB")
        self.copy_btn.clicked.connect(self.copy_historical_txt)
        historical_layout.addWidget(self.copy_btn)

        historical_group.setLayout(historical_layout)
        layout.addWidget(historical_group)
        
        self.setLayout(layout)
        
        # Conexiones
        self.btn_generar.clicked.connect(self.iniciar_proceso_reportes)
        
        # Timer para scheduler
        self.timer = QTimer()
        self.timer.timeout.connect(self.verificar_tareas_programadas)
        self.timer.start(60000)
        self.scheduler_thread = None

        # Actualizar la ruta del histórico
        self.update_historical_path()

    def update_historical_path(self):
        try:
            config = ConfigManager.cargar_config_general()
            storage_path = config.get("storage_path", "")
            report_type = config.get("report_type", "Medidor")
            
            if storage_path and report_type:
                # Generar el nombre del archivo histórico
                config_provider = ConfigProvider(ConfigManager())
                name_gen = FileNameGenerator(config_provider)
                historical_name = name_gen.generate_historic_name(report_type)
                historical_full_path = os.path.join(storage_path, historical_name)
                self.historical_path_edit.setText(historical_full_path)
            else:
                self.historical_path_edit.setText("No configurado")
        except Exception as e:
            self.historical_path_edit.setText("Error al cargar la ruta")
            self.error_handler.log_error("REP-HIST", f"Error updating historical path: {e}")

    def select_usb_path(self):
        path = QFileDialog.getExistingDirectory(self, "Seleccionar directorio USB")
        if path:
            self.usb_path_edit.setText(path)

    def copy_historical_txt(self):
        historical_path = self.historical_path_edit.text()
        usb_dest_path = self.usb_path_edit.text()
        
        if not historical_path or historical_path == "No configurado" or not os.path.exists(historical_path):
            QMessageBox.warning(self, "Error", "La ruta del reporte histórico no es válida o no existe.")
            return
        
        if not usb_dest_path or not os.path.exists(usb_dest_path):
            QMessageBox.warning(self, "Error", "Seleccione una ruta USB válida.")
            return
        
        try:
            # Copiar el archivo
            filename = os.path.basename(historical_path)
            dest_file = os.path.join(usb_dest_path, filename)
            shutil.copy2(historical_path, dest_file)
            QMessageBox.information(self, "Éxito", f"Reporte histórico copiado a:\n{dest_file}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al copiar: {str(e)}")
            self.error_handler.log_error("REP-COPY", f"Error copying historical report: {e}")

    def iniciar_proceso_reportes(self):
        try:
            config = ConfigManager.cargar_config_general()
            usb_path = config.get("storage_path", "")
            hora_programada = config.get("hora_reporte", "23:00")
            
            # Guardar tipo de reporte seleccionado
            tipo_reporte = self.combo_formato.currentText()
            config["report_type"] = tipo_reporte
            ConfigManager.guardar_config_general(config)
            
            # Actualizar la ruta del histórico mostrada
            self.update_historical_path()
            
            # Validación básica de USB
            if not usb_path:
                self.lbl_status.setText("❌ Ruta USB no configurada")
                return
            if not os.path.exists(usb_path):
                self.lbl_status.setText("❌ Ruta USB no existe")
                return

            # Programar tarea diaria (SIN pasar archivos histórico)
            self.programar_tarea_diaria(hora_programada)
            
            # Generar reporte inmediato
            self.generar_reporte_diario()
            self.lbl_status.setText("✅ Reporte diario programado")
            
        except Exception as e:
            self.lbl_status.setText(f"❌ Error: {str(e)}")
            self.error_handler.log_error("REP-INIT", str(e))

    def programar_tarea_diaria(self, hora: str):
        schedule.clear()
        schedule.every().day.at(hora).do(self.generar_reporte_diario)

    # Modificar todas las funciones que usan rutas relativas
    def generar_reporte_diario(self):
        try:
            self.error_handler.log_evento("INICIANDO GENERACIÓN DE REPORTE DIARIO", "REP-001")
            
            config = ConfigManager.cargar_config_general()
            tipo_reporte = config.get("report_type", "Medidor")
            usb_path = config.get("storage_path", "")
            
            self.error_handler.log_evento(f"Configuración: tipo={tipo_reporte}, ruta={usb_path}", "REP-002")
            
            # Validación crítica de USB
            if not usb_path or not os.path.exists(usb_path):
                raise ValueError("Ruta USB no configurada o inválida")
            
            # Obtener medidor desde StateManager
            medidor = StateManager.get_state('medidor')
            if not medidor:
                raise ValueError("Medidor no configurado")
            
            self.error_handler.log_evento(f"Medidor obtenido: {type(medidor).__name__}", "REP-003")
            
            # ========== LECTURA ROBUSTA CON REINTENTOS ==========
            datos = {}
            max_intentos = 3
            
            for intento in range(max_intentos):
                try:
                    self.error_handler.log_evento(f"Intentando lectura del medidor (intento {intento + 1}/{max_intentos})", "REP-004")
                    
                    # Verificar conexión primero
                    if not medidor.client.connected:
                        self.error_handler.log_evento("Conectando medidor...", "REP-005")
                        if not medidor.conectar():
                            self.error_handler.log_evento("No se pudo conectar, reintentando...", "REP-006")
                            continue
                    
                    # Realizar lectura
                    datos = medidor.leer_registros()
                    self.error_handler.log_evento(f"Datos crudos leídos: {datos}", "REP-007")
                    
                    # Verificar que tenemos datos válidos (no todos None o 0)
                    if datos and any(v is not None for v in datos.values()):
                        valores_validos = {k: v for k, v in datos.items() if v is not None}
                        self.error_handler.log_evento(f"Lectura exitosa con {len(valores_validos)} valores válidos", "REP-008")
                        break
                    else:
                        self.error_handler.log_evento(f"Lectura vacía o con valores None en intento {intento + 1}", "REP-009")
                        if intento < max_intentos - 1:
                            time.sleep(2)  # Esperar 2 segundos antes de reintentar
                            
                except Exception as e:
                    self.error_handler.log_error("REP-010", f"Error en intento {intento + 1}: {str(e)}")
                    if intento < max_intentos - 1:
                        time.sleep(2)
            
            # Si después de todos los intentos no hay datos, crear estructura con valores por defecto
            if not datos or all(v is None for v in datos.values()):
                self.error_handler.log_error("REP-011", "No se pudieron obtener datos después de todos los intentos")
                datos = {"flujo_instantaneo": 0.0, "flujo_acumulado": 0.0}
            else:
                # Asegurar que las claves críticas existan
                if "flujo_instantaneo" not in datos or datos["flujo_instantaneo"] is None:
                    datos["flujo_instantaneo"] = 0.0
                    self.error_handler.log_evento("flujo_instantaneo no encontrado, usando 0.0", "REP-012")
                if "flujo_acumulado" not in datos or datos["flujo_acumulado"] is None:
                    datos["flujo_acumulado"] = 0.0
                    self.error_handler.log_evento("flujo_acumulado no encontrado, usando 0.0", "REP-013")
            # ========== FIN LECTURA ROBUSTA ==========
            
            perfil = medidor.perfil
            self.error_handler.log_evento(f"Perfil del medidor: {perfil.get('tipo_medidor', 'Desconocido')}", "REP-014")
            
            # Obtener código KER del ErrorHandler
            ker_code = self.error_handler.get_ker_code()
            self.error_handler.log_evento(f"Código KER: {ker_code}", "REP-015")
            
            # Generar contenido con formato
            config_provider = ConfigProvider(ConfigManager())
            bitmask_converter = BitmaskConverter()
            formatter = RecordFormatter(config_provider, bitmask_converter)
            contenido = formatter.format(tipo_reporte, datos, perfil, ker_code)
            
            name_gen = FileNameGenerator(config_provider)
            
            # 1. Archivo historico (USB) - SIN FECHA
            nombre_historico = name_gen.generate_historic_name(tipo_reporte)
            ruta_historico = os.path.join(usb_path, nombre_historico)
            
            with open(ruta_historico, 'a', encoding='utf-8') as f:
                f.write(contenido + "\n")
            self.error_handler.log_evento(f"Registro añadido a histórico: {ruta_historico}", "REP-016")
            
            # 2. Crear archivo diario (pendientes_usb) - CON FECHA
            nombre_diario = name_gen.generate_daily_name(tipo_reporte)
            # USAR PATHMANGER PARA RUTA ABSOLUTA
            pendientes_dir = str(path_manager.get_pendientes_usb_path())
            ruta_diario = os.path.join(pendientes_dir, nombre_diario)
            
            os.makedirs(pendientes_dir, exist_ok=True)
            with open(ruta_diario, 'w', encoding='utf-8') as f:
                f.write(contenido)
            self.error_handler.log_evento(f"Archivo diario creado: {ruta_diario}", "REP-017")
                
        except Exception as e:
            self.error_handler.log_error("REP-018", f"ERROR CRÍTICO en generar_reporte_diario: {str(e)}")
            # Incluir código KER incluso en errores de generación
            ker_code = self.error_handler.get_ker_code()
            error_content = f"ERR|{datetime.now().strftime('%Y%m%d|%H%M%S')}|{type(e).__name__}|{str(e)}|{ker_code}"
            
            # Intentar guardar el error en ambos archivos
            try:
                with open(os.path.join(usb_path, "error_report.txt"), 'a', encoding='utf-8') as f:
                    f.write(error_content + "\n")
            except:
                pass
                
            try:
                # USAR PATHMANGER PARA RUTA ABSOLUTA
                pendientes_dir = str(path_manager.get_pendientes_usb_path())
                os.makedirs(pendientes_dir, exist_ok=True)
                with open(os.path.join(pendientes_dir, "error_report.txt"), 'w', encoding='utf-8') as f:
                    f.write(error_content)
            except:
                pass
                
            self.error_handler.log_error("REP-GEN", f"Error generando reporte: {str(e)}")
    
    def verificar_tareas_programadas(self):
        """Ejecuta las tareas programadas pendientes."""
        schedule.run_pending()