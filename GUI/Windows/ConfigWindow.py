# TESERACTO-UTR/GUI/Windows/ConfigWindow.py

import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QComboBox,
    QLineEdit, QPushButton, QFormLayout, QMessageBox, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIntValidator, QDoubleValidator
from PyQt5.QtCore import QLocale

from Core.Hardware import ModbusUtils
from Core.System.ConfigManager import ConfigManager
from Core.System.ThreadManager import thread_manager

class ConfigWindow(QWidget):
    def __init__(self, error_handler):
        super().__init__()
        self.error_handler = error_handler
        self.perfil_json_actual = {} 
        self.setup_ui()
        self.load_initial_config()
        
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        
        # =========================================================
        # 1. SELECCIÓN DE PERFIL BASE
        # =========================================================
        perfil_group = QGroupBox("1. Modelo del Medidor")
        perfil_layout = QVBoxLayout()
        self.cmb_profiles = QComboBox()
        self.cmb_profiles.currentIndexChanged.connect(self.cargar_datos_del_perfil)
        perfil_layout.addWidget(self.cmb_profiles)
        perfil_group.setLayout(perfil_layout)
        content_layout.addWidget(perfil_group)
        
        # =========================================================
        # 2. CONFIGURACIÓN FÍSICA Y PROTOCOLO
        # =========================================================
        serial_group = QGroupBox("2. Parámetros de Comunicación")
        serial_layout = QFormLayout()
        
        self.cmb_ports = QComboBox()
        self.cmb_ports.setMinimumWidth(150)
        port_layout = QHBoxLayout()
        port_layout.addWidget(self.cmb_ports)
        self.btn_refresh_ports = QPushButton("🔄 Actualizar")
        self.btn_refresh_ports.clicked.connect(self.refresh_com_ports)
        port_layout.addWidget(self.btn_refresh_ports)
        
        serial_layout.addRow("Puerto COM:", port_layout)
        
        self.cmb_baudrate = QComboBox()
        self.cmb_baudrate.addItems(["9600", "19200", "38400", "57600", "115200"])
        serial_layout.addRow("Baudrate:", self.cmb_baudrate)
        
        self.cmb_parity = QComboBox()
        self.cmb_parity.addItems(["Ninguna", "Par", "Impar"])
        serial_layout.addRow("Paridad:", self.cmb_parity)
        
        self.cmb_stopbits = QComboBox()
        self.cmb_stopbits.addItems(["1", "1.5", "2"])
        serial_layout.addRow("Bits de parada:", self.cmb_stopbits)
        
        # --- NUEVO: TAMAÑO DE BIT (BYTESIZE) ---
        self.cmb_bytesize = QComboBox()
        self.cmb_bytesize.addItems(["7", "8"])
        serial_layout.addRow("Tamaño de datos (Bits):", self.cmb_bytesize)
        
        self.txt_slave_id = QLineEdit("1")
        self.txt_slave_id.setValidator(QIntValidator(1, 247))
        serial_layout.addRow("ID Esclavo:", self.txt_slave_id)
        
        # --- LOS CONTROLES DE DECODIFICACIÓN MODBUS RESTAURADOS ---
        self.cmb_endianness = QComboBox()
        self.cmb_endianness.addItems(["Big", "Little"])
        serial_layout.addRow("Endianness (Byte Order):", self.cmb_endianness)
        
        self.cmb_word_order = QComboBox()
        self.cmb_word_order.addItems(["Big", "Little"])
        serial_layout.addRow("Word Order (Reg Order):", self.cmb_word_order)
        
        serial_group.setLayout(serial_layout)
        content_layout.addWidget(serial_group)
        
        # =========================================================
        # 3. VISTA PREVIA DEL MAPA DE REGISTROS (Solo Lectura)
        # =========================================================
        # ¡AQUÍ ESTÁ LA LÍNEA QUE OLVIDÉ DECLARAR!
        self.reg_group = QGroupBox("3. Mapa de Registros (Solo Lectura)")
        self.reg_layout = QFormLayout()
        self.reg_group.setLayout(self.reg_layout)
        content_layout.addWidget(self.reg_group)
        
        # =========================================================
        # 4. ESCALAS DE CALIBRACIÓN MATEMÁTICA
        # =========================================================
        escalas_group = QGroupBox("4. Calibración y Escalas")
        escalas_layout = QFormLayout()
        
        # Creamos un validador estricto que obliga a usar PUNTO (.) y solo acepta números
        validador_escala = QDoubleValidator(0.00000, 100000.0, 6)
        validador_escala.setLocale(QLocale(QLocale.English)) 
        
        self.txt_esc_instant = QLineEdit("1.0")
        self.txt_esc_instant.setValidator(validador_escala) # Bloquea letras en tiempo real
        escalas_layout.addRow("Escala Flujo Instantáneo:", self.txt_esc_instant)
        
        self.txt_esc_accum = QLineEdit("1.0")
        self.txt_esc_accum.setValidator(validador_escala) # Bloquea letras en tiempo real
        escalas_layout.addRow("Escala Flujo Acumulado:", self.txt_esc_accum)
        
        escalas_group.setLayout(escalas_layout)
        content_layout.addWidget(escalas_group)
        
        # =========================================================
        # 5. CONTROLES DE APLICACIÓN ASÍNCRONA
        # =========================================================
        self.btn_apply = QPushButton("💾 Aplicar y Probar Conexión")
        self.btn_apply.setStyleSheet("background-color: #2E86C1; color: white; font-weight: bold; padding: 10px; font-size: 11pt;")
        self.btn_apply.clicked.connect(self.apply_and_test_config)
        content_layout.addWidget(self.btn_apply)
        
        self.lbl_status = QLabel("Listo.")
        self.lbl_status.setFont(QFont("Arial", 11, QFont.Bold))
        self.lbl_status.setStyleSheet("color: #F39C12;")
        content_layout.addWidget(self.lbl_status)
        
        content_widget.setLayout(content_layout)
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)
        
        self.update_timer = QTimer()
        self.update_timer.setInterval(5000)
        self.update_timer.timeout.connect(self.refresh_com_ports)
        self.update_timer.start()

    def load_initial_config(self):
        self.refresh_com_ports()
        self.cmb_profiles.clear()
        try:
            perfiles = ConfigManager.obtener_perfiles_predefinidos()
            for perfil in perfiles:
                self.cmb_profiles.addItem(perfil["nombre"], perfil)
                
            poller = thread_manager.modbus_poller
            if poller and poller.medidor and poller.medidor.perfil:
                perfil_activo = poller.medidor.perfil
                
                # Buscar el perfil
                index = self.cmb_profiles.findText(perfil_activo.get("nombre", ""))
                if index >= 0:
                    self.cmb_profiles.setCurrentIndex(index)
                    
                # Rellenar con los valores en memoria (Overrides locales)
                self.cmb_ports.setCurrentText(perfil_activo.get("puerto_serie", ""))
                self.cmb_baudrate.setCurrentText(str(perfil_activo.get("baudrate", 9600)))
                self.txt_slave_id.setText(str(perfil_activo.get("slave_id", 1)))
                self.cmb_parity.setCurrentText(self.map_parity(perfil_activo.get("parity", "N")))
                self.cmb_bytesize.setCurrentText(str(perfil_activo.get("bytesize", 8)))
                
                if perfil_activo.get("endianness", "big").lower() == "big": self.cmb_endianness.setCurrentIndex(0)
                else: self.cmb_endianness.setCurrentIndex(1)
                
                if perfil_activo.get("word_order", "big").lower() == "big": self.cmb_word_order.setCurrentIndex(0)
                else: self.cmb_word_order.setCurrentIndex(1)
                
                registros = perfil_activo.get("registros", {})
                self.txt_esc_instant.setText(str(registros.get("flujo_instantaneo", {}).get("escala", 1.0)))
                self.txt_esc_accum.setText(str(registros.get("flujo_acumulado", {}).get("escala", 1.0)))
                    
        except Exception as e:
            self.error_handler.log_error("CONFIG-LOAD", f"Error cargando perfiles: {e}", es_error_sistema=True)

    def refresh_com_ports(self):
        current = self.cmb_ports.currentText()
        self.cmb_ports.clear()
        try:
            ports = ModbusUtils.obtener_puertos_com(only_modbus=True)
            self.cmb_ports.addItems(ports)
            if current in ports:
                self.cmb_ports.setCurrentText(current)
        except Exception:
            pass

    def cargar_datos_del_perfil(self, index):
        """Precarga parámetros y dibuja el mapa de registros con contraste corregido."""
        perfil = self.cmb_profiles.itemData(index)
        if not perfil: 
            return
            
        self.perfil_json_actual = perfil
        
        perfiles_maestros = ConfigManager.obtener_perfiles_sensores()
        maestro = next((p for p in perfiles_maestros if p.get("tipo_medidor") == perfil.get("tipo_medidor")), None)
        
        regs_referencia = {}
        
        if maestro:
            if maestro.get("endianness", "big").lower() == "big": self.cmb_endianness.setCurrentIndex(0)
            else: self.cmb_endianness.setCurrentIndex(1)
            
            if maestro.get("word_order", "big").lower() == "big": self.cmb_word_order.setCurrentIndex(0)
            else: self.cmb_word_order.setCurrentIndex(1)
            
            regs_referencia = maestro.get("registros", {})
            funcion_default = maestro.get("funcion_default", 4)
        else:
            defaults = perfil.get("config_defaults", {})
            if defaults.get("endianness", "big").lower() == "big": self.cmb_endianness.setCurrentIndex(0)
            else: self.cmb_endianness.setCurrentIndex(1)
            
            if defaults.get("word_order", "big").lower() == "big": self.cmb_word_order.setCurrentIndex(0)
            else: self.cmb_word_order.setCurrentIndex(1)
            
            regs_referencia = perfil.get("registros_mapping", {})
            funcion_default = defaults.get("funcion_default", 4)

        self.txt_esc_instant.setText(str(regs_referencia.get("flujo_instantaneo", {}).get("escala", 1.0)))
        self.txt_esc_accum.setText(str(regs_referencia.get("flujo_acumulado", {}).get("escala", 1.0)))

        while self.reg_layout.rowCount() > 0:
            self.reg_layout.removeRow(0)
                
        registros_habilitados = perfil.get("registros_habilitados", [])
        
        for nombre_reg in registros_habilitados:
            if nombre_reg in regs_referencia:
                data = regs_referencia[nombre_reg]
                direccion = data.get("address", "N/A")
                tipo = data.get("data_type", "N/A")
                funcion = data.get("funcion", funcion_default)
                
                # CORRECCIÓN DE CONTRASTE: Uso de #333333 (Gris oscuro/Negro)
                lbl_info = QLabel(f"Dir: {direccion} | Tipo: {tipo} | FC: {funcion}")
                lbl_info.setStyleSheet("color: #333333; font-size: 10pt; font-family: Consolas; font-weight: bold;")
                
                nombre_visual = nombre_reg.replace("_", " ").title()
                
                lbl_nombre = QLabel(f"✔️ {nombre_visual}:")
                lbl_nombre.setStyleSheet("color: #333333; font-size: 10pt;")
                
                self.reg_layout.addRow(lbl_nombre, lbl_info)
    
    def map_parity(self, parity_char):
        return {"N": "Ninguna", "E": "Par", "O": "Impar"}.get(parity_char.upper(), "Ninguna")

    def unmap_parity(self, text):
        return {"Ninguna": "N", "Par": "E", "Impar": "O"}.get(text, "N")

    def apply_and_test_config(self):
        try:
            if not self.cmb_ports.currentText():
                raise ValueError("Seleccione un puerto COM físico válido.")
            if not self.txt_slave_id.text().strip():
                raise ValueError("El ID de Esclavo no puede estar vacío.")

            perfil_final = self._fusionar_configuracion()
            config_completa = ConfigManager.cargar_config_sensor()
            
            # 1. Deshabilitar todos los sensores actuales para asegurar que solo uno quede activo
            for s in config_completa.get("sensores", []):
                s["habilitado"] = False
                
            # 2. Buscar el sensor en el arreglo maestro y actualizar sus parámetros
            encontrado = False
            for i, s in enumerate(config_completa.get("sensores", [])):
                if s.get("tipo_medidor") == perfil_final["tipo_medidor"]:
                    config_completa["sensores"][i] = perfil_final
                    config_completa["sensores"][i]["habilitado"] = True
                    encontrado = True
                    break
                    
            # 3. Si por alguna razón no existe, se inyecta de forma segura
            if not encontrado:
                perfil_final["habilitado"] = True
                config_completa.setdefault("sensores", []).append(perfil_final)
                
            ConfigManager.guardar_config_sensor(config_completa)

            # Bloqueo de UI e inicio de prueba en segundo plano
            self.btn_apply.setEnabled(False)
            self.lbl_status.setText("Guardado. Iniciando lectura de prueba...")
            self.lbl_status.setStyleSheet("color: #F39C12;")
            
            self.worker = self.ConnectionWorker(self.window(), perfil_final)
            self.worker.finished.connect(self.handle_connection_result)
            self.worker.start()
            
        except Exception as e:
            self.handle_connection_error(e)

    def _fusionar_configuracion(self):
        """
        Ensambla el perfil de ejecución inyectando parámetros físicos y escalares,
        preservando la inmutabilidad de la plantilla maestra de registros.
        """
        tipo_medidor = self.perfil_json_actual.get("tipo_medidor")
        perfiles_maestros = ConfigManager.obtener_perfiles_sensores()
        maestro = next((p for p in perfiles_maestros if p["tipo_medidor"] == tipo_medidor), None)
        
        if not maestro:
            raise ValueError(f"Medidor maestro '{tipo_medidor}' no hallado en la estructura base")
            
        perfil_fusionado = dict(maestro)
        
        # 1. Inyección de parámetros de capa física y enlace de datos
        perfil_fusionado["nombre"] = self.perfil_json_actual.get("nombre", tipo_medidor)
        perfil_fusionado["puerto_serie"] = self.cmb_ports.currentText()
        perfil_fusionado["baudrate"] = int(self.cmb_baudrate.currentText())
        perfil_fusionado["parity"] = self.unmap_parity(self.cmb_parity.currentText())
        perfil_fusionado["stopbits"] = float(self.cmb_stopbits.currentText())
        perfil_fusionado["slave_id"] = int(self.txt_slave_id.text())
        perfil_fusionado["bytesize"] = int(self.cmb_bytesize.currentText())
        
        # 2. Inyección de ordenamiento de bytes (Endianness / IEEE 754)
        perfil_fusionado["endianness"] = self.cmb_endianness.currentText().lower()
        perfil_fusionado["word_order"] = self.cmb_word_order.currentText().lower()
        
        # 3. Inyección del vector de enrutamiento para la RAM
        # Esto instruye al motor Modbus sobre qué registros leer, sin borrar el resto
        registros_habilitados = self.perfil_json_actual.get("registros_habilitados", [])
        perfil_fusionado["registros_habilitados"] = registros_habilitados
        
        # 4. Inyección de magnitudes escalares con validación estricta
        for reg_name, reg_data in perfil_fusionado.get("registros", {}).items():
            if reg_name == "flujo_instantaneo":
                try:
                    reg_data["escala"] = float(self.txt_esc_instant.text().strip())
                except ValueError:
                    raise ValueError("Magnitud escalar inválida para Flujo Instantáneo. Formato requerido: punto flotante (ej. 1.0, 0.001)")
                    
            elif reg_name == "flujo_acumulado":
                try:
                    reg_data["escala"] = float(self.txt_esc_accum.text().strip())
                except ValueError:
                    raise ValueError("Magnitud escalar inválida para Flujo Acumulado. Formato requerido: punto flotante (ej. 1.0, 0.001)")
                
        return perfil_fusionado

    def handle_connection_result(self, success, message):
        self.btn_apply.setEnabled(True)
        self.lbl_status.setText(message)
        self.lbl_status.setStyleSheet("color: #27AE60;" if success else "color: #E74C3C;")
        if not success:
            QMessageBox.warning(self, "Hardware", message)
            self.error_handler.log_error("007", message, es_error_sistema=True)

    def handle_connection_error(self, error):
        self.btn_apply.setEnabled(True)
        self.lbl_status.setText(f"❌ Error: {str(error)}")
        self.lbl_status.setStyleSheet("color: #E74C3C;")
        QMessageBox.critical(self, "Error", str(error))

    def closeEvent(self, event):
        self.update_timer.stop()
        super().closeEvent(event)

    class ConnectionWorker(QThread):
        finished = pyqtSignal(bool, str)
        
        def __init__(self, main_window, profile, parent=None):
            super().__init__(parent)
            self.main_window = main_window
            self.profile = profile
        
        def run(self):
            try:
                nuevo_medidor = self.main_window.actualizar_medidor_global(self.profile)
                with nuevo_medidor._connection_lock:
                    if not nuevo_medidor.conectar():
                        self.finished.emit(False, "Fallo al abrir Puerto COM.")
                        return
                    
                    # Lectura asíncrona que NO congela la pantalla principal
                    datos = nuevo_medidor.leer_registros_seguro(timeout=2.0)
                    
                    if datos and any(v is not None for v in datos.values()):
                        self.finished.emit(True, "✅ Hardware detectado y leyendo correctamente.")
                    else:
                        self.finished.emit(False, "COM abierto, pero el medidor no respondió (TimeOut).")
                    nuevo_medidor.desconectar()
            except Exception as e:
                self.finished.emit(False, f"Error asíncrono: {str(e)}")