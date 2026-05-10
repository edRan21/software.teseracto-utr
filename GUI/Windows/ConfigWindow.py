# TESERACTO-UTR/GUI/Windows/ConfigWindow.py

import os
import json
import re
import string
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QComboBox,
    QLineEdit, QPushButton, QFormLayout, QMessageBox, QScrollArea, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIntValidator, QDoubleValidator
from Core.Hardware import ModbusUtils
from Core.System.ConfigManager import ConfigManager
from Core.System import ErrorHandler

class ConfigWindow(QWidget):
    def __init__(self, medidor, error_handler):
        super().__init__()
        self.medidor = medidor
        self.error_handler = error_handler
        self.current_profile = {}
        self.setup_ui()
        
        if self.medidor is not None:
            self.load_initial_config()
        
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        
        # === NUEVO: Grupo para selección de tipo de medidor ===
        medidor_group = QGroupBox("Tipo de Medidor")
        medidor_layout = QFormLayout()
        
        self.cmb_tipo_medidor = QComboBox()
        self.cmb_tipo_medidor.addItems(["Badger M2000", "ISOMAG MV110/MV210", "Personalizado"])
        self.cmb_tipo_medidor.currentIndexChanged.connect(self.on_tipo_medidor_changed)
        medidor_layout.addRow("Modelo del Medidor:", self.cmb_tipo_medidor)
        
        medidor_group.setLayout(medidor_layout)
        content_layout.addWidget(medidor_group)
        
        serial_group = QGroupBox("Configuración Modbus RTU")
        serial_layout = QFormLayout()
        
        self.cmb_ports = QComboBox()
        self.cmb_ports.setMinimumWidth(150)
        serial_layout.addRow("Puerto COM:", self.cmb_ports)
        
        self.cmb_baudrate = QComboBox()
        self.cmb_baudrate.addItems(["9600", "19200", "38400", "57600", "115200"])
        serial_layout.addRow("Baudrate:", self.cmb_baudrate)
        
        self.cmb_parity = QComboBox()
        self.cmb_parity.addItems(["Ninguna", "Par", "Impar"])
        serial_layout.addRow("Paridad:", self.cmb_parity)
        
        self.cmb_stopbits = QComboBox()
        self.cmb_stopbits.addItems(["1", "1.5", "2"])
        serial_layout.addRow("Bits de parada:", self.cmb_stopbits)
        
        self.txt_slave_id = QLineEdit("1")
        self.txt_slave_id.setValidator(QIntValidator(1, 247))
        serial_layout.addRow("ID Esclavo:", self.txt_slave_id)
        
        self.btn_refresh_ports = QPushButton("Detectar Puertos")
        self.btn_refresh_ports.clicked.connect(self.refresh_com_ports)
        serial_layout.addRow(self.btn_refresh_ports)
        
        serial_group.setLayout(serial_layout)
        content_layout.addWidget(serial_group)
        
        sensor_group = QGroupBox("Perfil de Medidor")
        sensor_layout = QVBoxLayout()
        
        self.cmb_profiles = QComboBox()
        self.cmb_profiles.currentIndexChanged.connect(self.load_profile)
        sensor_layout.addWidget(QLabel("Perfil Predefinido:"))
        sensor_layout.addWidget(self.cmb_profiles)
        
        self.profile_form = QFormLayout()
        self.profile_form.addRow("Modelo:", QLineEdit())
        self.profile_form.addRow("Fabricante:", QLineEdit())
        sensor_layout.addLayout(self.profile_form)
        
        endian_layout = QHBoxLayout()
        self.cmb_endianness = QComboBox()
        self.cmb_endianness.addItems(["Big", "Little"])
        endian_layout.addWidget(QLabel("Endianness:"))
        endian_layout.addWidget(self.cmb_endianness)
        
        self.cmb_word_order = QComboBox()
        self.cmb_word_order.addItems(["Big", "Little"])
        endian_layout.addWidget(QLabel("Word Order:"))
        endian_layout.addWidget(self.cmb_word_order)
        sensor_layout.addLayout(endian_layout)
        
        self.txt_esc_instant = QLineEdit("1.0")
        self.txt_esc_instant.setValidator(QDoubleValidator(0.00001, 10000.1, 5))
        sensor_layout.addWidget(QLabel("Escala Flujo Inst:"))
        sensor_layout.addWidget(self.txt_esc_instant)
        
        self.txt_esc_accum = QLineEdit("1.0")
        self.txt_esc_accum.setValidator(QDoubleValidator(0.00001, 10000.0, 5))
        sensor_layout.addWidget(QLabel("Escala Flujo Acum:"))
        sensor_layout.addWidget(self.txt_esc_accum)

        reg_group = QGroupBox("Asignación de Registros")
        reg_layout = QFormLayout()
        
        self.reg_instant = QLineEdit("241")
        self.reg_instant.setValidator(QIntValidator(0, 65535))
        reg_layout.addRow("Flujo Instantáneo:", self.reg_instant)
        
        self.reg_accumulated = QLineEdit("211")
        self.reg_accumulated.setValidator(QIntValidator(0, 65535))
        reg_layout.addRow("Flujo Acumulado:", self.reg_accumulated)

        self.chk_velocidad = QCheckBox("Habilitar Velocidad de Flujo")
        self.chk_velocidad.setChecked(True)
        self.reg_velocidad = QLineEdit("233")
        self.reg_velocidad.setValidator(QIntValidator(0, 65535))
        reg_layout.addRow(self.chk_velocidad, self.reg_velocidad)
        
        self.chk_unidad_flujo = QCheckBox("Habilitar Unidad de Flujo")
        self.chk_unidad_flujo.setCheckable(True)
        self.reg_unidad_flujo = QLineEdit("131")
        self.reg_unidad_flujo.setEnabled(False)
        self.reg_unidad_flujo.setStyleSheet("background-color: #F0F0F0;")
        reg_layout.addRow(self.chk_unidad_flujo, self.reg_unidad_flujo)
        
        self.chk_dir = QCheckBox("Habilitar Dirección de Flujo")
        self.chk_dir.setChecked(True)
        self.reg_dir = QLineEdit("301")
        self.reg_dir.setValidator(QIntValidator(0, 65535))
        reg_layout.addRow(self.chk_dir, self.reg_dir)
        
        self.chk_energizacion = QCheckBox("Habilitar Energización")
        self.chk_energizacion.setChecked(True)
        self.reg_energizacion = QLineEdit("245")
        reg_layout.addRow(self.chk_energizacion, self.reg_energizacion)
        
        self.chk_errores_sensor = QCheckBox("Habilitar Errores Sensor")
        self.chk_errores_sensor.setChecked(True)
        self.reg_errores_sensor = QLineEdit("262")
        reg_layout.addRow(self.chk_errores_sensor, self.reg_errores_sensor)
        
        self.chk_codigo_error = QCheckBox("Habilitar Código Error")
        self.chk_codigo_error.setChecked(True)
        self.reg_codigo_error = QLineEdit("257")
        reg_layout.addRow(self.chk_codigo_error, self.reg_codigo_error)
        
        reg_group.setLayout(reg_layout)
        sensor_layout.addWidget(reg_group)
        
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Guardar Perfil")
        self.btn_save.clicked.connect(self.save_profile)
        btn_layout.addWidget(self.btn_save)
        
        self.btn_apply = QPushButton("Aplicar Configuración")
        self.btn_apply.clicked.connect(self.apply_config)
        btn_layout.addWidget(self.btn_apply)
        
        sensor_layout.addLayout(btn_layout)
        sensor_group.setLayout(sensor_layout)
        content_layout.addWidget(sensor_group)
        
        self.lbl_status = QLabel("Configuración no guardada")
        self.lbl_status.setFont(QFont("Arial", 10, QFont.Bold))
        self.lbl_status.setStyleSheet("color: #E74C3C;")
        content_layout.addWidget(self.lbl_status)
        
        content_widget.setLayout(content_layout)
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)
        
        self.update_timer = QTimer()
        self.update_timer.setInterval(5000)
        self.update_timer.timeout.connect(self.refresh_com_ports)
        self.update_timer.start()

    def on_tipo_medidor_changed(self, index):
        """Cambia la configuración según el tipo de medidor seleccionado"""
        tipo_medidor = self.cmb_tipo_medidor.currentText()
        
        if tipo_medidor == "Badger M2000":
            self.cargar_configuracion_badger()
        elif tipo_medidor == "ISOMAG MV110/MV210":
            self.cargar_configuracion_isomag()
        else:  # Personalizado
            self.limpiar_formulario_personalizado()

    def cargar_configuracion_badger(self):
        """Carga configuración por defecto para Badger M2000"""
        # Preservar configuración actual del Badger
        self.cmb_endianness.setCurrentIndex(0)  # Big
        self.cmb_word_order.setCurrentIndex(0)  # Big
        
        # Direcciones Badger (las que ya funcionan)
        self.reg_instant.setText("241")
        self.reg_accumulated.setText("211")
        self.reg_velocidad.setText("233")
        self.reg_unidad_flujo.setText("131")
        self.reg_dir.setText("301")
        self.reg_energizacion.setText("245")
        self.reg_errores_sensor.setText("262")
        self.reg_codigo_error.setText("257")
        
        # Escalas por defecto Badger
        self.txt_esc_instant.setText("1.0")
        self.txt_esc_accum.setText("1.0")
        
        self.lbl_status.setText("✅ Configuración Badger M2000 cargada")
        self.lbl_status.setStyleSheet("color: #27AE60;")

    def cargar_configuracion_isomag(self):
        """Carga configuración por defecto para ISOMAG"""
        # Configuración ISOMAG según manual
        self.cmb_endianness.setCurrentIndex(0)  # Big Endian (CRÍTICO)
        self.cmb_word_order.setCurrentIndex(0)  # Big Endian (CRÍTICO)
        
        # DIRECCIONES BASE 0 según manual ISOMAG
        self.reg_instant.setText("4")        # 0004-0005: Flow rate value
        self.reg_accumulated.setText("8")    # 0008-0009: Totalizer T+ value  
        self.reg_velocidad.setText("6")      # 0006-0007: Flow speed
        self.reg_unidad_flujo.setText("37")  # 0037: Flow rate unit and decimals
        self.reg_dir.setText("20")           # 0020: Process flags (dirección en bit 5)
        self.reg_energizacion.setText("27")  # 0027: Battery capacity
        self.reg_errores_sensor.setText("20") # 0020: Process flags (errores en LSB)
        self.reg_codigo_error.setText("32")  # 0032-0033: Sensor test result code
        
        # Escalas por defecto ISOMAG
        self.txt_esc_instant.setText("1.0")
        self.txt_esc_accum.setText("1.0")
        
        # Marcar checkboxes relevantes para ISOMAG
        self.chk_velocidad.setChecked(True)
        self.chk_unidad_flujo.setChecked(True)
        self.chk_dir.setChecked(True)
        self.chk_energizacion.setChecked(True)
        self.chk_errores_sensor.setChecked(True)
        self.chk_codigo_error.setChecked(True)
        
        self.lbl_status.setText("✅ Configuración ISOMAG MV110/MV210 cargada")
        self.lbl_status.setStyleSheet("color: #27AE60;")

    def limpiar_formulario_personalizado(self):
        """Limpia el formulario para configuración personalizada"""
        self.reg_instant.clear()
        self.reg_accumulated.clear()
        self.reg_velocidad.clear()
        self.reg_unidad_flujo.clear()
        self.reg_dir.clear()
        self.reg_energizacion.clear()
        self.reg_errores_sensor.clear()
        self.reg_codigo_error.clear()
        
        self.lbl_status.setText("🛠️ Configuración personalizada - complete los campos")
        self.lbl_status.setStyleSheet("color: #3498DB;")

    class ConnectionWorker(QThread):
        finished = pyqtSignal(bool, str)
        
        def __init__(self, main_window, profile, parent=None):
            super().__init__(parent)
            self.main_window = main_window # Referencia directa a MainWindow
            self.profile = profile
        
        def run(self):
            try:
                # ✅ Llamamos a la MainWindow para que reconstruya todo
                nuevo_medidor = self.main_window.actualizar_medidor_global(self.profile)
                
                with nuevo_medidor._connection_lock:
                    success = nuevo_medidor.conectar()
                    message = "✅ Configuración aplicada" if success else "❌ Conexión fallida"
                    self.finished.emit(success, message)
            except Exception as e:
                self.finished.emit(False, f"❌ Error crítico: {str(e)}")

    def load_initial_config(self):
        if self.medidor is None:
            return
            
        QTimer.singleShot(100, self.load_profiles)
        self.refresh_com_ports()
        if self.medidor.perfil:
            self.current_profile = self.medidor.perfil
            self.show_profile(self.current_profile)

    def load_profiles(self):
        self.cmb_profiles.clear()
        try:
            profiles = ConfigManager.obtener_perfiles_predefinidos()
            self.cmb_profiles.addItem("-- Nuevo Perfil --", None)
            for profile in profiles:
                self.cmb_profiles.addItem(profile["nombre"], profile)
        except Exception as e:
            if self.error_handler:
                # APORTACIÓN 1: Uso del código oficial "CONFIG-LOAD"
                self.error_handler.log_error("CONFIG-LOAD", f"Error cargando perfiles: {e}", es_error_sistema=True)
            else:
                logging.error(f"Error cargando perfiles: {e}")

    def refresh_com_ports(self):
        current = self.cmb_ports.currentText()
        self.cmb_ports.clear()
        try:
            ports = ModbusUtils.obtener_puertos_com(only_modbus=True)
            self.cmb_ports.addItems(ports)
            if current in ports:
                self.cmb_ports.setCurrentText(current)
            elif ports:
                self.cmb_ports.setCurrentIndex(0)
        except Exception as e:
            if self.error_handler:
                # APORTACIÓN 1: Uso del código oficial "005"
                self.error_handler.log_error("005", f"Error detectando puertos COM: {e}", es_error_sistema=True)
            else:
                logging.error(f"Error detectando puertos: {e}")

    def load_profile(self, index):
        profile = self.cmb_profiles.itemData(index)
        if not profile:
            self.clear_form()
            return
        self.show_profile(profile)
        self.current_profile = profile

    def show_profile(self, profile):
        # Determinar tipo de medidor basado en el perfil
        tipo_medidor = profile.get("tipo_medidor", "Badger M2000")
        if "ISOMAG" in tipo_medidor.upper():
            self.cmb_tipo_medidor.setCurrentText("ISOMAG MV110/MV210")
        else:
            self.cmb_tipo_medidor.setCurrentText("Badger M2000")
        
        self.cmb_ports.setCurrentText(profile.get("puerto_serie", ""))
        self.cmb_baudrate.setCurrentText(str(profile.get("baudrate", 9600)))
        self.cmb_parity.setCurrentText(self.map_parity(profile.get("parity", "N")))
        self.cmb_stopbits.setCurrentText(str(profile.get("stopbits", 1)))
        self.txt_slave_id.setText(str(profile.get("slave_id", 1)))
        
        # Cargar configuración de endianness y word_order
        endianness = profile.get("endianness", "big").lower()
        if endianness == "big":
            self.cmb_endianness.setCurrentIndex(0)  # "Big"
        else:
            self.cmb_endianness.setCurrentIndex(1)  # "Little"

        word_order = profile.get("word_order", "big").lower()
        if word_order == "big":
            self.cmb_word_order.setCurrentIndex(0)  # "Big"
        else:
            self.cmb_word_order.setCurrentIndex(1)  # "Little"
            
        for i in range(self.profile_form.rowCount()):
            widget = self.profile_form.itemAt(i, QFormLayout.FieldRole).widget()
            if isinstance(widget, QLineEdit):
                if i == 0:
                    widget.setText(profile.get("modelo", ""))
                elif i == 1:
                    widget.setText(profile.get("fabricante", ""))
        
        registros = profile.get("registros", {})
        self.reg_instant.setText(str(registros.get("flujo_instantaneo", {}).get("address", 241)))
        self.reg_velocidad.setText(str(registros.get("velocidad_flujo", {}).get("address", 233)))
        self.reg_unidad_flujo.setText(str(registros.get("unidad_flujo", {}).get("address", 131)))
        self.chk_unidad_flujo.setChecked("unidad_flujo" in registros)
        self.reg_accumulated.setText(str(registros.get("flujo_acumulado", {}).get("address", 211)))
        self.reg_dir.setText(str(registros.get("direccion_flujo", {}).get("address", 301)))
        self.reg_energizacion.setText(str(registros.get("contador_energizacion", {}).get("address", 245)))
        self.reg_errores_sensor.setText(str(registros.get("errores_sensor", {}).get("address", 262)))
        self.reg_codigo_error.setText(str(registros.get("codigo_error", {}).get("address", 257)))
        
        self.txt_esc_instant.setText(str(registros.get("flujo_instantaneo", {}).get("escala", 0.001)))
        self.txt_esc_accum.setText(str(registros.get("flujo_acumulado", {}).get("escala", 1.0)))
        
        self.lbl_status.setText("Perfil cargado")
        self.lbl_status.setStyleSheet("color: #27AE60;")

    def map_parity(self, parity_char):
        mapping = {"N": "Ninguna", "E": "Par", "O": "Impar"}
        return mapping.get(parity_char.upper(), "Ninguna")

    def unmap_parity(self, text):
        mapping = {"Ninguna": "N", "Par": "E", "Impar": "O"}
        return mapping.get(text, "N")

    def clear_form(self):
        self.cmb_ports.setCurrentIndex(0)
        self.cmb_baudrate.setCurrentIndex(0)
        self.cmb_parity.setCurrentIndex(0)
        self.cmb_stopbits.setCurrentIndex(0)
        self.txt_slave_id.setText("1")
        
        # Configuración por defecto según Badger M2000
        self.cmb_endianness.setCurrentIndex(0)  # "Big" - Big-Endian
        self.cmb_word_order.setCurrentIndex(0)  # "Big" - Big-Endian
        
        for i in range(self.profile_form.rowCount()):
            widget = self.profile_form.itemAt(i, QFormLayout.FieldRole).widget()
            if isinstance(widget, QLineEdit):
                widget.clear()
        
        self.reg_instant.setText("241")
        self.reg_accumulated.setText("211")
        self.reg_velocidad.setText("233")
        self.reg_unidad_flujo.setText("131")
        self.reg_dir.setText("301")
        self.reg_energizacion.setText("245")
        self.reg_errores_sensor.setText("262")
        self.reg_codigo_error.setText("257")
        
        self.current_profile = {}
        self.lbl_status.setText("Listo para nuevo perfil")
        self.lbl_status.setStyleSheet("color: #3498DB;")

    def save_profile(self):
        try:
            modelo = self.profile_form.itemAt(0, QFormLayout.FieldRole).widget().text()
            if not modelo.strip():
                raise ValueError("El modelo no puede estar vacío")
                
            campos_numericos = {
                "Flujo Instantáneo": self.reg_instant,
                "Flujo Acumulado": self.reg_accumulated,
                "Velocidad de Flujo": self.reg_velocidad,
                "Dirección de Flujo": self.reg_dir,
                "Energización": self.reg_energizacion,
                "Errores Sensor": self.reg_errores_sensor,
                "Código Error": self.reg_codigo_error,
                "ID Esclavo": self.txt_slave_id
            }
            
            for nombre, campo in campos_numericos.items():
                if not campo.text().strip():
                    raise ValueError(f"El campo '{nombre}' no puede estar vacío")
                try:
                    int(campo.text())
                except ValueError:
                    raise ValueError(f"Valor inválido en '{nombre}': debe ser un número entero")
            
            try:
                float(self.txt_esc_instant.text())
                float(self.txt_esc_accum.text())
            except ValueError:
                raise ValueError("Las escalas deben ser valores numéricos")
            
            profile = self.collect_form_data()
            ConfigManager.guardar_perfil_sensor(profile, es_nuevo=True)
            self.load_profiles()
            
            self.lbl_status.setText("✅ Perfil guardado exitosamente")
            self.lbl_status.setStyleSheet("color: #27AE60;")
            
        except Exception as e:
            # APORTACIÓN 1: Uso del código oficial "CONFIG-SAVE"
            self.error_handler.log_error("CONFIG-SAVE", f"Error guardando perfil: {e}", es_error_sistema=True)
            self.lbl_status.setText(f"❌ Error: {str(e)}")
            self.lbl_status.setStyleSheet("color: #E74C3C;")
            
            QMessageBox.critical(
                self,
                "Error al guardar",
                f"No se pudo guardar el perfil:\n\n{str(e)}",
                QMessageBox.Ok
            )

    def apply_config(self):
        try:
            if not self.cmb_ports.currentText():
                raise ValueError("Seleccione un puerto COM")
                
            campos_numericos = {
                "ID Esclavo": self.txt_slave_id,
                "Flujo Instantáneo": self.reg_instant,
                "Flujo Acumulado": self.reg_accumulated,
                "Velocidad de Flujo": self.reg_velocidad,
                "Dirección de Flujo": self.reg_dir,
                "Energización": self.reg_energizacion,
                "Errores Sensor": self.reg_errores_sensor,
                "Código Error": self.reg_codigo_error
            }
            
            for nombre, campo in campos_numericos.items():
                if not campo.text().strip():
                    raise ValueError(f"El campo '{nombre}' no puede estar vacío")
                try:
                    valor = int(campo.text())
                    if not (0 <= valor <= 65535):
                        raise ValueError(f"Valor inválido en '{nombre}': debe estar entre 0-65535")
                except ValueError:
                    raise ValueError(f"Valor inválido en '{nombre}': debe ser un número entero")
            
            try:
                float(self.txt_esc_instant.text())
                float(self.txt_esc_accum.text())
            except ValueError:
                raise ValueError("Las escalas deben ser valores numéricos")
            
            profile = self.collect_form_data()
            
            self.setEnabled(False)
            self.lbl_status.setText("Aplicando configuración...")
            self.lbl_status.setStyleSheet("color: #3498DB;")
            
            # ✅ self.window() obtiene la MainWindow y se la pasamos al hilo
            self.worker = self.ConnectionWorker(self.window(), profile)
            self.worker.finished.connect(self.handle_connection_result)
            self.worker.start()
            
        except Exception as e:
            self.handle_connection_error(e)

    def handle_connection_result(self, success, message):
        self.setEnabled(True)
        self.lbl_status.setText(message)
        self.lbl_status.setStyleSheet("color: #27AE60;" if success else "color: #E74C3C;")
        
        if success:
            QTimer.singleShot(500, self.force_initial_read)

    def handle_connection_error(self, error):
        self.setEnabled(True)
        # APORTACIÓN 1: Uso del código oficial "007"
        self.error_handler.log_error("007", f"Error aplicando configuración Modbus: {error}", es_error_sistema=True)
        self.lbl_status.setText(f"❌ Error: {str(error)}")
        self.lbl_status.setStyleSheet("color: #E74C3C;")
        
        QMessageBox.critical(
            self,
            "Error de Conexión",
            f"No se pudo aplicar la configuración:\n\n{str(error)}\n\n"
            "Verifique los parámetros de conexión e intente nuevamente.",
            QMessageBox.Ok
        )
    
    def collect_form_data(self):
        tipo_medidor = self.cmb_tipo_medidor.currentText()
        
        if tipo_medidor == "ISOMAG MV110/MV210":
            return self._collect_isomag_data()
        else:  # Badger M2000 y Personalizado
            return self._collect_generic_data()

    def _collect_isomag_data(self):
        """Recopila datos específicos para ISOMAG"""
        profile = {
            "puerto_serie": self.cmb_ports.currentText(),
            "baudrate": int(self.cmb_baudrate.currentText()),
            "parity": self.unmap_parity(self.cmb_parity.currentText()),
            "stopbits": float(self.cmb_stopbits.currentText()),
            "bytesize": 8,
            "timeout": 5.0,
            "slave_id": int(self.txt_slave_id.text()),
            "endianness": "big",  # FIJO para ISOMAG
            "word_order": "big",   # FIJO para ISOMAG  
            "funcion_default": 4,  # FIJO para ISOMAG
            "modelo": "ISOMAG MV110/MV210",
            "fabricante": "ISOL INDUSTRIA",
            "tipo_medidor": "ISOMAG",
            "registros": {
                "flujo_instantaneo": {
                    "address": int(self.reg_instant.text()),
                    "count": 2,
                    "data_type": "float32",
                    "escala": float(self.txt_esc_instant.text()),
                    "unidad": "m³/s",
                    "funcion": 4
                },
                "flujo_acumulado": {
                    "address": int(self.reg_accumulated.text()),
                    "count": 2,
                    "data_type": "uint32",
                    "escala": float(self.txt_esc_accum.text()),
                    "unidad": "m³", 
                    "funcion": 4
                }
            }
        }
        
        # Agregar registros opcionales para ISOMAG
        if self.chk_velocidad.isChecked():
            profile["registros"]["velocidad_flujo"] = {
                "address": int(self.reg_velocidad.text()),
                "count": 2,
                "data_type": "float32",
                "funcion": 4
            }

        if self.chk_unidad_flujo.isChecked():
            profile["registros"]["unidad_flujo"] = {
                "address": int(self.reg_unidad_flujo.text()),
                "count": 1,
                "data_type": "int16", 
                "no_escalar": True,
                "funcion": 4
            }
        
        # Manejo especial de flags para ISOMAG
        if self.chk_dir.isChecked() or self.chk_errores_sensor.isChecked():
            profile["registros"]["flags_proceso"] = {
                "address": 20,
                "count": 1,
                "data_type": "isomag_flags",
                "funcion": 4
            }
        
        return profile

    def _collect_generic_data(self):
        """Recopila datos para Badger M2000 y configuraciones personalizadas"""
        profile = {
            "puerto_serie": self.cmb_ports.currentText(),
            "baudrate": int(self.cmb_baudrate.currentText()),
            "parity": self.unmap_parity(self.cmb_parity.currentText()),
            "stopbits": float(self.cmb_stopbits.currentText()),
            "bytesize": 8,
            "timeout": 5.0,
            "slave_id": int(self.txt_slave_id.text()),
            "endianness": self.cmb_endianness.currentText().lower(),
            "word_order": self.cmb_word_order.currentText().lower(),
            "funcion_default": 4,
            "modelo": self.profile_form.itemAt(0, QFormLayout.FieldRole).widget().text(),
            "fabricante": self.profile_form.itemAt(1, QFormLayout.FieldRole).widget().text(),
            "tipo_medidor": self.cmb_tipo_medidor.currentText(),
            "registros": {
                "flujo_instantaneo": {
                    "address": int(self.reg_instant.text()),
                    "count": 2,
                    "data_type": "float32",
                    "escala": float(self.txt_esc_instant.text()),
                    "unidad": "m³/s",
                    "funcion": 4
                },
                "flujo_acumulado": {
                    "address": int(self.reg_accumulated.text()),
                    "count": 2,
                    "data_type": "float32",
                    "escala": float(self.txt_esc_accum.text()),
                    "unidad": "m³",
                    "funcion": 4
                }
            },
            "output_mapping": {
                "flujo_instantaneo": "flujo_instantaneo",
                "flujo_acumulado": "flujo_acumulado",
                "direccion_flujo": "direccion_flujo"
            }
        }
        
        if self.chk_velocidad.isChecked():
            profile["registros"]["velocidad_flujo"] = {
                "address": int(self.reg_velocidad.text()),
                "count": 2,
                "data_type": "float32",
                "funcion": 4
            }
            profile["output_mapping"]["velocidad_flujo"] = "velocidad_flujo"

        if self.chk_unidad_flujo.isChecked():
            profile["registros"]["unidad_flujo"] = {
                "address": int(self.reg_unidad_flujo.text()),
                "count": 1,
                "data_type": "int16",
                "no_escalar": True,
                "funcion": 4
            }
        
        if self.chk_dir.isChecked():
            profile["registros"]["direccion_flujo"] = {
                "address": int(self.reg_dir.text()),
                "count": 1,
                "data_type": "int16",
                "funcion": 4
            }
        
        if self.chk_energizacion.isChecked():
            profile["registros"]["contador_energizacion"] = {
                "address": int(self.reg_energizacion.text()),
                "count": 1,
                "data_type": "int16",
                "funcion": 4
            }
        
        if self.chk_errores_sensor.isChecked():
            profile["registros"]["errores_sensor"] = {
                "address": int(self.reg_errores_sensor.text()),
                "count": 1,
                "data_type": "error",
                "funcion": 4
            }
        
        if self.chk_codigo_error.isChecked():
            profile["registros"]["codigo_error"] = {
                "address": int(self.reg_codigo_error.text()),
                "count": 1,
                "data_type": "int16",
                "funcion": 4
            }
        
        return profile
    
    def force_initial_read(self):
        try:
            if self.medidor.leer_registros():
                self.lbl_status.setText("✅ Lectura inicial exitosa")
        except Exception as e:
            # APORTACIÓN 2: Evitar error silencioso enviando al notificador
            self.error_handler.log_error("007", f"Error en lectura inicial de prueba: {str(e)}", es_error_sistema=True)
            self.lbl_status.setText(f"⚠️ Error en lectura: {str(e)}")
            self.lbl_status.setStyleSheet("color: #E67E22;")

    def closeEvent(self, event):
        self.update_timer.stop()
        super().closeEvent(event)