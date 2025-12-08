# Tesseract/GUI/Windows/SMSConfigWindow.py

import json
import os
import requests
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, QLineEdit,
    QPushButton, QCheckBox, QLabel, QMessageBox, QHBoxLayout, QComboBox
)
from PyQt5.QtCore import Qt
from Core.System.ErrorHandler import ErrorHandler
from Core.System.PathManager import path_manager

class SMSConfigWindow(QWidget):
    def __init__(self, error_handler: ErrorHandler):
        super().__init__()
        self.error_handler = error_handler
        self.setWindowTitle("Configuración SMS Instasent")
        self.setMinimumWidth(600)
        self.setup_ui()
        self.load_config()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Método de envío
        method_group = QGroupBox("Método de Envío")
        method_layout = QFormLayout()
        
        self.method_combo = QComboBox()
        self.method_combo.addItems(["SMPP", "HTTP API"])
        self.method_combo.currentTextChanged.connect(self.on_method_changed)
        method_layout.addRow("Método:", self.method_combo)
        
        method_group.setLayout(method_layout)
        main_layout.addWidget(method_group)

        # SMS Configuration - SMPP
        self.sms_group = QGroupBox("Configuración SMS Instasent (SMPP)")
        sms_layout = QFormLayout()
        
        self.sms_enabled = QCheckBox("Habilitar envío de SMS")
        self.sms_enabled.setChecked(True)
        
        # Información importante sobre Instasent
        info_label = QLabel(
            "Instasent utiliza protocolo SMPP para envío confiable de SMS. "
            "Requiere cuenta activa en instasent.com con acceso SMPP habilitado."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-style: italic;")
        
        # Campos específicos de Instasent SMPP
        self.instasent_host = QLineEdit()
        self.instasent_host.setPlaceholderText("smpp.instasent.com")
        
        self.instasent_port = QLineEdit()
        self.instasent_port.setPlaceholderText("2775")
        self.instasent_port.setText("2775")
        
        self.instasent_username = QLineEdit()
        self.instasent_username.setPlaceholderText("Tu usuario de Instasent SMPP")
        
        self.instasent_password = QLineEdit()
        self.instasent_password.setEchoMode(QLineEdit.Password)
        self.instasent_password.setPlaceholderText("Tu contraseña de Instasent SMPP")
        
        self.instasent_sender = QLineEdit()
        self.instasent_sender.setPlaceholderText("TESSERACT")
        
        self.destination_number = QLineEdit()
        self.destination_number.setPlaceholderText("+521234567890")
        
        sms_layout.addRow(self.sms_enabled)
        sms_layout.addRow(info_label)
        sms_layout.addRow("Host SMPP:", self.instasent_host)
        sms_layout.addRow("Puerto:", self.instasent_port)
        sms_layout.addRow("Usuario SMPP:", self.instasent_username)
        sms_layout.addRow("Contraseña SMPP:", self.instasent_password)
        sms_layout.addRow("Remitente:", self.instasent_sender)
        sms_layout.addRow("Número Destino:", self.destination_number)
        
        self.btn_test_sms = QPushButton("Probar Conexión SMPP")
        self.btn_test_sms.clicked.connect(self.test_sms_connection)
        sms_layout.addRow(self.btn_test_sms)
        
        self.sms_group.setLayout(sms_layout)
        main_layout.addWidget(self.sms_group)

        # HTTP API Configuration
        self.http_group = QGroupBox("Configuración HTTP API")
        http_layout = QFormLayout()
        
        http_info_label = QLabel(
            "API HTTP de Instasent para envío de SMS. "
            "Utiliza el token proporcionado en tu cuenta de Instasent."
        )
        http_info_label.setWordWrap(True)
        http_info_label.setStyleSheet("color: #666; font-style: italic;")
        
        self.api_token = QLineEdit()
        self.api_token.setPlaceholderText("Token de API HTTP de Instasent")
        
        self.http_sender = QLineEdit()
        self.http_sender.setPlaceholderText("TESSERACT")
        
        self.http_destination = QLineEdit()
        self.http_destination.setPlaceholderText("+521234567890")
        
        http_layout.addRow(http_info_label)
        http_layout.addRow("Token API:", self.api_token)
        http_layout.addRow("Remitente:", self.http_sender)
        http_layout.addRow("Número Destino:", self.http_destination)
        
        self.btn_test_http = QPushButton("Probar API HTTP")
        self.btn_test_http.clicked.connect(self.test_http_connection)
        http_layout.addRow(self.btn_test_http)
        
        self.http_group.setLayout(http_layout)
        main_layout.addWidget(self.http_group)

        # Save Button
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Guardar Configuración")
        self.btn_save.clicked.connect(self.save_config)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.close)
        
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_layout)
        
        # Status Label
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)
        
        self.setLayout(main_layout)
        
        # Inicialmente ocultar el grupo HTTP
        self.http_group.setVisible(False)

    def on_method_changed(self, method):
        """Muestra/oculta campos según el método seleccionado"""
        if method == "SMPP":
            self.sms_group.setVisible(True)
            self.http_group.setVisible(False)
        else:
            self.sms_group.setVisible(False)
            self.http_group.setVisible(True)

    # Modificar la función load_config
    def load_config(self):
        """Carga la configuración SMS actual desde el archivo"""
        try:
            # Usar PathManager para obtener ruta absoluta
            config_path = path_manager.get_config_path("sms_config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    sms_config = json.load(f)
                    
                    # Cargar configuración según el proveedor
                    provider = sms_config.get('provider', 'instasent')
                    
                    if provider == 'instasent':
                        self.method_combo.setCurrentText("SMPP")
                        self.sms_enabled.setChecked(sms_config.get('use_sms', True))
                        self.instasent_host.setText(sms_config.get('instasent_host', 'smpp.instasent.com'))
                        self.instasent_port.setText(str(sms_config.get('instasent_port', 2775)))
                        self.instasent_username.setText(sms_config.get('instasent_username', ''))
                        self.instasent_password.setText(sms_config.get('instasent_password', ''))
                        self.instasent_sender.setText(sms_config.get('instasent_sender_id', 'TESSERACT'))
                        self.destination_number.setText(sms_config.get('numero_destino', ''))
                    else:
                        self.method_combo.setCurrentText("HTTP API")
                        self.api_token.setText(sms_config.get('api_token', ''))
                        self.http_sender.setText(sms_config.get('instasent_sender_id', 'TESSERACT'))
                        self.http_destination.setText(sms_config.get('numero_destino', ''))
                    
        except Exception as e:
            self.error_handler.log_error("SMS_CONF_LOAD", f"Error cargando configuración SMS: {e}")
            self.status_label.setText("❌ Error cargando configuración")

    # Modificar la función save_config
    def save_config(self):
        """Guarda la configuración SMS en el archivo"""
        try:
            method = self.method_combo.currentText()
            
            if method == "SMPP":
                # Validar campos obligatorios para SMPP
                if not all([
                    self.instasent_host.text().strip(),
                    self.instasent_port.text().strip(),
                    self.instasent_username.text().strip(),
                    self.instasent_password.text().strip(),
                    self.instasent_sender.text().strip(),
                    self.destination_number.text().strip()
                ]):
                    QMessageBox.warning(self, "Campos incompletos", 
                                    "Todos los campos son obligatorios para configuración SMPP.")
                    return
                
                # Configuración para SMPP
                sms_config = {
                    "use_sms": self.sms_enabled.isChecked(),
                    "provider": "instasent",
                    "instasent_host": self.instasent_host.text().strip(),
                    "instasent_port": int(self.instasent_port.text().strip()),
                    "instasent_username": self.instasent_username.text().strip(),
                    "instasent_password": self.instasent_password.text().strip(),
                    "instasent_sender_id": self.instasent_sender.text().strip(),
                    "numero_destino": self.destination_number.text().strip()
                }
            else:
                # Validar campos obligatorios para HTTP API
                if not all([
                    self.api_token.text().strip(),
                    self.http_sender.text().strip(),
                    self.http_destination.text().strip()
                ]):
                    QMessageBox.warning(self, "Campos incompletos", 
                                    "Todos los campos son obligatorios para configuración HTTP API.")
                    return
                
                # Configuración para HTTP API
                sms_config = {
                    "use_sms": True,
                    "provider": "instasent_http",
                    "api_token": self.api_token.text().strip(),
                    "instasent_sender_id": self.http_sender.text().strip(),
                    "numero_destino": self.http_destination.text().strip()
                }
            
            # Usar PathManager para obtener ruta absoluta
            config_path = path_manager.get_config_path("sms_config.json")
            
            # Guardar configuración
            with open(config_path, 'w') as f:
                json.dump(sms_config, f, indent=4)
            
            self.status_label.setText("✅ Configuración SMS guardada exitosamente")
            QMessageBox.information(self, "Éxito", "Configuración SMS guardada correctamente")
            
        except ValueError:
            self.status_label.setText("❌ Error: El puerto debe ser un número")
            QMessageBox.critical(self, "Error", "El puerto debe ser un número entero.")
        except Exception as e:
            self.status_label.setText("❌ Error guardando configuración SMS")
            self.error_handler.log_error("SMS_CONF_SAVE", f"Error guardando configuración SMS: {e}")
            QMessageBox.critical(self, "Error", f"Error al guardar configuración SMS: {str(e)}")

    def test_sms_connection(self):
        """Prueba la conexión SMPP con las credenciales actuales"""
        try:
            # Validar campos
            if not all([
                self.instasent_host.text().strip(),
                self.instasent_port.text().strip(),
                self.instasent_username.text().strip(),
                self.instasent_password.text().strip()
            ]):
                QMessageBox.warning(self, "Campos incompletos", 
                                  "Complete los campos de host, puerto, usuario y contraseña para probar la conexión.")
                return
            
            # Obtener valores
            host = self.instasent_host.text().strip()
            port = int(self.instasent_port.text().strip())
            username = self.instasent_username.text().strip()
            password = self.instasent_password.text().strip()
            
            # Intentar conexión SMPP
            from smpplib import client as smpp_client
            client = smpp_client.Client(host, port)
            client.connect()
            client.bind_transceiver(
                system_id=username,
                password=password
            )
            
            # Si llegamos aquí, la conexión fue exitosa
            client.unbind()
            client.disconnect()
            
            QMessageBox.information(self, "Prueba de Conexión", "✅ Conexión SMPP exitosa!")
                
        except ValueError:
            QMessageBox.critical(self, "Error", "El puerto debe ser un número entero.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"❌ Error en la conexión SMPP: {str(e)}")

    def test_http_connection(self):
        """Prueba la conexión HTTP API con las credenciales actuales"""
        try:
            # Validar campos
            if not all([
                self.api_token.text().strip(),
                self.http_sender.text().strip(),
                self.http_destination.text().strip()
            ]):
                QMessageBox.warning(self, "Campos incompletos", 
                                "Complete los campos de token, remitente y número destino para probar la conexión.")
                return
            
            # Obtener valores y asegurar longitud máxima
            token = self.api_token.text().strip()
            sender = self.http_sender.text().strip()[:11]  # Limitar a 11 caracteres
            destination = self.http_destination.text().strip()
            
            # Validar formato del número
            if not destination.startswith('+'):
                QMessageBox.warning(self, "Formato incorrecto", 
                                "El número destino debe incluir código de país (ej: +521234567890)")
                return
            
            # Intentar conexión HTTP API
            url = "https://api.instasent.com/sms/"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            data = {
                "from": sender,
                "to": destination,
                "text": "Prueba de conexión desde Tesseract"
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=10)
            
            if response.status_code == 201:
                QMessageBox.information(self, "Prueba de Conexión", "✅ Conexión HTTP API exitosa!")
            else:
                QMessageBox.critical(self, "Error", f"❌ Error en la conexión HTTP API: {response.status_code} - {response.text}")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"❌ Error en la conexión HTTP API: {str(e)}")