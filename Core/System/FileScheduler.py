# TESERACTO-UTR/Core/System/FileScheduler.py

import os
import time
import threading
import logging
import json
import smtplib
from datetime import datetime
from typing import Callable, Dict, Any, List, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from Core.Network.IFileTransfer import IFileTransfer
from Core.System.ErrorHandler import ErrorHandler
from Core.System.PathManager import path_manager
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import shutil

class FileScheduler:
    
    def __init__(
        self,
        transfer_service: IFileTransfer,
        config: Dict[str, Any],
        get_plantilla_fn: Callable[[str], Dict[str, Any]],
        error_handler: ErrorHandler
    ):
        self.transfer_service = transfer_service
        self.config = config
        self.get_plantilla = get_plantilla_fn
        self.error_handler = error_handler
        self.logger = logging.getLogger(__name__)
        
        self._scheduler: Optional[BackgroundScheduler] = None
        self._lock = threading.RLock()
        self._is_running = False
        self._is_processing = False
        self._last_successful_run: Optional[datetime] = None
        self._consecutive_failures = 0
        
        self.email_config = self._cargar_config_email()
        self.backup_dir = path_manager.get_base_path() / "backups_envios"
        self.backup_dir.mkdir(exist_ok=True)
        self._verificar_estructura_directorios()
        
    def _cargar_config_email(self) -> Optional[Dict[str, Any]]:
        try:
            config_path = path_manager.get_config_path("email_config.json")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            self.error_handler.log_error("301", "Error cargando configuración de Email", es_error_sistema=True)
            return None

    def _actualizar_config_email(self, nueva_config: Dict[str, Any]):
        self.email_config = nueva_config

    def actualizar_configuracion_completa(self, ftp_config: Dict[str, Any], email_config: Optional[Dict[str, Any]] = None):
        with self._lock:
            if hasattr(self.transfer_service, 'actualizar_configuracion'):
                self.transfer_service.actualizar_configuracion(ftp_config)
            
            self.config["hora_envio"] = ftp_config.get("hora_envio", self.config.get("hora_envio", "23:59"))
            self.config["ruta_remota"] = ftp_config.get("ruta_remota", self.config.get("ruta_remota", "/"))
            
            if email_config:
                self.email_config = email_config
            
            if self._is_running:
                self.detener()
                time.sleep(1)
                self.iniciar()

    def _verificar_estructura_directorios(self):
        try:
            pendientes_dir = self.config.get("directorio_pendientes", str(path_manager.get_pendientes_usb_path()))
            os.makedirs(pendientes_dir, exist_ok=True)
        except Exception as e:
            self.error_handler.log_error("010", "Fallo al verificar estructura de directorios", es_error_sistema=True)
    
    def _crear_respaldo_seguro(self, ruta_archivo: str) -> bool:
        try:
            if not os.path.exists(ruta_archivo):
                return True
            
            filename = os.path.basename(ruta_archivo)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"{filename}.{timestamp}.backup"
            
            shutil.copy2(ruta_archivo, backup_file)
            
            backups = list(self.backup_dir.glob("*.backup"))
            if len(backups) > 50:
                for old_backup in sorted(backups)[:len(backups)-50]:
                    try: old_backup.unlink()
                    except: pass
            return True
        except Exception as e:
            self.logger.error(f"Error creando respaldo: {e}")
            return False
    
    def obtener_estado(self) -> Dict[str, Any]:
        with self._lock:
            directorio = self.config.get("directorio_pendientes", str(path_manager.get_pendientes_usb_path()))
            archivos_pendientes = 0
            archivos_fallidos_email = 0
            
            if os.path.exists(directorio):
                for f in os.listdir(directorio):
                    if f.endswith('.txt') and not f.endswith('.email_pending'):
                        archivos_pendientes += 1
                    elif f.endswith('.email_pending'):
                        archivos_fallidos_email += 1
            
            estado = {
                "activo": self._is_running,
                "hora_programada": self.config.get("hora_envio", "23:59"),
                "proxima_ejecucion": None,
                "archivos_pendientes": archivos_pendientes,
                "archivos_fallidos_email": archivos_fallidos_email,
                "ultimo_exito": self._last_successful_run.strftime("%Y-%m-%d %H:%M:%S") if self._last_successful_run else "Nunca",
                "fallos_consecutivos": self._consecutive_failures,
                "modo": "AUTOMÁTICO"
            }
            
            if self._scheduler and self._is_running:
                try:
                    for job in self._scheduler.get_jobs():
                        if job.id == 'envio_automatico_diario' and job.next_run_time:
                            estado["proxima_ejecucion"] = job.next_run_time.strftime("%H:%M")
                            break
                except: pass
            
            return estado
    
    def obtener_detalle_archivos_pendientes(self) -> List[Dict[str, Any]]:
        detalles = []
        directorio = self.config.get("directorio_pendientes", str(path_manager.get_pendientes_usb_path()))
        
        if not os.path.exists(directorio):
            return detalles
        
        for filename in os.listdir(directorio):
            if filename.endswith('.txt') or filename.endswith('.email_pending'):
                filepath = os.path.join(directorio, filename)
                try:
                    stat = os.stat(filepath)
                    modificado = datetime.fromtimestamp(stat.st_mtime)
                    antiguedad = (datetime.now() - modificado).days
                    
                    detalles.append({
                        "nombre": filename,
                        "tamano_kb": round(stat.st_size / 1024, 2),
                        "modificado": modificado.strftime("%Y-%m-%d %H:%M:%S"),
                        "antiguedad_dias": antiguedad,
                        "estado": "email_pendiente" if filename.endswith('.email_pending') else "pendiente",
                        "prioridad": "ALTA" if antiguedad >= 3 else "MEDIA" if antiguedad >= 1 else "BAJA"
                    })
                except: pass
        
        return sorted(detalles, key=lambda x: x["antiguedad_dias"], reverse=True)
    
    def _enviar_email_archivo(self, ruta_archivo: str) -> bool:
        if not self.email_config or 'smtp_server' not in self.email_config:
            return False 
        
        filename = os.path.basename(ruta_archivo)
        for intento in range(3):
            try:
                with open(ruta_archivo, 'r', encoding='utf-8') as f:
                    contenido = f.read()
                
                msg = MIMEMultipart()
                msg['From'] = self.email_config['from']
                msg['To'] = ', '.join(self.email_config['to'])
                msg['Subject'] = self.email_config['subject']
                msg['Date'] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
                
                body = f"Archivo adjunto: {filename}\nFecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nSistema: Tesseract UTR\n"
                msg.attach(MIMEText(body, 'plain'))
                
                with open(ruta_archivo, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                    msg.attach(part)
                
                with smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'], timeout=30) as server:
                    server.starttls()
                    server.login(self.email_config['username'], self.email_config['password'])
                    server.send_message(msg)
                return True
                
            except Exception as e:
                self.logger.error(f"Error email: {e}")
                time.sleep(2)
        return False
    
    def _guardar_log_envio_detallado(self, inicio: datetime, resultados: list, modo: str):
        """Genera un reporte JSON detallado de la sesión de envío."""
        try:
            log_dir = path_manager.get_base_path() / "logs_envios"
            log_dir.mkdir(exist_ok=True)
            
            timestamp = inicio.strftime('%Y%m%d_%H%M%S')
            log_file = log_dir / f"envio_{timestamp}.json"
            
            log_data = {
                "sesion_inicio": inicio.isoformat(),
                "modo": modo,
                "servidores": {
                    "ftp_host": self.config.get("host", "Desconocido"),
                    "email_activo": bool(self.email_config)
                },
                "detalle_archivos": resultados,
                "resumen": {
                    "total_procesados": len(resultados),
                    "exitos_completos": len([r for r in resultados if r['ftp_ok'] and r['email_ok']]),
                    "fallos_ftp": len([r for r in resultados if not r['ftp_ok']]),
                    "fallos_email": len([r for r in resultados if not r['email_ok']])
                }
            }
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"📝 Log de envío generado: {log_file}")
            
        except Exception as e:
            self.logger.error(f"Fallo crítico al intentar escribir el log: {e}")

    def _procesar_archivo_individual(self, ruta_archivo: str) -> Dict[str, Any]:
        """Procesa FTP y Email de forma 100% independiente y registra en errores.log"""
        
        filename = os.path.basename(ruta_archivo)
        resultado = {
            "ftp_ok": False,
            "ftp_msg": "No ejecutado",
            "email_ok": False,
            "exito_completo": False
        }
        
        try:
            plantilla = self.get_plantilla(filename)
            nombre_remoto = plantilla.get("nombre_remoto", filename)
            ruta_base = self.config.get("ruta_remota", "/").rstrip('/')
            ruta_remota = f"{ruta_base}/{nombre_remoto}" if ruta_base != "/" else f"/{nombre_remoto}"

            es_email_pendiente = filename.endswith('.email_pending')
            
            # ==========================================
            # 1. BLOQUE FTP (Aislado)
            # ==========================================
            if not es_email_pendiente:
                ftp_ok, ftp_msg = self.transfer_service.enviar_archivo(ruta_archivo, ruta_remota)
                resultado["ftp_ok"] = ftp_ok
                resultado["ftp_msg"] = ftp_msg
                
                if not ftp_ok:
                    self.logger.error(f"FTP Fallido para {filename}: {ftp_msg}")
                    # ✅ REGISTRO FÍSICO: Se envía al errores.log
                    self.error_handler.log_error("FTP-550", f"Fallo FTP en {filename}: {ftp_msg}", es_error_sistema=True)
            else:
                resultado["ftp_ok"] = True
                resultado["ftp_msg"] = "Ya enviado previamente (Omitido)"

            # ==========================================
            # 2. BLOQUE EMAIL (Aislado e Independiente)
            # ==========================================
            # ✅ INDEPENDENCIA: Se ejecuta sin importar si el FTP falló o tuvo éxito
            email_ok = self._enviar_email_archivo(ruta_archivo)
            resultado["email_ok"] = email_ok
            
            if not email_ok:
                self.error_handler.log_error("EMAIL-FAIL", f"Fallo Email en {filename}", es_error_sistema=True)

            # ==========================================
            # 3. EVALUACIÓN Y PERSISTENCIA
            # ==========================================
            if resultado["ftp_ok"] and resultado["email_ok"]:
                resultado["exito_completo"] = True
                if self._crear_respaldo_seguro(ruta_archivo):
                    try: os.remove(ruta_archivo)
                    except: pass
            elif resultado["ftp_ok"] and not resultado["email_ok"]:
                # FTP exitoso, Email fallido. Cambiamos extensión para no repetir FTP
                if not es_email_pendiente:
                    nueva_ruta = f"{ruta_archivo}.email_pending"
                    try: os.rename(ruta_archivo, nueva_ruta)
                    except: pass
            
            # Nota: Si FTP falla, simplemente no lo renombramos ni lo borramos. 
            # El archivo se queda como .txt para el siguiente intento.
            
            return resultado

        except Exception as e:
            msg = f"Error crítico procesando {filename}: {str(e)}"
            self.logger.error(msg)
            self.error_handler.log_error("SYS-FAIL", msg, es_error_sistema=True)
            resultado["ftp_msg"] = msg
            return resultado
    
    def _ejecutar_envio_automatico(self, modo="AUTOMÁTICO"):
        """Procesa estrictamente en FILA INDIA SIN CONGELAR EL SISTEMA."""
        # 1. BLOQUEO MILIMÉTRICO (Solo para checar si ya estamos ocupados)
        with self._lock:
            if self._is_processing:
                return
            self._is_processing = True

        # 2. PROCESO DE RED (Totalmente libre de candados)
        inicio_sesion = datetime.now()
        resultados_sesion = []
        
        try:
            import os
            directorio = self.config.get("directorio_pendientes", str(path_manager.get_pendientes_usb_path()))
            if not os.path.exists(directorio):
                return
            
            archivos = [os.path.join(directorio, f) for f in os.listdir(directorio) if f.endswith('.txt') or f.endswith('.email_pending')]
            
            if not archivos:
                self._last_successful_run = datetime.now()
                return
            
            archivos.sort(key=os.path.getmtime)
            
            exitosos = 0
            for ruta_archivo in archivos:
                nombre = os.path.basename(ruta_archivo)
                
                try:
                    fecha_archivo = datetime.fromtimestamp(os.path.getmtime(ruta_archivo)).isoformat()
                except OSError:
                    fecha_archivo = datetime.now().isoformat()
                
                res = self._procesar_archivo_individual(ruta_archivo)
                
                resultados_sesion.append({
                    "archivo": nombre,
                    "fecha_archivo": fecha_archivo,
                    "ftp_ok": res["ftp_ok"],
                    "ftp_respuesta": res["ftp_msg"], 
                    "email_ok": res["email_ok"],
                    "timestamp_envio": datetime.now().isoformat()
                })
                
                if res["exito_completo"]:
                    exitosos += 1
            
            if resultados_sesion:
                self._guardar_log_envio_detallado(inicio_sesion, resultados_sesion, modo)
            
            if exitosos > 0:
                self._last_successful_run = datetime.now()

        except Exception as e:
            self.logger.error(f"Error en el ciclo de ejecución: {str(e)}")
        finally:
            # 3. LIBERACIÓN DEL ESTADO (Para que el siguiente ciclo pueda entrar)
            with self._lock:
                self._is_processing = False
    
    def actualizar_hora_envio(self, nueva_hora: str):
        with self._lock:
            try:
                hora, minuto = map(int, nueva_hora.split(':'))
                if not (0 <= hora <= 23 and 0 <= minuto <= 59):
                    raise ValueError("Hora inválida")
                
                self.config["hora_envio"] = nueva_hora
                
                if self._is_running and self._scheduler:
                    self.detener()
                    time.sleep(1)
                    self.iniciar()
                return True
            except Exception as e:
                return False
    
    def iniciar(self):
        """Inicia los cronómetros correctos de envío y reintento."""
        with self._lock:
            if self._is_running:
                return
            try:
                if self._scheduler:
                    try: self._scheduler.shutdown(wait=False)
                    except: pass
                
                self._scheduler = BackgroundScheduler(daemon=True, timezone='America/Mexico_City')
                
                hora_str = self.config.get("hora_envio", "23:59")
                hora, minuto = map(int, hora_str.split(':'))
                
                # TAREA 1: El reloj maestro que la UI lee
                self._scheduler.add_job(
                    func=self._ejecutar_envio_automatico,
                    trigger=CronTrigger(hour=hora, minute=minuto),
                    id='envio_automatico_diario',
                    name=f'Envío programado {hora_str}',
                    replace_existing=True
                )
                
                # TAREA 2: El martillo de reintentos
                self._scheduler.add_job(
                    func=self._ejecutar_envio_automatico,
                    trigger='interval',
                    minutes=15,
                    id='persistencia_industrial',
                    name='Reintento continuo FTP/Email',
                    replace_existing=True
                )
                
                self._scheduler.start()
                self._is_running = True
            except Exception as e:
                self.error_handler.log_error("010", f"Error de inicio: {e}")
                self._is_running = False
    
    def detener(self):
        with self._lock:
            try:
                if self._scheduler and self._is_running:
                    self._scheduler.shutdown(wait=True)
                    self._is_running = False
            except: pass
    
    def forzar_envio_inmediato(self) -> Dict[str, Any]:
        """Cálculo real de archivos transmitidos en envío manual."""
        resultado = {"exitosos": 0, "fallidos": 0, "total": 0, "tiempo_segundos": 0, "mensaje": ""}
        try:
            start = datetime.now()
            
            estado_antes = self.obtener_estado()
            pendientes_antes = estado_antes.get("archivos_pendientes", 0) + estado_antes.get("archivos_fallidos_email", 0)
            
            self._ejecutar_envio_automatico(modo="MANUAL")
            
            estado_despues = self.obtener_estado()
            pendientes_despues = estado_despues.get("archivos_pendientes", 0) + estado_despues.get("archivos_fallidos_email", 0)
            
            exitosos_reales = pendientes_antes - pendientes_despues
            if exitosos_reales < 0: exitosos_reales = 0
            
            resultado["total"] = pendientes_antes
            resultado["exitosos"] = exitosos_reales
            resultado["fallidos"] = pendientes_despues
            resultado["tiempo_segundos"] = (datetime.now() - start).total_seconds()
            resultado["mensaje"] = "Proceso manual finalizado."
            
        except Exception as e:
            resultado["mensaje"] = f"Error crítico: {str(e)}"
            self.error_handler.log_error("010", resultado["mensaje"])
        
        return resultado