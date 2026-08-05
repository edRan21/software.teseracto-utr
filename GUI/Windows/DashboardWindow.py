# TESERACTO-UTR/GUI/Windows/DashboardWindow.py

import os
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QGroupBox, QPushButton, QMessageBox, QScrollArea)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal
# Arquitectura renovada
from Core.System.ThreadManager import thread_manager
from Core.DataProcessing.Services import UnitConverter
from Core.DataProcessing.DataProcessor import DataProcessor
from Core.System.ConfigManager import ConfigManager
from Core.System.PathManager import path_manager
from Core.System.ErrorHandler import ErrorHandler

class DashboardWindow(QWidget):
    def __init__(self, error_handler: ErrorHandler):
        """
        Nota: medidor_referencia se mantiene por compatibilidad temporal en la inicialización,
        pero los datos se extraerán estrictamente del thread_manager.modbus_poller.
        """
        super().__init__()
        self.error_handler = error_handler
        
        self.config_manager = ConfigManager()
        self.convertidor_unidades = UnitConverter()
        self.procesador_datos = DataProcessor(self.convertidor_unidades, self.error_handler)
        
        self.unidad_medidor = "m³/h"
        self.unidad_visual = self.config_manager.cargar_config_general().get("unidad_visualizacion", "m³/h")
        self.imagen_logo = self._cargar_imagen_logo()
        
        self._aplicar_tema_oscuro()
        self._configurar_interfaz()
        self._configurar_temporizador_visual()
        self.actualizar_configuracion_unidades()

    def _cargar_imagen_logo(self):
        """Carga la imagen del logo asegurando la ruta mediante PathManager."""
        try:
            ruta_imagen = path_manager.get_image_path("LOGO2.jpeg")
            if ruta_imagen.exists():
                pixmap = QPixmap(str(ruta_imagen))
                return pixmap.scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            else:
                self.error_handler.log_error("301", f"Imagen de logo no encontrada: {ruta_imagen}", es_error_sistema=True)
                return None
        except Exception as e:
            self.error_handler.log_error("301", f"Error cargando logo: {str(e)}", es_error_sistema=True)
            return None

    def _aplicar_tema_oscuro(self):
        """Aplica la hoja de estilos general. (Los selectores CSS se mantienen en inglés por estándar web)"""
        estilo_oscuro = """
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
            .system-error { color: #ff5252; font-weight: bold; font-size: 12pt; }
            .sensor-value { font-size: 22pt; font-family: Arial; }
            .error-code { font-size: 22pt; font-family: Consolas; }
            .status-label { font-size: 12pt; }
        """
        self.setStyleSheet(estilo_oscuro)

    def _configurar_interfaz(self):
        """Construye todos los elementos visuales de la ventana."""
        diseno_ventana = QVBoxLayout()
        diseno_ventana.setContentsMargins(0, 0, 0, 0)
        
        area_scroll = QScrollArea()
        area_scroll.setWidgetResizable(True)
        area_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        widget_contenido = QWidget()
        widget_contenido.setStyleSheet("background-color: transparent;")
        
        diseno_principal = QVBoxLayout()
        diseno_principal.setSpacing(10)
        diseno_principal.setContentsMargins(20, 20, 20, 20)
        
        # --- ENCABEZADO ---
        diseno_titulo = QVBoxLayout()
        diseno_titulo.setSpacing(5)
        
        diseno_superior_titulo = QHBoxLayout()
        contenedor_titulo = QVBoxLayout()
        
        self.lbl_titulo = QLabel("TESSERACTO UTR")
        self.lbl_titulo.setStyleSheet("font-size: 20pt; font-weight: bold; color: #ffffff;")
        contenedor_titulo.addWidget(self.lbl_titulo)
        
        self.lbl_estado_sistema = QLabel("✅ Sistema operativo")
        self.lbl_estado_sistema.setProperty("class", "system-ok")
        contenedor_titulo.addWidget(self.lbl_estado_sistema)
        
        diseno_superior_titulo.addLayout(contenedor_titulo)
        diseno_superior_titulo.addStretch()
        
        if self.imagen_logo:
            lbl_logo = QLabel()
            lbl_logo.setPixmap(self.imagen_logo)
            lbl_logo.setAlignment(Qt.AlignRight)
            diseno_superior_titulo.addWidget(lbl_logo)
        
        diseno_titulo.addLayout(diseno_superior_titulo)
        diseno_principal.addLayout(diseno_titulo)
        
        separador = QLabel()
        separador.setStyleSheet("background-color: #555; height: 2px;")
        diseno_principal.addWidget(separador)
        
        # --- PANEL DE DATOS ---
        grupo_datos = QGroupBox("Datos de Medición")
        diseno_datos = QGridLayout()
        diseno_datos.setSpacing(15)
        
        # FLUJO INSTANTÁNEO
        lbl_flujo = QLabel("FLUJO INSTANTÁNEO:")
        lbl_flujo.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 14pt;")
        diseno_datos.addWidget(lbl_flujo, 0, 0)
        
        contenedor_flujo = QWidget()
        diseno_h_flujo = QHBoxLayout(contenedor_flujo)
        diseno_h_flujo.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_valor_flujo = QLabel("--")
        self.lbl_valor_flujo.setProperty("class", "flow-value")
        self.lbl_valor_flujo.setMinimumWidth(120)
        self.lbl_valor_flujo.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.lbl_unidad_flujo = QLabel("m³/h")
        self.lbl_unidad_flujo.setProperty("class", "flow-unit")
        
        diseno_h_flujo.addWidget(self.lbl_valor_flujo)
        diseno_h_flujo.addWidget(self.lbl_unidad_flujo)
        diseno_h_flujo.addStretch()
        diseno_datos.addWidget(contenedor_flujo, 1, 0)
        
        # VOLUMEN ACUMULADO
        lbl_volumen = QLabel("VOLUMEN ACUMULADO:")
        lbl_volumen.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 14pt;")
        diseno_datos.addWidget(lbl_volumen, 0, 1)
        
        contenedor_volumen = QWidget()
        diseno_h_volumen = QHBoxLayout(contenedor_volumen)
        diseno_h_volumen.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_valor_volumen = QLabel("--")
        self.lbl_valor_volumen.setProperty("class", "volume-value")
        self.lbl_valor_volumen.setMinimumWidth(120)
        self.lbl_valor_volumen.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.lbl_unidad_volumen = QLabel("m³")
        self.lbl_unidad_volumen.setProperty("class", "volume-unit")
        
        diseno_h_volumen.addWidget(self.lbl_valor_volumen)
        diseno_h_volumen.addWidget(self.lbl_unidad_volumen)
        diseno_h_volumen.addStretch()
        diseno_datos.addWidget(contenedor_volumen, 1, 1)
        
        # VELOCIDAD DE FLUJO
        lbl_velocidad = QLabel("VELOCIDAD DE FLUJO:")
        lbl_velocidad.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 14pt;")
        diseno_datos.addWidget(lbl_velocidad, 0, 2)

        contenedor_velocidad = QWidget()
        diseno_h_velocidad = QHBoxLayout(contenedor_velocidad)
        diseno_h_velocidad.setContentsMargins(0, 0, 0, 0)

        self.lbl_valor_velocidad = QLabel("--")
        self.lbl_valor_velocidad.setProperty("class", "velocity-value")
        self.lbl_valor_velocidad.setMinimumWidth(120)
        self.lbl_valor_velocidad.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.lbl_unidad_velocidad = QLabel("m/s")
        self.lbl_unidad_velocidad.setProperty("class", "velocity-unit")

        diseno_h_velocidad.addWidget(self.lbl_valor_velocidad)
        diseno_h_velocidad.addWidget(self.lbl_unidad_velocidad)
        diseno_h_velocidad.addStretch()
        diseno_datos.addWidget(contenedor_velocidad, 1, 2)
        
        # DIRECCIÓN DE FLUJO
        lbl_direccion = QLabel("DIRECCIÓN DE FLUJO:")
        lbl_direccion.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 14pt;")
        diseno_datos.addWidget(lbl_direccion, 2, 0, 1, 3)
        
        self.lbl_valor_direccion = QLabel("--")
        self.lbl_valor_direccion.setProperty("class", "stopped-flow")
        diseno_datos.addWidget(self.lbl_valor_direccion, 3, 0, 1, 3)
        
        grupo_datos.setLayout(diseno_datos)
        diseno_principal.addWidget(grupo_datos)
       
        # --- CONTROLES DE TELEMETRÍA ---
        grupo_control = QGroupBox("⚙️ Control de Telemetría (Modbus)")
        diseno_control = QHBoxLayout()
        
        self.btn_iniciar_telemetria = QPushButton("▶️ Comenzar Lecturas")
        self.btn_iniciar_telemetria.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        self.btn_iniciar_telemetria.clicked.connect(self._arrancar_telemetria)
        
        self.btn_detener_telemetria = QPushButton("⏹️ Detener Lecturas")
        self.btn_detener_telemetria.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 10px;")
        self.btn_detener_telemetria.clicked.connect(self._pausar_telemetria)
        self.btn_detener_telemetria.setEnabled(False)
        
        diseno_control.addWidget(self.btn_iniciar_telemetria)
        diseno_control.addWidget(self.btn_detener_telemetria)
        grupo_control.setLayout(diseno_control)
        diseno_principal.addWidget(grupo_control)
        
        # --- ESTADÍSTICAS DEL SENSOR ---
        diseno_info = QHBoxLayout()
        diseno_info.setSpacing(10)
        
        grupo_estadisticas = QGroupBox("Estadísticas del Sensor")
        diseno_estadisticas = QGridLayout()
        
        lbl_encendidos = QLabel("Encendidos:")
        lbl_encendidos.setStyleSheet("font-weight: bold;")
        diseno_estadisticas.addWidget(lbl_encendidos, 0, 0)
        
        self.lbl_estadistica_encendidos = QLabel("N/A")
        self.lbl_estadistica_encendidos.setProperty("class", "sensor-value")
        diseno_estadisticas.addWidget(self.lbl_estadistica_encendidos, 0, 1)
        
        lbl_errores = QLabel("Errores:")
        lbl_errores.setStyleSheet("font-weight: bold;")
        diseno_estadisticas.addWidget(lbl_errores, 1, 0)
        
        self.lbl_estadistica_errores = QLabel("N/A")
        self.lbl_estadistica_errores.setProperty("class", "sensor-value")
        diseno_estadisticas.addWidget(self.lbl_estadistica_errores, 1, 1)
        
        lbl_codigo_error = QLabel("Código Error:")
        lbl_codigo_error.setStyleSheet("font-weight: bold;")
        diseno_estadisticas.addWidget(lbl_codigo_error, 2, 0)
        
        self.lbl_codigo_hexadecimal = QLabel("N/A") 
        self.lbl_codigo_hexadecimal.setProperty("class", "error-code")
        diseno_estadisticas.addWidget(self.lbl_codigo_hexadecimal, 2, 1)
        
        grupo_estadisticas.setLayout(diseno_estadisticas)
        diseno_info.addWidget(grupo_estadisticas)
        
        # --- ESTADO Y UNIDADES ---
        diseno_inferior = QHBoxLayout()
        diseno_inferior.setSpacing(10)
        
        grupo_unidades = QGroupBox("Configuración de Unidades")
        diseno_unidades = QVBoxLayout(grupo_unidades)
        
        self.lbl_unidad_medidor_info = QLabel("Medidor: Cargando...")
        self.lbl_unidad_visual_info = QLabel("Visualización: Cargando...")
        
        diseno_unidades.addWidget(self.lbl_unidad_medidor_info)
        diseno_unidades.addWidget(self.lbl_unidad_visual_info)
        diseno_inferior.addWidget(grupo_unidades)
        
        grupo_estado = QGroupBox("Estado de Conexión")
        diseno_estado = QVBoxLayout(grupo_estado)
        
        self.lbl_estado_conexion = QLabel("Desconectado")
        self.lbl_estado_conexion.setProperty("class", "disconnected-status")
        
        fecha_inicio = datetime.now()
        lbl_inicio = QLabel(f"Inicio: {fecha_inicio.strftime('%d/%m/%Y %H:%M:%S')}")
        lbl_inicio.setProperty("class", "status-label")
        
        self.lbl_ultima_actualizacion = QLabel("Última actualización: --:--:--")
        self.lbl_ultima_actualizacion.setProperty("class", "status-label")
        
        diseno_estado.addWidget(self.lbl_estado_conexion)
        diseno_estado.addWidget(lbl_inicio)
        diseno_estado.addWidget(self.lbl_ultima_actualizacion)
        diseno_inferior.addWidget(grupo_estado)
        
        diseno_principal.addLayout(diseno_info)
        diseno_principal.addLayout(diseno_inferior)
        
        widget_contenido.setLayout(diseno_principal)
        area_scroll.setWidget(widget_contenido)
        diseno_ventana.addWidget(area_scroll)
        
        self.setLayout(diseno_ventana)

    def _configurar_temporizador_visual(self):
        """
        ÚNICO temporizador del Dashboard. 
        Su función es extraer la información de la memoria RAM.
        NO realiza llamadas bloqueantes de red o hardware.
        """
        self.temporizador_interfaz = QTimer(self)
        self.temporizador_interfaz.timeout.connect(self._consumir_datos_de_memoria)
        # Se iniciará cuando el usuario presione "Comenzar Lecturas"

    def _arrancar_telemetria(self):
        """Ordena al Orquestador encender el motor de hardware y activa la actualización visual."""
        config_path = path_manager.get_config_path("sensor_config.json")
        if not config_path.exists():
            QMessageBox.warning(self, "Atención", "No hay configuración de sensor guardada. Vaya a Configuración Hardware primero.")
            return

        # 1. Ordenar al Orquestador (ThreadManager) arrancar el Productor
        thread_manager.arrancar_hardware()
        
        # 2. Iniciar el Consumidor (Actualización visual cada segundo)
        self.temporizador_interfaz.start(1000)
            
        self.btn_iniciar_telemetria.setEnabled(False)
        self.btn_detener_telemetria.setEnabled(True)
        self.btn_iniciar_telemetria.setText("Lecturas en Proceso...")
        self.actualizar_configuracion_unidades()

    def _pausar_telemetria(self):
        """Inicia la secuencia de apagado de forma asíncrona para evitar congelamientos."""
        # 1. Detener inmediatamente el Consumidor Visual (UI Thread)
        self.temporizador_interfaz.stop()
        
        # 2. Proporcionar retroalimentación visual instantánea al usuario
        self.btn_detener_telemetria.setEnabled(False)
        self.btn_iniciar_telemetria.setEnabled(False) # Bloqueado hasta que termine el apagado
        self.btn_iniciar_telemetria.setText("⏳ Deteniendo hardware...")
        
        self.lbl_estado_conexion.setText("Cerrando puertos de comunicación...")
        self.lbl_estado_conexion.setProperty("class", "stopped-flow")
        self._refrescar_estilo_css(self.lbl_estado_conexion)

        # 3. Delegar la destrucción del hilo Productor a un proceso en segundo plano
        self.worker_detener = self.WorkerDetenerTelemetria()
        self.worker_detener.finished.connect(self._telemetria_detenida_callback)
        self.worker_detener.start()

    def _telemetria_detenida_callback(self):
        """Se ejecuta cuando el hardware ha liberado completamente la memoria y los puertos."""
        self.btn_iniciar_telemetria.setEnabled(True)
        self.btn_iniciar_telemetria.setText("▶️ Comenzar Lecturas")
        
        self.lbl_estado_conexion.setText("Detenido (Manual)")
        self._refrescar_estilo_css(self.lbl_estado_conexion)
        self.lbl_estado_sistema.setText("✅ Sistema en espera")
        self._refrescar_estilo_css(self.lbl_estado_sistema)
    
    def _consumir_datos_de_memoria(self):
        """
        Extrae el Payload de la memoria RAM del ModbusPoller y actualiza la UI.
        Complejidad temporal O(1), ejecución instantánea.
        """
        try:
            # Actualizar hora visual
            self.lbl_ultima_actualizacion.setText(f"Última actualización: {datetime.now().strftime('%H:%M:%S')}")
            
            # Obtener instancia activa del Poller desde el Orquestador central
            poller = thread_manager.modbus_poller
            if not poller:
                self._aplicar_estado_visual_error("Esperando motor...")
                return
                
            # Extraer Payload de la RAM (Sin esperas)
            paquete = poller.obtener_ultimo_paquete()
            
            if paquete["timestamp"] == 0.0:
                self._aplicar_estado_visual_error("Inicializando sensor...")
                return

            if not paquete["estado_conexion"] or paquete["codigo_error"] != "000":
                self._aplicar_estado_visual_error(f"Error {paquete['codigo_error']}")
                return

            # Si llegamos aquí, los datos son válidos
            self._aplicar_estado_visual_conectado()
            self._procesar_y_dibujar_datos(paquete["datos_crudos"], poller.medidor.perfil)
            
        except Exception as e:
            self.error_handler.log_error("010", f"Error crítico al consumir memoria RAM: {e}", es_error_sistema=True)

    def _procesar_y_dibujar_datos(self, datos_crudos: dict, perfil: dict):
        """Aplica factores de escala matemáticos y dibuja en pantalla."""
        try:
            datos_procesados = self.procesador_datos.process(datos_crudos, perfil)
            
            flujo_valor = datos_procesados.get("flujo_instantaneo", 0.0) or 0.0
            flujo_convertido = self.convertidor_unidades.convert(
                flujo_valor,
                self.unidad_medidor,
                self.unidad_visual
            )
            
            volumen_valor = datos_procesados.get("flujo_acumulado", 0.0) or 0.0
            velocidad_valor = datos_procesados.get("velocidad_flujo", 0.0) or 0.0
            direccion_valor = datos_procesados.get("direccion_flujo", 0) or 0
            
            self.lbl_valor_flujo.setText(f"{flujo_convertido:.3f}")
            self.lbl_valor_volumen.setText(f"{volumen_valor:.2f}")
            self.lbl_valor_velocidad.setText(f"{velocidad_valor:.3f}")
            
            # Formato Visual Dirección
            if direccion_valor == 2:
                self.lbl_valor_direccion.setText("⬅️ NEGATIVA")
                self.lbl_valor_direccion.setProperty("class", "negative-flow")
            elif direccion_valor == 1:
                self.lbl_valor_direccion.setText("➡️ POSITIVA") 
                self.lbl_valor_direccion.setProperty("class", "positive-flow")
            else:
                self.lbl_valor_direccion.setText("⏹️ DETENIDO")
                self.lbl_valor_direccion.setProperty("class", "stopped-flow")
            self._refrescar_estilo_css(self.lbl_valor_direccion)
            
            # Estadísticas Inferiores
            energizacion = datos_procesados.get('contador_energizacion', None)
            self.lbl_estadistica_encendidos.setText(str(energizacion) if energizacion is not None else "N/A")
            
            errores = datos_procesados.get('errores_sensor', {})
            errores_text = []
            if isinstance(errores, dict):
                if errores.get('sensor_fault', False) or errores.get('coils_excitation_error', False): errores_text.append("Sensor")
                if errores.get('over_range', False) or errores.get('flow_rate_overflow', False): errores_text.append("Rango")
                if errores.get('empty_pipe', False) or errores.get('pipe_empty', False): errores_text.append("Tubería")
            self.lbl_estadistica_errores.setText(", ".join(errores_text) if errores_text else "Ninguno")
            
            cod_error = datos_procesados.get('codigo_error', None)
            if cod_error is not None:
                self.lbl_codigo_hexadecimal.setText(f"{cod_error:04X}")
            else:
               self.lbl_codigo_hexadecimal.setText("N/A")

            # Evaluación de Salud para el KER
            if not errores_text and cod_error in (0, None, 65535):
                if hasattr(self.error_handler, 'reset_ker_normal'):
                    self.error_handler.reset_ker_normal()

        except Exception as e:
            self.error_handler.log_error("010", f"Error renderizando interfaz: {e}", es_error_sistema=True)

    def _aplicar_estado_visual_error(self, mensaje: str):
        self.lbl_estado_sistema.setText("⚠️ Error en lectura")
        self.lbl_estado_sistema.setProperty("class", "system-error")
        self._refrescar_estilo_css(self.lbl_estado_sistema)
        
        self.lbl_estado_conexion.setText(mensaje)
        self.lbl_estado_conexion.setProperty("class", "disconnected-status")
        self._refrescar_estilo_css(self.lbl_estado_conexion)

    def _aplicar_estado_visual_conectado(self):
        self.lbl_estado_sistema.setText("✅ Sistema operativo")
        self.lbl_estado_sistema.setProperty("class", "system-ok")
        self._refrescar_estilo_css(self.lbl_estado_sistema)
        
        self.lbl_estado_conexion.setText("Conectado y Transmitiendo")
        self.lbl_estado_conexion.setProperty("class", "connected-status")
        self._refrescar_estilo_css(self.lbl_estado_conexion)

    def _refrescar_estilo_css(self, widget):
        """Fuerza al motor de PyQt5 a recalcular el CSS del widget."""
        self.style().unpolish(widget)
        self.style().polish(widget)

    # =========================================================================
    # LÓGICA ASÍNCRONA PARA UNIDADES
    # =========================================================================
    class WorkerUnidadFlujo(QThread):
        finished = pyqtSignal(str)
        
        def __init__(self, medidor):
            super().__init__()
            self.medidor = medidor
            
        def run(self):
            try:
                # Lectura de hardware aislada del hilo principal
                unidad = self.medidor.obtener_unidad_flujo()
                self.finished.emit(unidad if unidad else "")
            except Exception:
                self.finished.emit("")

    def actualizar_configuracion_unidades(self):
        """Sincroniza las etiquetas visuales de forma ASÍNCRONA."""
        try:
            config = self.config_manager.cargar_config_general()
            self.unidad_visual = config.get("unidad_visualizacion", "m³/h")
            
            poller = thread_manager.modbus_poller
            if poller and poller.medidor:
                # 1. Carga inmediata del default del JSON para no dejar la UI vacía
                perfil_activo = poller.medidor.perfil
                self.unidad_medidor = perfil_activo.get("unidad_flujo_default", "m³/h")
                self._actualizar_textos_unidades()
                
                # 2. Invocación Asíncrona: Delegamos la lectura física a un hilo secundario
                self.worker_unidad = self.WorkerUnidadFlujo(poller.medidor)
                self.worker_unidad.finished.connect(self._aplicar_unidad_real)
                self.worker_unidad.start()
            else:
                self.unidad_medidor = "m³/h"
                self._actualizar_textos_unidades()
            
        except Exception as e:
            self.error_handler.log_error("303", f"Fallo al actualizar unidades: {e}", es_error_sistema=True)

    def _aplicar_unidad_real(self, unidad_real: str):
        """Callback ejecutado cuando el hilo secundario termina de interrogar al medidor."""
        if unidad_real:
            self.unidad_medidor = unidad_real
        self._actualizar_textos_unidades()

    def _actualizar_textos_unidades(self):
        """Actualiza puramente los elementos gráficos en el hilo principal."""
        self.lbl_unidad_medidor_info.setText(f"Medidor transmite en: {self.unidad_medidor}")
        self.lbl_unidad_visual_info.setText(f"Visualizando en: {self.unidad_visual}")
        self.lbl_unidad_flujo.setText(self.unidad_visual)
        
    class WorkerDetenerTelemetria(QThread):
        """
        Hilo sepulturero.
        Absorbe la latencia de apagado del hardware (Timeouts residuales)
        para garantizar que la UI se mantenga responsiva al 100%.
        """
        finished = pyqtSignal()
        
        def run(self):
            try:
                # La orden de detención y liberación de memoria ocurre en segundo plano
                thread_manager.detener_hardware()
                self.finished.emit()
            except Exception as e:
                import logging
                logging.error(f"Error asíncrono al detener hardware: {e}")
                self.finished.emit()