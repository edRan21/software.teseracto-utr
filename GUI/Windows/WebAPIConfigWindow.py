# TESERACTO-UTR/GUI/Windows/WebAPIConfigWindow.py

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit, 
                             QPushButton, QCheckBox, QMessageBox, QGroupBox, QSpinBox)
from PyQt5.QtCore import Qt
from Core.System.ConfigManager import ConfigManager

class WebAPIConfigWindow(QWidget):
    def __init__(self, api_worker, error_handler):
        super().__init__()
        self.api_worker = api_worker
        self.error_handler = error_handler
        
        self.setWindowTitle("Configuración de Servidor Web (API)")
        self.setMinimumSize(500, 300)
        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: white; font-family: Segoe UI; }
            QLineEdit, QSpinBox { background-color: #3b3b3b; color: white; border: 1px solid #555; border-radius: 3px; padding: 5px; }
            QPushButton { background-color: #4CAF50; color: white; padding: 8px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #45a049; }
            QGroupBox { border: 1px solid #444; border-radius: 5px; margin-top: 10px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)

        self._setup_ui()
        self._cargar_configuracion()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        grupo = QGroupBox("Parámetros de Telemetría (Web API)")
        form = QFormLayout()

        self.chk_habilitado = QCheckBox("Habilitar transmisión al servidor Web")
        
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("Ej: https://miservidor.com/api")
        
        self.txt_key = QLineEdit()
        self.txt_key.setEchoMode(QLineEdit.Password)
        self.txt_key.setPlaceholderText("Token Bearer o API Key")
        
        self.spin_intervalo = QSpinBox()
        self.spin_intervalo.setRange(1, 1440) # Mínimo 1 minuto, Máximo 24 horas
        self.spin_intervalo.setSuffix(" minutos")

        form.addRow(self.chk_habilitado)
        form.addRow("URL del Servidor:", self.txt_url)
        form.addRow("API Key (Token):", self.txt_key)
        form.addRow("Frecuencia de Envío:", self.spin_intervalo)

        grupo.setLayout(form)
        layout.addWidget(grupo)

        self.btn_guardar = QPushButton("Guardar y Aplicar")
        self.btn_guardar.clicked.connect(self._guardar_configuracion)
        layout.addWidget(self.btn_guardar)

    def _cargar_configuracion(self):
        config = ConfigManager.cargar_config_api()
        self.chk_habilitado.setChecked(config.get("enabled", False))
        self.txt_url.setText(config.get("api_url", ""))
        self.txt_key.setText(config.get("api_key", ""))
        self.spin_intervalo.setValue(int(config.get("intervalo_minutos", 15)))

    def _guardar_configuracion(self):
        try:
            nueva_config = {
                "enabled": self.chk_habilitado.isChecked(),
                "api_url": self.txt_url.text().strip(),
                "api_key": self.txt_key.text().strip(),
                "intervalo_minutos": self.spin_intervalo.value()
            }

            if nueva_config["enabled"] and not nueva_config["api_url"]:
                QMessageBox.warning(self, "Validación", "Debe ingresar una URL válida para habilitar la API.")
                return

            # Guarda en disco (AppData) a través de ConfigManager
            ConfigManager.guardar_config_api(nueva_config)

            # Sincronización en caliente: Inyecta la config directamente al Worker en ejecución
            if self.api_worker:
                self.api_worker.actualizar_configuracion(nueva_config)

            QMessageBox.information(self, "Éxito", "Configuración guardada y aplicada al motor de red.")
            self.close()

        except Exception as e:
            self.error_handler.log_error("301", f"Error guardando config API: {e}")
            QMessageBox.critical(self, "Error", f"Fallo al guardar: {e}")