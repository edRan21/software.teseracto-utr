# TESERACTO-UTR/GUI/Windows/DashboardWindow.py

import logging
import os
import time
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QPalette, QFont, QPixmap
from Core.DataProcessing.Services import UnitConverter
from Core.System.ConfigManager import ConfigManager
from Core.System.ErrorHandler import ErrorHandler
from Core.System.StateManager import StateManager

class DashboardWorker(QObject):
    """Worker dedicado para lecturas del dashboard"""
    data_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    connection_status = pyqtSignal(bool)
    
    def __init__(self, medidor):
        super().__init__()
        self.medidor = medidor
        self._is_running = True
        self._last_successful_read = 0

    def read_data(self):
        """Lectura de datos en hilo de trabajo - VERSIÓN MEJORADA"""
        if not self._is_running or not self.medidor:
            return
            
        try:
            # LECTURA CON TIMEOUT REDUCIDO PARA DASHBOARD
            # Verificar si el medidor tiene el método seguro
            if hasattr(self.medidor, 'leer_registros_seguro'):
                datos = self.medidor.leer_registros_seguro(timeout=3.0)
            else:
                # FALLBACK: Usar método normal con manejo de timeout manual
                self.logger = logging.getLogger(__name__)
                self.logger.warning("Método leer_registros_seguro no disponible, usando lectura normal")
                datos = self.medidor.leer_registros()
            
            if datos and any(datos.values()):  # Verificar que hay datos válidos
                self._last_successful_read = time.time()
                self.data_ready.emit(datos)
                self.connection_status.emit(True)
            else:
                self.connection_status.emit(False)
                self.error_occurred.emit("No se pudieron leer datos del medidor")
                
        except Exception as e:
            self.connection_status.emit(False)
            self.error_occurred.emit(f"Error en lectura: {str(e)}")

    def stop(self):
        """Detener worker"""
        self._is_running = False

