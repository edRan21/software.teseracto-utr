# TESERACTO-UTR/GUI/Windows/FTPConaguaWindow.py

import os
import re
import time
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                            QComboBox, QPushButton, QMessageBox, QTextEdit, QGroupBox,
                            QCheckBox, QApplication)
from PyQt5.QtCore import Qt, QTimer
from Core.System.ConfigManager import ConfigManager
from Core.System.StateManager import StateManager
from Core.DataProcessing.Services import RecordFormatter, ConfigProvider, BitmaskConverter, FileNameGenerator
from Core.Network.FTPManager import FTPManager

class FTPConaguaWindow(QWidget):
    def __init__(self, error_handler):
        super().__init__()
        self.error_handler = error_handler
        self.setWindowTitle("Unidad de Inspección")
        self.setGeometry(100, 100, 600, 750)  # Aumentado para nuevo checkbox
        self.current_content = None
        self.current_filename = None
        self.setup_ui()
        self.load_ftp_config()
        self.apply_dark_theme()
        self._progress_label = None
        self._progress_timer = QTimer()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Grupo para configuración FTP
        ftp_group = QGroupBox("Configuración FTP")
        ftp_layout = QVBoxLayout()

        # Campos FTP
        self.ftp_host = QLineEdit()
        self.ftp_port = QLineEdit("21")
        self.ftp_user = QLineEdit()
        self.ftp_password = QLineEdit()
        self.ftp_password.setEchoMode(QLineEdit.Password)
        self.ftp_remote_path = QLineEdit()

        ftp_layout.addWidget(QLabel("Servidor FTP:"))
        ftp_layout.addWidget(self.ftp_host)
        ftp_layout.addWidget(QLabel("Puerto:"))
        ftp_layout.addWidget(self.ftp_port)
        ftp_layout.addWidget(QLabel("Usuario:"))
        ftp_layout.addWidget(self.ftp_user)
        ftp_layout.addWidget(QLabel("Contraseña:"))
        ftp_layout.addWidget(self.ftp_password)
        ftp_layout.addWidget(QLabel("Ruta remota (opcional):"))
        ftp_layout.addWidget(self.ftp_remote_path)

        ftp_group.setLayout(ftp_layout)
        layout.addWidget(ftp_group)

        # Grupo para reporte CONAGUA
        report_group = QGroupBox("Reporte Unidad de Inspección")
        report_layout = QVBoxLayout()

        # Tipo de reporte
        report_layout.addWidget(QLabel("Tipo de reporte:"))
        self.report_type_combo = QComboBox()
        self.report_type_combo.addItems(["Medidor", "SistemaMedicion"])
        report_layout.addWidget(self.report_type_combo)

        # Clave para la Unidad de Inspección (persona que externa que audita enviando un archivo txt especial)
        report_layout.addWidget(QLabel("Clave Unidad de Inspección:"))
        self.clave_conagua = QLineEdit()
        self.clave_conagua.setMaxLength(5)
        self.clave_conagua.setPlaceholderText("Ejemplo: AB123")
        report_layout.addWidget(self.clave_conagua)

        # ✅ NUEVO: Opción de reintentos inteligentes
        self.retry_checkbox = QCheckBox("Reintentar lectura automáticamente (hasta 3 veces si falla)")
        self.retry_checkbox.setChecked(True)
        report_layout.addWidget(self.retry_checkbox)

        # Botones de generación
        btn_layout = QHBoxLayout()
        self.generate_btn = QPushButton("Generar reporte para Unidad de Inspección")
        self.generate_btn.clicked.connect(self.generate_report)
        self.clear_btn = QPushButton("Borrar reporte")
        self.clear_btn.clicked.connect(self.clear_report)
        self.clear_btn.setEnabled(False)
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addWidget(self.clear_btn)
        report_layout.addLayout(btn_layout)

        # Mostrar nombre de archivo
        report_layout.addWidget(QLabel("Nombre de archivo:"))
        self.filename_label = QLabel("")
        self.filename_label.setWordWrap(True)
        report_layout.addWidget(self.filename_label)

        # Mostrar contenido
        report_layout.addWidget(QLabel("Contenido del reporte:"))
        self.content_text = QTextEdit()
        self.content_text.setReadOnly(True)
        report_layout.addWidget(self.content_text)

        report_group.setLayout(report_layout)
        layout.addWidget(report_group)

        # Botón de enviar
        self.send_btn = QPushButton("Enviar a servidor")
        self.send_btn.clicked.connect(self.send_report)
        self.send_btn.setEnabled(False)
        layout.addWidget(self.send_btn)

        self.setLayout(layout)

    def apply_dark_theme(self):
        dark_theme = """
            QWidget {
                background-color: #2b2b2b;
                color: #cccccc;
                font-family: Segoe UI;
            }
            QLabel {
                color: #cccccc;
                padding: 2px;
            }
            QComboBox, QLineEdit, QTextEdit {
                background-color: #3b3b3b;
                color: white;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
            }
            QComboBox:hover, QLineEdit:hover, QTextEdit:hover {
                border: 1px solid #777777;
            }
            QPushButton {
                background-color: #5a5a5a;
                color: white;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #666666;
                border: 1px solid #777777;
            }
            QPushButton:pressed {
                background-color: #777777;
            }
            QPushButton:disabled {
                background-color: #3b3b3b;
                color: #777777;
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
            QCheckBox {
                color: #cccccc;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """
        self.setStyleSheet(dark_theme)

    def load_ftp_config(self):
        """Cargar configuración FTP existente si está disponible"""
        try:
            config = ConfigManager.cargar_config_ftp()
            self.ftp_host.setText(config.get("host", ""))
            self.ftp_port.setText(str(config.get("port", "21")))
            self.ftp_user.setText(config.get("usuario", ""))
            self.ftp_password.setText(config.get("clave", ""))
            self.ftp_remote_path.setText(config.get("ruta_remota", ""))
        except:
            pass

    def validate_clave(self, clave):
        """Validar formato de clave CONAGUA: 2 letras + 3 números"""
        if len(clave) != 5:
            return False
        if not clave[:2].isalpha():
            return False
        if not clave[2:].isdigit():
            return False
        return True

    def format_conagua_report(self, tipo_reporte: str, ker_code: str, clave: str, 
                             flujo_inst: float = 0.0, flujo_acum: float = 0.0) -> str:
        """Formatea el reporte específicamente para la Unidad de Inspección"""
        try:
            config = ConfigManager.cargar_config_general()
            now = datetime.now()
            fecha = now.strftime("%Y%m%d")
            hora = now.strftime("%H%M%S")
            ker_code_str = str(ker_code).zfill(3)
            
            if tipo_reporte == "Medidor":
                # ✅ MODIFICADO: Reemplazar NSUE por NSUT
                # Formato: M|fecha|hora|RFC|NSM|NSUT|lat|long|ker_code|clave
                return (
                    f"M|{fecha}|{hora}|{config['RFC']}|{config['NSM']}|{config['NSUT']}|"
                    f"{config['Lat']}|{config['Long']}|{ker_code_str}|{clave}"
                )
            elif tipo_reporte == "SistemaMedicion":
                # ✅ MODIFICADO: Agregar NSUT después de RFC e incluir lecturas
                # Formato: QA|fecha|hora|RFC|NSUT|flujo_inst|flujo_acum|lat|long|ker_code|clave
                return (
                    f"QA|{fecha}|{hora}|{config['RFC']}|{config['NSUT']}|"
                    f"{flujo_inst:.3f}|{flujo_acum:.3f}|"
                    f"{config['Lat']}|{config['Long']}|{ker_code_str}|{clave}"
                )
            else:
                raise ValueError("Tipo de reporte inválido")
                
        except Exception as e:
            # En caso de error, generar formato de error
            ker_code_str = str(ker_code).zfill(3)
            return f"ERR|{datetime.now().strftime('%Y%m%d|%H%M%S')}|{type(e).__name__}|{str(e)}|{ker_code_str}|{clave}"

    def generate_conagua_filename(self, tipo_reporte: str, clave: str) -> str:
        """Genera nombre de archivo específico para Unidad de Inspección con la clave incluida"""
        try:
            config_provider = ConfigProvider(ConfigManager())
            name_gen = FileNameGenerator(config_provider)
            
            # Generar nombre base
            base_name = name_gen.generate_daily_name(tipo_reporte)
            
            # Insertar la clave antes de .txt
            if base_name.endswith('.txt'):
                # Remover .txt, agregar clave, y volver a agregar .txt
                name_without_ext = base_name[:-4]
                return f"{name_without_ext}_{clave}.txt"
            else:
                # Si por alguna razón no termina en .txt, agregar normalmente
                return f"{base_name}_{clave}.txt"
                
        except Exception as e:
            # Fallback: nombre genérico con clave
            fecha = datetime.now().strftime("%Y%m%d")
            return f"reporte_conagua_{fecha}_{clave}.txt"

    def mostrar_progreso(self, mensaje: str):
        """Muestra mensaje de progreso sin bloquear la UI"""
        if not self._progress_label:
            self._progress_label = QLabel(mensaje, self)
            self._progress_label.setAlignment(Qt.AlignCenter)
            self._progress_label.setStyleSheet("color: #FFA500; font-weight: bold;")
            self.layout().insertWidget(1, self._progress_label)  # Insertar después del primer grupo
        else:
            self._progress_label.setText(mensaje)
        
        # Forzar actualización de la UI
        QApplication.processEvents()

    def ocultar_progreso(self):
        """Oculta la etiqueta de progreso"""
        if self._progress_label:
            self._progress_label.hide()
            self._progress_label = None
        QApplication.processEvents()

    def obtener_lecturas_confiables(self, medidor, max_intentos=3, delay_entre_intentos=1.0):
        """
        Intenta obtener lecturas válidas con reintentos inteligentes.
        Retorna: (flujo_instantaneo, flujo_acumulado, intentos_realizados, mensaje_estado)
        """
        intentos = 0
        mejores_lecturas = (0.0, 0.0)
        ultimo_error = ""
        
        # Determinar si se deben hacer reintentos
        hacer_reintentos = self.retry_checkbox.isChecked()
        if not hacer_reintentos:
            max_intentos = 1
        
        for intento in range(max_intentos):
            intentos += 1
            
            try:
                # Mostrar progreso al usuario si es reintento
                if intento > 0:
                    self.mostrar_progreso(f"Intento {intento+1}/{max_intentos}...")
                
                # Leer datos del medidor
                datos = medidor.leer_registros()
                
                if datos:
                    # Extraer valores con nombres estándar
                    flujo_inst = datos.get("flujo_instantaneo", 0.0)
                    flujo_acum = datos.get("flujo_acumulado", 0.0)
                    
                    # Validar que sean números y no None
                    try:
                        flujo_inst = float(flujo_inst) if flujo_inst is not None else 0.0
                        flujo_acum = float(flujo_acum) if flujo_acum is not None else 0.0
                    except (ValueError, TypeError):
                        ultimo_error = f"Valores no numéricos en intento {intento+1}"
                        continue
                    
                    # CRITERIO DE ACEPTACIÓN: Ambos valores son numéricos
                    if isinstance(flujo_inst, (int, float)) and isinstance(flujo_acum, (int, float)):
                        # Si son valores distintos de 0, aceptar inmediatamente
                        if flujo_inst != 0.0 or flujo_acum != 0.0:
                            self.ocultar_progreso()
                            return flujo_inst, flujo_acum, intentos, f"Lectura exitosa en intento {intentos}"
                        
                        # Si son 0.0, guardar pero seguir intentando
                        mejores_lecturas = (flujo_inst, flujo_acum)
                        ultimo_error = f"Lecturas en 0.0 en intento {intento+1}"
                else:
                    ultimo_error = f"Datos vacíos en intento {intento+1}"
            
            except Exception as e:
                ultimo_error = f"Error en intento {intento+1}: {str(e)}"
            
            # Pequeña pausa entre intentos si no es el último
            if intento < max_intentos - 1 and hacer_reintentos:
                time.sleep(delay_entre_intentos)
        
        self.ocultar_progreso()
        mensaje = f"Usando valores de respaldo después de {intentos} intentos"
        if ultimo_error:
            mensaje += f" ({ultimo_error})"
        
        return mejores_lecturas[0], mejores_lecturas[1], intentos, mensaje

    def generate_report(self):
        """Generar el reporte CONAGUA con lecturas confiables"""
        # Validar clave CONAGUA
        clave = self.clave_conagua.text().strip()
        if not self.validate_clave(clave):
            QMessageBox.warning(self, "Clave inválida", 
                            "La clave de Unidad de Inspección debe tener exactamente 2 letras seguidas de 3 números.")
            return

        # Obtener el medidor desde StateManager
        medidor = StateManager.get_state('medidor')
        if not medidor:
            QMessageBox.warning(self, "Error", "No hay medidor configurado o conectado.")
            return

        # Obtener lecturas confiables con reintentos
        self.mostrar_progreso("Obteniendo lecturas del medidor...")
        flujo_inst, flujo_acum, intentos, mensaje_estado = self.obtener_lecturas_confiables(medidor)
        
        # Mostrar información sobre los intentos si fueron necesarios
        if intentos > 1:
            self.mostrar_progreso(mensaje_estado)
            QApplication.processEvents()
            time.sleep(1)  # Breve pausa para que el usuario vea el mensaje
        
        # Si después de todos los intentos tenemos 0.0, preguntar al usuario
        if flujo_inst == 0.0 and flujo_acum == 0.0 and intentos >= 3:
            respuesta = QMessageBox.question(
                self, 
                "Advertencia - Lecturas en 0.0",
                "Las lecturas son 0.0 después de múltiples intentos.\n\n" +
                "Posibles causas:\n" +
                "1. El medidor está en reposo (sin flujo)\n" +
                "2. Problemas de conexión\n" +
                "3. Configuración incorrecta\n\n" +
                "¿Desea continuar con valores 0.0?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if respuesta == QMessageBox.No:
                self.ocultar_progreso()
                return
        
        # Obtener código KER del ErrorHandler
        ker_code = self.error_handler.get_ker_code()

        # Obtener el tipo de reporte
        tipo_reporte = self.report_type_combo.currentText()

        try:
            # Generar contenido ESPECIAL para CONAGUA
            if tipo_reporte == "Medidor":
                contenido = self.format_conagua_report(tipo_reporte, ker_code, clave)
            elif tipo_reporte == "SistemaMedicion":
                contenido = self.format_conagua_report(tipo_reporte, ker_code, clave, flujo_inst, flujo_acum)
            
            # Generar nombre de archivo ESPECIAL para CONAGUA (con clave)
            filename = self.generate_conagua_filename(tipo_reporte, clave)

        except Exception as e:
            self.ocultar_progreso()
            QMessageBox.warning(self, "Error", 
                            f"Error al formatear el reporte: {str(e)}")
            return

        # Mostrar en la interfaz
        self.filename_label.setText(filename)
        self.content_text.setPlainText(contenido)

        # Habilitar botones
        self.clear_btn.setEnabled(True)
        self.send_btn.setEnabled(True)

        # Guardar para envío
        self.current_content = contenido
        self.current_filename = filename

        self.ocultar_progreso()
        
        # Mensaje final informativo
        if intentos == 1:
            QMessageBox.information(self, "Éxito", 
                                "Reporte para Unidad de Inspección generado correctamente en 1 intento.")
        else:
            QMessageBox.information(self, "Éxito", 
                                f"Reporte generado correctamente después de {intentos} intentos.")

    def clear_report(self):
        """Limpiar el reporte generado"""
        self.filename_label.setText("")
        self.content_text.setPlainText("")
        self.current_content = None
        self.current_filename = None
        self.clear_btn.setEnabled(False)
        self.send_btn.setEnabled(False)

    def send_report(self):
        """Enviar el reporte al servidor FTP"""
        if not self.current_content or not self.current_filename:
            QMessageBox.warning(self, "Error", "No hay reporte generado para enviar.")
            return

        # Validar campos FTP
        host = self.ftp_host.text().strip()
        port = self.ftp_port.text().strip()
        user = self.ftp_user.text().strip()
        password = self.ftp_password.text().strip()
        remote_path = self.ftp_remote_path.text().strip()

        if not host or not user or not password:
            QMessageBox.warning(self, "Error", 
                            "Complete los campos obligatorios del FTP (servidor, usuario y contraseña).")
            return

        # Crear archivo temporal
        temp_path = os.path.join(os.getcwd(), self.current_filename)
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(self.current_content)
        except Exception as e:
            QMessageBox.warning(self, "Error", 
                            f"No se pudo crear el archivo temporal: {str(e)}")
            return

        # Enviar via FTP
        try:
            # Crear configuración para FTPManager
            ftp_config = {
                "host": host,
                "usuario": user,
                "clave": password,
                "port": int(port) if port else 21,
                "ruta_remota": remote_path
            }
            ftp_manager = FTPManager(ftp_config, self.error_handler)
            remote_filename = os.path.join(remote_path, self.current_filename) if remote_path else self.current_filename
            success = ftp_manager.enviar_archivo(temp_path, remote_filename)
            if success:
                QMessageBox.information(self, "Éxito", "Reporte enviado correctamente al servidor FTP.")
            else:
                QMessageBox.warning(self, "Error", "No se pudo enviar el reporte. Verifique la conexión.")
        except Exception as e:
            QMessageBox.warning(self, "Error", 
                            f"Error al enviar el reporte: {str(e)}")
        finally:
            # Eliminar archivo temporal
            try:
                os.remove(temp_path)
            except:
                pass
            self.ocultar_progreso()