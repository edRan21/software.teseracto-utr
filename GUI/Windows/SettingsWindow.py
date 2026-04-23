# TESERACTO-UTR/GUI/Windows/SettingsWindow.py 

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton, QMessageBox, QFileDialog, QTimeEdit
from PyQt5.QtCore import pyqtSignal, QTime
from Core.System.ConfigManager import ConfigManager
from Core.System.StateManager import StateManager

class SettingsWindow(QWidget):
    config_updated = pyqtSignal()
    
    # APORTACIÓN 1: Inyectar error_handler
    def __init__(self, error_handler=None):
        super().__init__()
        self.error_handler = error_handler
        self.setWindowTitle("Configuración del Sistema")
        self.setup_ui()
        self.load_current_config()
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Selector de unidad de medición
        unit_layout = QHBoxLayout()
        unit_label = QLabel("Unidad de Flujo Instantáneo:")
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["L/s", "m³/h", "GPM"])
        unit_layout.addWidget(unit_label)
        unit_layout.addWidget(self.unit_combo)
        main_layout.addLayout(unit_layout)
        
        # Campo para RFC
        rfc_layout = QHBoxLayout()
        rfc_label = QLabel("RFC:")
        self.rfc_input = QLineEdit()
        self.rfc_input.setPlaceholderText("Ejemplo: XAXX010101000")
        rfc_layout.addWidget(rfc_label)
        rfc_layout.addWidget(self.rfc_input)
        main_layout.addLayout(rfc_layout)
        
        # Campos NSM y NSUE
        nsm_layout = QHBoxLayout()
        nsm_label = QLabel("Número Serie Medidor (NSM):")
        self.nsm_input = QLineEdit()
        nsm_layout.addWidget(nsm_label)
        nsm_layout.addWidget(self.nsm_input)
        main_layout.addLayout(nsm_layout)
        
        nsue_layout = QHBoxLayout()
        nsue_label = QLabel("Número Serie UE (NSUE):")
        self.nsue_input = QLineEdit()
        nsue_layout.addWidget(nsue_label)
        nsue_layout.addWidget(self.nsue_input)
        main_layout.addLayout(nsue_layout)
        
        # ✅ NUEVO: Campo para NSUT (Número Serie Unidad Telemetría)
        nsut_layout = QHBoxLayout()
        nsut_label = QLabel("Número Serie Unidad Telemetría (NSUT):")
        self.nsut_input = QLineEdit()
        self.nsut_input.setPlaceholderText("Ejemplo: TSRA-001")
        nsut_layout.addWidget(nsut_label)
        nsut_layout.addWidget(self.nsut_input)
        main_layout.addLayout(nsut_layout)
        
        # Campos para coordenadas
        lat_layout = QHBoxLayout()
        lat_label = QLabel("Latitud:")
        self.lat_input = QLineEdit()
        self.lat_input.setPlaceholderText("Ejemplo: 19.4326")
        lat_layout.addWidget(lat_label)
        lat_layout.addWidget(self.lat_input)
        main_layout.addLayout(lat_layout)
        
        long_layout = QHBoxLayout()
        long_label = QLabel("Longitud:")
        self.long_input = QLineEdit()
        self.long_input.setPlaceholderText("Ejemplo: -99.1332")
        long_layout.addWidget(long_label)
        long_layout.addWidget(self.long_input)
        main_layout.addLayout(long_layout)
        
        # Configuración USB
        usb_layout = QHBoxLayout()
        usb_label = QLabel("Ruta de Almacenamiento Acumulativo:")
        self.usb_input = QLineEdit()
        self.usb_input.setPlaceholderText("Ejemplo: D:\\TesseractData")
        usb_layout.addWidget(usb_label)
        usb_layout.addWidget(self.usb_input)
        
        self.btn_browse = QPushButton("Examinar...")
        self.btn_browse.clicked.connect(self.browse_usb_path)
        usb_layout.addWidget(self.btn_browse)
        main_layout.addLayout(usb_layout)
        
        # Hora programada reporte
        time_layout = QHBoxLayout()
        time_label = QLabel("Hora Reporte Diario (HH:MM):")
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        time_layout.addWidget(time_label)
        time_layout.addWidget(self.time_edit)
        main_layout.addLayout(time_layout)
        
        # Botones
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Guardar")
        self.save_button.clicked.connect(self.save_config)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.close)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)
        
        main_layout.addStretch()
        self.setLayout(main_layout)
    
    def browse_usb_path(self):
        path = QFileDialog.getExistingDirectory(self, "Seleccionar Directorio USB", "C:\\")
        if path:
            path = path.replace('/', '\\')
            self.usb_input.setText(path)
    
    def load_current_config(self):
        try:
            config = ConfigManager.cargar_config_general()
            self.rfc_input.setText(config.get("RFC", ""))
            self.lat_input.setText(str(config.get("Lat", "")))
            self.long_input.setText(str(config.get("Long", "")))
            self.nsm_input.setText(config.get("NSM", ""))
            self.nsue_input.setText(config.get("NSUE", ""))
            # ✅ CARGAR NSUT
            self.nsut_input.setText(config.get("NSUT", ""))
            
            unit = config.get("unidad_visualizacion", "L/s")
            index = self.unit_combo.findText(unit)
            if index >= 0:
                self.unit_combo.setCurrentIndex(index)
            else:
                self.unit_combo.setCurrentText("L/s")
            
            usb_path = config.get("storage_path", "D:\\TesseractData")
            self.usb_input.setText(usb_path)

            hora_reporte = config.get("hora_reporte", "23:00")
            hora, minuto = map(int, hora_reporte.split(':'))
            self.time_edit.setTime(QTime(hora, minuto))
            
        except Exception as e:
            # APORTACIÓN 2: Registrar error de carga
            if hasattr(self, 'error_handler') and self.error_handler:
                self.error_handler.log_error("CONFIG-LOAD", f"Error cargando configuración general: {e}", es_error_sistema=True)
            QMessageBox.warning(self, "Error", f"No se pudo cargar la configuración: {e}")
    
    def save_config(self):
        try:
            rfc = self.rfc_input.text().strip()
            lat = self.lat_input.text().strip()
            long = self.long_input.text().strip()
            unit = self.unit_combo.currentText()
            usb_path = self.usb_input.text().strip()
            nsm = self.nsm_input.text().strip()
            nsue = self.nsue_input.text().strip()
            # ✅ OBTENER Y GUARDAR NSUT
            nsut = self.nsut_input.text().strip()
            hora_reporte = self.time_edit.time().toString("HH:mm")
            
            # Validar campos obligatorios
            if not nsm or not nsue:
                raise ValueError("NSM y NSUE son campos obligatorios")
            
            ConfigManager._validar_rfc(rfc)
            ConfigManager._validar_coordenadas(lat, long)
            
            config = ConfigManager.cargar_config_general()
            config["RFC"] = rfc
            config["Lat"] = float(lat)
            config["Long"] = float(long)
            config["unidad_visualizacion"] = unit
            config["storage_path"] = usb_path
            config["hora_reporte"] = hora_reporte
            config["NSM"] = nsm
            config["NSUE"] = nsue
            # ✅ GUARDAR NSUT
            config["NSUT"] = nsut
            
            ConfigManager.guardar_config_general(config)
            self.config_updated.emit()
            StateManager.set_ready("settings")
            QMessageBox.information(self, "Éxito", "Configuración guardada correctamente")
            self.close()
            
        except ValueError as e:
            # Error de validación por parte del usuario
            if hasattr(self, 'error_handler') and self.error_handler:
                self.error_handler.log_error("301", f"Error de validación en configuración: {str(e)}", es_error_sistema=True)
            QMessageBox.critical(self, "Error de Validación", str(e))
            
        except Exception as e:
            # Error crítico al guardar el archivo JSON
            if hasattr(self, 'error_handler') and self.error_handler:
                self.error_handler.log_error("CONFIG-SAVE", f"Fallo crítico guardando configuración general: {str(e)}", es_error_sistema=True)
            QMessageBox.critical(self, "Error al Guardar", f"Error inesperado: {str(e)}")