class DashboardWindow(QWidget):
    def __init__(self, medidor, error_handler: ErrorHandler):
        super().__init__()
        self.medidor = medidor
        self.error_handler = error_handler
        self.config_manager = ConfigManager()
        self.unit_converter = UnitConverter()
        
        self.unidad_medidor = "m³/h"
        self.unidad_visual = self.config_manager.cargar_config_general().get("unidad_visualizacion", "m³/h")
        self.unidad_volumen = "m³"
        
        self.logo_image = self.load_logo_image()
        
        # Worker y thread para lecturas
        self.worker = None
        self.worker_thread = None
        
        self.apply_dark_theme()
        self.setup_ui()
        self.setup_timers()
        self.actualizar_unidades()

    def load_logo_image(self):
        try:
            from Core.System.PathManager import path_manager
            image_path = path_manager.get_image_path("LOGO2.jpeg")
            
            if image_path.exists():
                pixmap = QPixmap(str(image_path))
                return pixmap.scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            else:
                # APORTACIÓN 1: Código oficial 301
                self.error_handler.log_error("301", f"Imagen de logo no encontrada: {image_path}", es_error_sistema=True)
                return None
        except Exception as e:
            # APORTACIÓN 1: Código oficial 301
            self.error_handler.log_error("301", f"Error cargando logo: {str(e)}", es_error_sistema=True)
            return None

    def apply_dark_theme(self):
        dark_theme = """
            QWidget { background-color: #2b2b2b; color: #ffffff; border: none; font-size: 12pt; }
            QGroupBox { color: #ffffff; border: 1px solid #555; border-radius: 5px; margin-top: 10px; padding-top: 10px; font-weight: bold; font-size: 12pt; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 5px; color: #ffffff; font-size: 12pt; }
            QLabel { color: #ffffff; background-color: transparent; font-size: 12pt; }
            .flow-value { font-size: 50pt; color: #4fc3f7; }
            .flow-unit { font-size: 30pt; color: #4fc3f7; }
            .volume-value { font-size: 50pt; color: #81c784; }
            .volume-unit { font-size: 30pt; color: #81c784; }
            .velocity-value { font-size: 50pt; color: #e1bee7; }
            .velocity-unit { font-size: 30pt; color: #e1bee7; }
            .positive-flow { color: #4fc3f7; font-size: 22pt; }
            .negative-flow { color: #ff9800; font-size: 22pt; }
            .stopped-flow { color: #bdbdbd; font-size: 22pt; }
            .connected-status { color: #81c784; font-weight: bold; font-size: 12pt; }
            .disconnected-status { color: #ff5252; font-weight: bold; font-size: 12pt; }
            .system-ok { color: #81c784; font-weight: bold; font-size: 12pt; }
            .system-warning { color: #ffb74d; font-weight: bold; font-size: 12pt; }
            .system-error { color: #ff5252; font-weight: bold; font-size: 12pt; }
            .sensor-value { font-size: 22pt; font-family: Arial; }
            .error-code { font-size: 22pt; font-family: Consolas; }
            .status-label { font-size: 12pt; }
            .logo-label { background-color: transparent; border: none; padding: 5px; }
        """
        self.setStyleSheet(dark_theme)

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        title_main_layout = QVBoxLayout()
        title_main_layout.setSpacing(5)
        
        title_top_layout = QHBoxLayout()
        
        title_container = QVBoxLayout()
        self.title_label = QLabel("TESSERACTO UTR")
        self.title_label.setStyleSheet("font-size: 20pt; font-weight: bold; color: #ffffff;")
        title_container.addWidget(self.title_label)
        
        self.system_status = QLabel("✅ Sistema operativo")
        self.system_status.setProperty("class", "system-ok")
        title_container.addWidget(self.system_status)
        
        title_top_layout.addLayout(title_container)
        title_top_layout.addStretch()
        
        if self.logo_image:
            logo_label = QLabel()
            logo_label.setPixmap(self.logo_image)
            logo_label.setProperty("class", "logo-label")
            logo_label.setAlignment(Qt.AlignRight)
            title_top_layout.addWidget(logo_label)
        
        title_main_layout.addLayout(title_top_layout)
        main_layout.addLayout(title_main_layout)
        
        separator = QLabel()
        separator.setStyleSheet("background-color: #555; height: 2px;")
        main_layout.addWidget(separator)
        
        data_group = QGroupBox("Datos de Medición")
        data_layout = QGridLayout()
        data_layout.setSpacing(15)
        
        # --- COLUMNA 0: FLUJO INSTANTÁNEO ---
        flow_label = QLabel("FLUJO INSTANTÁNEO:")
        flow_label.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 14pt;")
        data_layout.addWidget(flow_label, 0, 0)
        
        flow_container = QWidget()
        flow_h_layout = QHBoxLayout(flow_container)
        flow_h_layout.setContentsMargins(0, 0, 0, 0)
        flow_h_layout.setSpacing(5)
        
        self.flow_value = QLabel("--")
        self.flow_value.setProperty("class", "flow-value")
        self.flow_value.setMinimumWidth(120)
        self.flow_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.flow_unit = QLabel("m³/h")
        self.flow_unit.setProperty("class", "flow-unit")
        
        flow_h_layout.addWidget(self.flow_value)
        flow_h_layout.addWidget(self.flow_unit)
        flow_h_layout.addStretch()
        
        data_layout.addWidget(flow_container, 1, 0)
        
        # --- COLUMNA 1: VOLUMEN ACUMULADO ---
        volume_label = QLabel("VOLUMEN ACUMULADO:")
        volume_label.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 14pt;")
        data_layout.addWidget(volume_label, 0, 1)
        
        volume_container = QWidget()
        volume_h_layout = QHBoxLayout(volume_container)
        volume_h_layout.setContentsMargins(0, 0, 0, 0)
        volume_h_layout.setSpacing(5)
        
        self.volume_value = QLabel("--")
        self.volume_value.setProperty("class", "volume-value")
        self.volume_value.setMinimumWidth(120)
        self.volume_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.volume_unit = QLabel("m³")
        self.volume_unit.setProperty("class", "volume-unit")
        
        volume_h_layout.addWidget(self.volume_value)
        volume_h_layout.addWidget(self.volume_unit)
        volume_h_layout.addStretch()
        
        data_layout.addWidget(volume_container, 1, 1)
        
        # --- COLUMNA 2: VELOCIDAD DE FLUJO ---
        velocity_label = QLabel("VELOCIDAD DE FLUJO:")
        velocity_label.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 14pt;")
        data_layout.addWidget(velocity_label, 0, 2)

        velocity_container = QWidget()
        velocity_h_layout = QHBoxLayout(velocity_container)
        velocity_h_layout.setContentsMargins(0, 0, 0, 0)
        velocity_h_layout.setSpacing(5)

        self.velocity_value = QLabel("--")
        self.velocity_value.setProperty("class", "velocity-value")
        self.velocity_value.setMinimumWidth(120)
        self.velocity_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.velocity_unit = QLabel("m/s")
        self.velocity_unit.setProperty("class", "velocity-unit")

        velocity_h_layout.addWidget(self.velocity_value)
        velocity_h_layout.addWidget(self.velocity_unit)
        velocity_h_layout.addStretch()

        data_layout.addWidget(velocity_container, 1, 2)
        
        # --- DIRECCIÓN DE FLUJO (DEBAJO, ABARCANDO 3 COLUMNAS) ---
        direction_label = QLabel("DIRECCIÓN DE FLUJO:")
        direction_label.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 14pt;")
        data_layout.addWidget(direction_label, 2, 0, 1, 3)
        
        self.direction_value = QLabel("--")
        self.direction_value.setProperty("class", "stopped-flow")
        data_layout.addWidget(self.direction_value, 3, 0, 1, 3)
        
        data_group.setLayout(data_layout)
        main_layout.addWidget(data_group)
        
        info_layout = QHBoxLayout()
        info_layout.setSpacing(10)
        
        sensor_stats_group = QGroupBox("Estadísticas del Sensor")
        sensor_stats_layout = QGridLayout()
        
        sensor_label_energizacion = QLabel("Encendidos:")
        sensor_label_energizacion.setStyleSheet("font-weight: bold;")
        sensor_stats_layout.addWidget(sensor_label_energizacion, 0, 0)
        
        self.lbl_energizacion = QLabel("N/A")
        self.lbl_energizacion.setProperty("class", "sensor-value")
        sensor_stats_layout.addWidget(self.lbl_energizacion, 0, 1)
        
        sensor_label_errores = QLabel("Errores:")
        sensor_label_errores.setStyleSheet("font-weight: bold;")
        sensor_stats_layout.addWidget(sensor_label_errores, 1, 0)
        
        self.lbl_errores = QLabel("N/A")
        self.lbl_errores.setProperty("class", "sensor-value")
        sensor_stats_layout.addWidget(self.lbl_errores, 1, 1)
        
        # 🔧 CORRECCIÓN CRÍTICA: Cambiar de lbl_cod_error a lbl_codigo_error
        sensor_label_cod_error = QLabel("Código Error:")
        sensor_label_cod_error.setStyleSheet("font-weight: bold;")
        sensor_stats_layout.addWidget(sensor_label_cod_error, 2, 0)
        
        self.lbl_codigo_error = QLabel("N/A")  # 🔧 NOMBRE CORREGIDO
        self.lbl_codigo_error.setProperty("class", "error-code")
        sensor_stats_layout.addWidget(self.lbl_codigo_error, 2, 1)
        
        sensor_stats_group.setLayout(sensor_stats_layout)
        info_layout.addWidget(sensor_stats_group)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)
        
        unit_box = QGroupBox("Configuración de Unidades")
        unit_layout = QVBoxLayout(unit_box)
        
        self.medidor_unit_label = QLabel("Medidor: Cargando...")
        self.visual_unit_label = QLabel("Visualización: Cargando...")
        
        unit_layout.addWidget(self.medidor_unit_label)
        unit_layout.addWidget(self.visual_unit_label)
        bottom_layout.addWidget(unit_box)
        
        status_box = QGroupBox("Estado de Conexión")
        status_layout = QVBoxLayout(status_box)
        
        self.connection_status = QLabel("Desconectado")
        self.connection_status.setProperty("class", "disconnected-status")
        
        from datetime import datetime
        self.startup_datetime = datetime.now()
        self.startup_label = QLabel(f"Inicio: {self.startup_datetime.strftime('%d/%m/%Y %H:%M:%S')}")
        self.startup_label.setProperty("class", "status-label")
        
        self.last_update = QLabel("Última actualización: --:--:--")
        self.last_update.setProperty("class", "status-label")
        
        status_layout.addWidget(self.connection_status)
        status_layout.addWidget(self.startup_label)
        status_layout.addWidget(self.last_update)
        bottom_layout.addWidget(status_box)
        
        main_layout.addLayout(bottom_layout)
        
        self.setLayout(main_layout)

    def setup_timers(self):
        """Configura timers de forma segura"""
        # TIMER DE INTERFAZ (RÁPIDO) - EN HILO PRINCIPAL
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.actualizar_ui)
        self.ui_timer.start(1000)  # 1 segundo para UI
        
        # TIMER DE LECTURA (LENTO) - EN HILO DE TRABAJO
        self.read_timer = QTimer(self)
        self.read_timer.timeout.connect(self.iniciar_lectura_segura)
        self.read_timer.start(30000)  # 30 segundos para lecturas
        
        self.unit_timer = QTimer(self)
        self.unit_timer.timeout.connect(self.actualizar_unidades)
        self.unit_timer.start(60000)
        
        self.connection_timer = QTimer(self)
        self.connection_timer.timeout.connect(self.verificar_conexion)
        self.connection_timer.start(30000)
        
        # INICIAR WORKER
        self.setup_worker()

    def setup_worker(self):
        """Configura el worker para lecturas en hilo separado"""
        if self.medidor:
            self.worker = DashboardWorker(self.medidor)
            self.worker_thread = QThread()
            
            # Mover worker al hilo
            self.worker.moveToThread(self.worker_thread)
            
            # Conectar señales
            self.worker.data_ready.connect(self.procesar_datos)
            self.worker.error_occurred.connect(self.manejar_error_lectura)
            self.worker.connection_status.connect(self.actualizar_estado_conexion)
            
            # Iniciar hilo
            self.worker_thread.start()

    def iniciar_lectura_segura(self):
        """Inicia lectura de forma segura en hilo de trabajo"""
        if self.worker and hasattr(self.worker, 'read_data'):
            # Ejecutar en el hilo del worker
            QTimer.singleShot(0, self.worker.read_data)

    def procesar_datos(self, datos):
        """Procesa datos recibidos del worker (en hilo principal)"""
        try:
            # ========== VERIFICACIÓN PARA RESET KER ==========
            
            # Si tenemos datos válidos y el sistema está operativo, resetear KER
            datos_son_validos = datos and any(v is not None for v in datos.values())
            
            if datos_son_validos:
                # Verificar que no hay errores del medidor
                estado_operativo = True
                
                # Para ISOMAG, verificar flags de error
                if hasattr(self.medidor, 'perfil') and self.medidor.perfil.get("tipo_medidor") == "ISOMAG":
                    errores = datos.get("errores_sensor", {})
                    if isinstance(errores, dict) and any(errores.values()):
                        estado_operativo = False
                
                # Para Badger, verificar estado del medidor
                elif hasattr(self.medidor, 'leer_estado_medidor'):
                    try:
                        estado = self.medidor.leer_estado_medidor()
                        if estado and estado.get('meter_status', 0) != 0:
                            estado_operativo = False
                    except Exception:
                        estado_operativo = True  # Si falla, asumir operativo
                
                # ✅ RESETEAR KER SI TODO ESTÁ BIEN
                if estado_operativo:
                    if hasattr(self.error_handler, 'reset_ker_normal'):
                        self.error_handler.reset_ker_normal()
            # ========== FIN VERIFICACIÓN KER ==========
            
            # ACTUALIZAR INTERFAZ CON DATOS NUEVOS
            flujo_valor = datos.get("flujo_instantaneo", 0.0) or 0.0
            
            flujo_convertido = self.unit_converter.convert(
                flujo_valor,
                self.unidad_medidor,
                self.unidad_visual
            )
            
            volumen_valor = datos.get("flujo_acumulado", 0.0) or 0.0
            velocidad_valor = datos.get("velocidad_flujo", 0.0) or 0.0
            direccion_valor = datos.get("direccion_flujo", 0) or 0
            
            # ACTUALIZAR WIDGETS (OPERACIÓN RÁPIDA)
            self.flow_value.setText(f"{flujo_convertido:.3f}")
            self.volume_value.setText(f"{volumen_valor:.2f}")
            self.velocity_value.setText(f"{velocidad_valor:.3f}")
            
            # DIRECCIÓN DE FLUJO COMPATIBLE CON AMBOS MEDIDORES
            if direccion_valor == 2:  # Flujo negativo
                self.direction_value.setText("⬅️ NEGATIVA")
                self.direction_value.setProperty("class", "negative-flow")
            elif direccion_valor == 1:  # Flujo positivo
                self.direction_value.setText("➡️ POSITIVA") 
                self.direction_value.setProperty("class", "positive-flow")
            else:  # Detenido o desconocido
                self.direction_value.setText("⏹️ DETENIDO")
                self.direction_value.setProperty("class", "stopped-flow")
                
            self.style().unpolish(self.direction_value)
            self.style().polish(self.direction_value)
            
            # VERIFICACIÓN DE ESTADO COMPATIBLE CON AMBOS MEDIDORES
            estado_operativo = True
            
            # Para ISOMAG, verificar flags de error
            if hasattr(self.medidor, 'perfil') and self.medidor.perfil.get("tipo_medidor") == "ISOMAG":
                errores = datos.get("errores_sensor", {})
                if isinstance(errores, dict) and any(errores.values()):
                    estado_operativo = False
            
            # Para Badger, verificar estado del medidor
            elif hasattr(self.medidor, 'leer_estado_medidor'):
                try:
                    estado = self.medidor.leer_estado_medidor()
                    if estado and estado.get('meter_status', 0) != 0:
                        estado_operativo = False
                except Exception:
                    estado_operativo = True  # Si falla, asumir operativo
            
            if estado_operativo:
                self.system_status.setText("✅ Sistema operativo")
                self.system_status.setProperty("class", "system-ok")
            else:
                self.system_status.setText("⚠️ Error en medidor")
                self.system_status.setProperty("class", "system-error")
                
            self.style().unpolish(self.system_status)
            self.style().polish(self.system_status)
            
            # 🔧 CORRECCIÓN: ACTUALIZAR ESTADÍSTICAS CON NOMBRE CORREGIDO
            try:
                energizacion = datos.get('contador_energizacion', None)
                self.lbl_energizacion.setText(str(energizacion) if energizacion is not None else "N/A")
                
                errores = datos.get('errores_sensor', {})
                errores_text = []
                if isinstance(errores, dict):
                    # Compatible con ambos medidores
                    if errores.get('sensor_fault', False) or errores.get('coils_excitation_error', False):
                        errores_text.append("Sensor")
                    if errores.get('over_range', False) or errores.get('flow_rate_overflow', False):
                        errores_text.append("Rango")
                    if errores.get('empty_pipe', False) or errores.get('pipe_empty', False):
                        errores_text.append("Tubería")
                self.lbl_errores.setText(", ".join(errores_text) if errores_text else "Ninguno")
                
                cod_error = datos.get('codigo_error', None)
                # 🔧 USANDO EL NOMBRE CORREGIDO
                if cod_error is not None:
                    self.lbl_codigo_error.setText(f"{cod_error:04X}")
                else:
                    self.lbl_codigo_error.setText("N/A")
            
            except Exception as e:
                # APORTACIÓN 1: Código oficial 010
                self.error_handler.log_error("010", f"Error actualizando estadísticas visuales: {str(e)}", es_error_sistema=True)
                
        except Exception as e:
            # APORTACIÓN 1: Código oficial 010
            self.error_handler.log_error("010", f"Error procesando datos en dashboard: {str(e)}", es_error_sistema=True)

    def actualizar_ui(self):
        """Actualización rápida de UI (siempre en hilo principal)"""
        # Solo operaciones rápidas de UI aquí
        try:
            from datetime import datetime
            current_time = datetime.now()
            self.last_update.setText(f"Última actualización: {current_time.strftime('%H:%M:%S')}")
        except Exception as e:
            pass  # No bloquear por errores de UI

    def verificar_conexion(self):
        try:
            if self.medidor and hasattr(self.medidor, 'client') and self.medidor.client.connected:
                self.connection_status.setText("Conectado")
                self.connection_status.setProperty("class", "connected-status")
            else:
                self.connection_status.setText("Desconectado")
                self.connection_status.setProperty("class", "disconnected-status")
                
            self.style().unpolish(self.connection_status)
            self.style().polish(self.connection_status)
                
        except Exception as e:
            # APORTACIÓN 1: Código oficial 007
            self.error_handler.log_error("007", f"Error verificando conexión visual: {str(e)}", es_error_sistema=True)

    def actualizar_unidades(self):
        try:
            if self.medidor and hasattr(self.medidor, 'obtener_unidad_flujo'):
                self.unidad_medidor = self.medidor.obtener_unidad_flujo()
            
            config = self.config_manager.cargar_config_general()
            self.unidad_visual = config.get("unidad_visualizacion", "m³/h")
            
            self.medidor_unit_label.setText(f"Medidor: {self.unidad_medidor}")
            self.visual_unit_label.setText(f"Visualización: {self.unidad_visual}")
            self.flow_unit.setText(self.unidad_visual)
            
        except Exception as e:
            # APORTACIÓN 1: Código oficial 303
            self.error_handler.log_error("303", f"Error de conversión actualizando unidades: {str(e)}", es_error_sistema=True)
            self.unidad_medidor = "m³/h"
            self.unidad_visual = "m³/h"

    def manejar_error_lectura(self, mensaje_error):
        """Maneja errores de lectura desde el worker"""
        # APORTACIÓN 1: Código oficial 007
        self.error_handler.log_error("007", mensaje_error, es_error_sistema=True)
        self.system_status.setText("⚠️ Error en lectura")
        self.system_status.setProperty("class", "system-error")

    def actualizar_estado_conexion(self, conectado):
        """Actualiza estado de conexión desde el worker"""
        if conectado:
            self.connection_status.setText("Conectado")
            self.connection_status.setProperty("class", "connected-status")
        else:
            self.connection_status.setText("Desconectado")
            self.connection_status.setProperty("class", "disconnected-status")

    def refresh_unit_config(self):
        try:
            config = self.config_manager.cargar_config_general()
            self.unidad_visual = config.get("unidad_visualizacion", "m³/h")
            
            self.visual_unit_label.setText(f"Visualización: {self.unidad_visual}")
            self.flow_unit.setText(self.unidad_visual)
            
            # También podemos forzar una actualización de datos
            self.iniciar_lectura_segura()
            
        except Exception as e:
            # APORTACIÓN 1: Código oficial 301
            self.error_handler.log_error("301", f"Error refrescando configuración visual: {str(e)}", es_error_sistema=True)

    def closeEvent(self, event):
        """Cierre seguro liberando recursos"""
        # DETENER WORKER PRIMERO
        if self.worker:
            self.worker.stop()
            
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(2000)  # Esperar máximo 2 segundos
            
        # DETENER TIMERS
        if hasattr(self, 'ui_timer'):
            self.ui_timer.stop()
        if hasattr(self, 'read_timer'):
            self.read_timer.stop()
        if hasattr(self, 'unit_timer'):
            self.unit_timer.stop()
        if hasattr(self, 'connection_timer'):
            self.connection_timer.stop()
        
        event.accept()