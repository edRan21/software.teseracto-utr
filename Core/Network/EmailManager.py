# TESERACTO-UTR/Core/Network/EmailManager.py

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import os
import logging
from typing import Tuple

class EmailManager:
    """
    Gestor del protocolo SMTP.
    Responsabilidad Única: Construir el mensaje MIME y transmitir archivos adjuntos.
    """
    def __init__(self, config: dict, error_handler):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.error_handler = error_handler
        self._actualizar_credenciales(config)

    def actualizar_configuracion(self, config: dict) -> None:
        """Actualización en caliente desde la UI."""
        self._actualizar_credenciales(config)

    def _actualizar_credenciales(self, config: dict) -> None:
        self.host = config.get("smtp_host", "smtp.gmail.com")
        self.puerto = int(config.get("smtp_port", 587))
        self.usuario = config.get("email_usuario", "")
        self.clave = config.get("email_clave", "")
        self.destinatarios = config.get("destinatarios", [])
        self.asunto = config.get("asunto", "Reporte de Telemetría TESSERACTO-UTR")

    def enviar_archivo(self, ruta_local: str, nombre_adjunto: str) -> Tuple[bool, str]:
        if not self.usuario or not self.clave or not self.destinatarios:
            return False, "Credenciales SMTP o destinatarios incompletos."

        try:
            msg = MIMEMultipart()
            msg['From'] = self.usuario
            msg['To'] = ", ".join(self.destinatarios)
            msg['Subject'] = self.asunto
            
            cuerpo = "Se adjunta el reporte automatizado generado por el sistema TESSERACTO-UTR."
            msg.attach(MIMEText(cuerpo, 'plain'))

            with open(ruta_local, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename= {nombre_adjunto}")
            msg.attach(part)

            server = smtplib.SMTP(self.host, self.puerto, timeout=10)
            server.starttls()
            server.login(self.usuario, self.clave)
            server.sendmail(self.usuario, self.destinatarios, msg.as_string())
            server.quit()

            return True, "250 OK - Correo enviado exitosamente"
            
        except Exception as e:
            self.error_handler.activar_ker_sistema("002", f"Fallo SMTP: {str(e)}")
            return False, str(e)