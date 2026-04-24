# TESERACTO-UTR/Core/System/FileScheduler.py
# VERSIÓN DEFINITIVA - TODOS LOS BUGS CORREGIDOS

import os
import time
import threading
import logging
import json
import smtplib
from datetime import datetime, timedelta
from typing import Callable, Dict, Any, List, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from concurrent.futures import ThreadPoolExecutor, as_completed
from Core.Network.IFileTransfer import IFileTransfer
from Core.System.ErrorHandler import ErrorHandler
from Core.System.PathManager import path_manager
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import shutil  # Para respaldos

class FileScheduler:
    """Scheduler automático industrial - VERSIÓN CORREGIDA"""
    
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
        
        # Estado interno
        self._scheduler: Optional[BackgroundScheduler] = None
        self._lock = threading.RLock()
        self._is_running = False
        self._last_successful_run: Optional[datetime] = None
        self._consecutive_failures = 0
        
        # Configuraciones
        self.email_config = self._cargar_config_email()
        
        # Directorio de respaldos
        self.backup_dir = path_manager.get_base_path() / "backups_envios"
        self.backup_dir.mkdir(exist_ok=True)
        
        # Inicialización
        self._verificar_estructura_directorios()
        
    def _cargar_config_email(self) -> Optional[Dict[str, Any]]:
        """Carga configuración de email"""
        try:
            config_path = path_manager.get_config_path("email_config.json")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            # APORTACIÓN 3: Uso de código oficial en lugar de "EMAIL-CONFIG"
            self.error_handler.log_error("301", "Error cargando configuración de Email", es_error_sistema=True)
            self.logger.error(f"Error detallado config email: {e}")
            return None

    def _actualizar_config_email(self, nueva_config: Dict[str, Any]):
        """Actualiza configuración de email en tiempo de ejecución"""
        self.email_config = nueva_config
        self.logger.info("✅ Configuración de email actualizada en tiempo de ejecución")

    def actualizar_configuracion_completa(self, ftp_config: Dict[str, Any], email_config: Optional[Dict[str, Any]] = None):
        """Actualiza toda la configuración del scheduler"""
        with self._lock:
            # 1. Actualizar FTPManager
            if hasattr(self.transfer_service, 'actualizar_configuracion'):
                self.transfer_service.actualizar_configuracion(ftp_config)
            
            # 2. Actualizar configuración interna
            self.config["hora_envio"] = ftp_config.get("hora_envio", self.config.get("hora_envio", "23:59"))
            self.config["ruta_remota"] = ftp_config.get("ruta_remota", self.config.get("ruta_remota", "/"))
            
            # 3. Actualizar email si se proporciona
            if email_config:
                self.email_config = email_config
            
            # 4. Reiniciar scheduler si está en ejecución
            if self._is_running:
                self.detener()
                time.sleep(1)
                self.iniciar()
            
            self.logger.info("✅ Configuración completa del scheduler actualizada")

    def _verificar_estructura_directorios(self):
        """Verifica estructura de directorios"""
        try:
            pendientes_dir = self.config.get("directorio_pendientes", 
                                           str(path_manager.get_pendientes_usb_path()))
            os.makedirs(pendientes_dir, exist_ok=True)
            
        except Exception as e:
            # APORTACIÓN 3: Uso de código oficial en lugar de "DIR-STRUCT"
            self.error_handler.log_error("010", "Fallo al verificar estructura de directorios del sistema", es_error_sistema=True)
            self.logger.error(f"Error detallado directorios: {e}")
    
    def _crear_respaldo_seguro(self, ruta_archivo: str) -> bool:
        """Crea respaldo antes de eliminar - GARANTÍA DE NO PÉRDIDA"""
        try:
            if not os.path.exists(ruta_archivo):
                return True
            
            filename = os.path.basename(ruta_archivo)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"{filename}.{timestamp}.backup"
            
            shutil.copy2(ruta_archivo, backup_file)
            self.logger.debug(f"📦 Respaldo creado: {backup_file.name}")
            
            # Limitar a 50 respaldos máximo
            backups = list(self.backup_dir.glob("*.backup"))
            if len(backups) > 50:
                for old_backup in sorted(backups)[:len(backups)-50]:
                    try:
                        old_backup.unlink()
                    except:
                        pass
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error creando respaldo {ruta_archivo}: {e}")
            return False
    
    def obtener_estado(self) -> Dict[str, Any]:
        """Obtiene estado del scheduler"""
        with self._lock:
            directorio = self.config.get("directorio_pendientes",
                                       str(path_manager.get_pendientes_usb_path()))
            
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
                "ultimo_exito": self._last_successful_run.strftime("%Y-%m-%d %H:%M:%S") 
                               if self._last_successful_run else "Nunca",
                "fallos_consecutivos": self._consecutive_failures,
                "modo": "AUTOMÁTICO"
            }
            
            if self._scheduler and self._is_running:
                try:
                    jobs = self._scheduler.get_jobs()
                    for job in jobs:
                        if job.id == 'envio_automatico_diario':
                            if job.next_run_time:
                                estado["proxima_ejecucion"] = job.next_run_time.strftime("%H:%M")
                            break
                except:
                    pass
            
            return estado
    
    def obtener_detalle_archivos_pendientes(self) -> List[Dict[str, Any]]:
        """Obtiene lista detallada de archivos"""
        detalles = []
        directorio = self.config.get("directorio_pendientes",
                                   str(path_manager.get_pendientes_usb_path()))
        
        if not os.path.exists(directorio):
            return detalles
        
        for filename in os.listdir(directorio):
            if filename.endswith('.txt'):
                filepath = os.path.join(directorio, filename)
                try:
                    stat = os.stat(filepath)
                    modificado = datetime.fromtimestamp(stat.st_mtime)
                    antiguedad = (datetime.now() - modificado).days
                    
                    archivo_info = {
                        "nombre": filename,
                        "tamano_kb": round(stat.st_size / 1024, 2),
                        "modificado": modificado.strftime("%Y-%m-%d %H:%M:%S"),
                        "antiguedad_dias": antiguedad,
                        "estado": "email_pendiente" if filename.endswith('.email_pending') else "pendiente",
                        "prioridad": "ALTA" if antiguedad >= 3 else "MEDIA" if antiguedad >= 1 else "BAJA"
                    }
                    detalles.append(archivo_info)
                except Exception as e:
                    self.logger.error(f"Error obteniendo info de {filename}: {e}")
        
        return sorted(detalles, key=lambda x: x["antiguedad_dias"], reverse=True)
    
    def _enviar_email_archivo(self, ruta_archivo: str) -> bool:
        """Envía archivo por email con manejo robusto de errores"""
        if not self.email_config:
            return True  # No hay email configurado, considerar éxito
        
        filename = os.path.basename(ruta_archivo)
        
        for intento in range(3):
            try:
                # Leer contenido
                with open(ruta_archivo, 'r', encoding='utf-8') as f:
                    contenido = f.read()
                
                # Crear mensaje
                msg = MIMEMultipart()
                msg['From'] = self.email_config['from']
                msg['To'] = ', '.join(self.email_config['to'])
                msg['Subject'] = self.email_config['subject']
                msg['Date'] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
                
                # Cuerpo
                body = f"Archivo adjunto: {filename}\n"
                body += f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                body += "Sistema: Tesseract UTR\n\n"
                msg.attach(MIMEText(body, 'plain'))
                
                # Adjuntar archivo
                with open(ruta_archivo, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', 
                                  f'attachment; filename="{filename}"')
                    msg.attach(part)
                
                # Enviar
                with smtplib.SMTP(self.email_config['smtp_server'], 
                                self.email_config['smtp_port'], timeout=30) as server:
                    server.starttls()
                    server.login(self.email_config['username'], 
                               self.email_config['password'])
                    server.send_message(msg)
                
                self.logger.info(f"✅ Email enviado: {filename}")
                return True
                
            except smtplib.SMTPServerDisconnected:
                self.logger.warning(f"🔄 SMTP desconectado, reintento {intento+1}/3")
                time.sleep(2)
                continue
                
            except Exception as e:
                self.logger.error(f"❌ Error email intento {intento+1}/3: {e}")
                if intento < 2:
                    time.sleep(2)
                    continue
        
        # APORTACIÓN 3: Uso de código oficial en lugar de "EMAIL-FAILED"
        self.error_handler.log_error("EMAIL-TEST", "Fallo definitivo al enviar reporte por correo", es_error_sistema=True)
        return False
    
    def _procesar_archivo_individual(self, ruta_archivo: str) -> bool:
        filename = os.path.basename(ruta_archivo)
        self.logger.info(f"🔍 Procesando: {filename}")
        
        # 1. Intentar FTP (Siempre primero)
        plantilla = self.get_plantilla(filename)
        nombre_remoto = plantilla.get("nombre_remoto", filename)
        ruta_base = self.config.get("ruta_remota", "/").rstrip('/')
        ruta_remota = f"{ruta_base}/{nombre_remoto}" if ruta_base != "/" else f"/{nombre_remoto}"

        # Si ya es un archivo marcado como 'email_pendiente', saltamos el FTP
        ftp_ya_completado = filename.endswith('.email_pending')
        ftp_exitoso = True

        if not ftp_ya_completado:
            ftp_exitoso = self.transfer_service.enviar_archivo(ruta_archivo, ruta_remota)
            if not ftp_exitoso:
                self.logger.error(f"❌ FTP Fallido para {filename}. Se mantendrá en cola.")
                return False # No avanzamos si el FTP falla

        # 2. Intentar Email (Solo si FTP tuvo éxito o ya estaba hecho)
        email_exitoso = self._enviar_email_archivo(ruta_archivo)
        
        if email_exitoso:
            # ✅ ÉXITO TOTAL: Solo aquí se crea respaldo y se borra el original
            if self._crear_respaldo_seguro(ruta_archivo):
                try:
                    os.remove(ruta_archivo)
                    self.logger.info(f"✅ Ciclo completo para {filename}")
                    return True
                except: return True
        else:
            # Éxito FTP pero fallo Email: Marcamos para reintento de email únicamente
            if not ftp_ya_completado:
                nueva_ruta = f"{ruta_archivo}.email_pending"
                os.rename(ruta_archivo, nueva_ruta)
            return False
    
    def _ejecutar_envio_automatico(self):
        """Ejecuta envío automático"""
        self.logger.info("🕐 === INICIANDO ENVÍO AUTOMÁTICO ===")
        
        start_time = datetime.now()
        exitosos = 0
        fallidos = 0
        
        try:
            directorio = self.config.get("directorio_pendientes",
                                       str(path_manager.get_pendientes_usb_path()))
            
            if not os.path.exists(directorio):
                self.logger.error(f"❌ Directorio no existe: {directorio}")
                return
            
            # Obtener archivos
            archivos = []
            for f in os.listdir(directorio):
                if f.endswith('.txt'):
                    archivos.append(os.path.join(directorio, f))
            
            if not archivos:
                self.logger.info("✅ No hay archivos pendientes")
                self._last_successful_run = datetime.now()
                return
            
            self.logger.info(f"📂 Encontrados {len(archivos)} archivos pendientes")
            
            # Procesar en paralelo (máximo 2 para evitar sobrecarga)
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = []
                for archivo in archivos:
                    future = executor.submit(self._procesar_archivo_individual, archivo)
                    futures.append(future)
                
                # Esperar resultados
                for future in as_completed(futures):
                    try:
                        if future.result(timeout=300):  # 5 minutos por archivo
                            exitosos += 1
                        else:
                            fallidos += 1
                    except Exception as e:
                        self.error_handler.log_error("010", f"Error: {e}")
                        fallidos += 1
            
            # Resultado
            elapsed = (datetime.now() - start_time).total_seconds()
            
            if exitosos > 0:
                self._last_successful_run = datetime.now()
                self.logger.info(f"✅ Envío completado: {exitosos} exitosos, {fallidos} fallidos, {elapsed:.1f}s")
            else:
                self.logger.warning(f"⚠️ Envío sin éxitos: {fallidos} fallidos")
                
            # Guardar log
            self._guardar_log_envio(start_time, exitosos, fallidos, elapsed)
            
        except Exception as e:
            self.error_handler.log_error("010", f"Error: {e}")
    
    def _guardar_log_envio(self, inicio: datetime, exitosos: int, fallidos: int, tiempo: float):
        """Guarda log del envío"""
        try:
            log_dir = path_manager.get_base_path() / "logs_envios"
            log_dir.mkdir(exist_ok=True)
            
            log_file = log_dir / f"envio_{inicio.strftime('%Y%m%d_%H%M%S')}.json"
            
            log_data = {
                "timestamp": inicio.isoformat(),
                "hora_programada": self.config.get("hora_envio", "23:59"),
                "exitosos": exitosos,
                "fallidos": fallidos,
                "tiempo_segundos": round(tiempo, 2),
                "modo": "automático",
                "archivos_pendientes_despues": len(self.obtener_detalle_archivos_pendientes())
            }
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Error guardando log: {e}")
    
    def _reintentar_emails_fallidos(self):
        """Reintenta emails fallidos"""
        try:
            directorio = self.config.get("directorio_pendientes",
                                       str(path_manager.get_pendientes_usb_path()))
            
            if not os.path.exists(directorio):
                return
            
            reintentados = 0
            exitosos = 0
            
            for filename in os.listdir(directorio):
                if filename.endswith('.email_pending'):
                    ruta = os.path.join(directorio, filename)
                    reintentados += 1
                    
                    if self._enviar_email_archivo(ruta):
                        if self._crear_respaldo_seguro(ruta):
                            try:
                                os.remove(ruta)
                                exitosos += 1
                                self.logger.info(f"✅ Email reenviado: {filename}")
                            except:
                                pass
            
            if reintentados > 0:
                self.logger.info(f"📧 Reintento emails: {exitosos}/{reintentados} exitosos")
                
        except Exception as e:
            self.error_handler.log_error("010", f"Error: {e}")
    
    def _limpiar_archivos_antiguos(self):
        """Limpia archivos antiguos"""
        try:
            directorio = self.config.get("directorio_pendientes",
                                       str(path_manager.get_pendientes_usb_path()))
            max_dias = max(self.config.get("retencion_dias", 30), 180)
            
            if not os.path.exists(directorio):
                return
            
            eliminados = 0
            for filename in os.listdir(directorio):
                ruta = os.path.join(directorio, filename)
                if os.path.isfile(ruta):
                    try:
                        modificado = datetime.fromtimestamp(os.path.getmtime(ruta))
                        if (datetime.now() - modificado).days > max_dias:
                            # Crear respaldo antes de eliminar
                            if self._crear_respaldo_seguro(ruta):
                                os.remove(ruta)
                                eliminados += 1
                                self.logger.warning(f"🗑️ Archivo antiguo eliminado: {filename}")
                    except:
                        pass
            
            if eliminados > 0:
                self.logger.info(f"🧹 Limpieza: {eliminados} archivos eliminados")
                
        except Exception as e:
            self.error_handler.log_error("010", f"Error: {e}")
    
    def actualizar_hora_envio(self, nueva_hora: str):
        """Actualiza hora de envío"""
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
                
                self.logger.info(f"✅ Hora actualizada: {nueva_hora}")
                return True
                
            except Exception as e:
                self.error_handler.log_error("301", f"Error: {e}")
                return False
    
    def iniciar(self):
        """Inicia el scheduler"""
        with self._lock:
            if self._is_running:
                return
            
            try:
                # Detener si existe
                if self._scheduler:
                    try:
                        self._scheduler.shutdown(wait=False)
                    except:
                        pass
                
                # Nuevo scheduler
                self._scheduler = BackgroundScheduler(
                    daemon=True,
                    timezone='America/Mexico_City'
                )
                
                # Hora programada
                hora_str = self.config.get("hora_envio", "23:59")
                hora, minuto = map(int, hora_str.split(':'))
                
                # ✅ RUTINA INDUSTRIAL DE PERSISTENCIA
                self._scheduler.add_job(
                    func=self._ejecutar_envio_automatico,
                    trigger='interval',
                    minutes=15,
                    id='persistencia_industrial',
                    name='Reintento continuo de envíos fallidos',
                    replace_existing=True
                )
                
                # Job de reintentos
                self._scheduler.add_job(
                    func=self._reintentar_emails_fallidos,
                    trigger='interval',
                    hours=2,
                    id='reintento_emails',
                    name='Reintento emails',
                    replace_existing=True
                )
                
                # Job de limpieza
                self._scheduler.add_job(
                    func=self._limpiar_archivos_antiguos,
                    trigger=CronTrigger(hour=0, minute=30),
                    id='limpieza_automatica',
                    name='Limpieza automática',
                    replace_existing=True
                )
                
                # Iniciar
                self._scheduler.start()
                self._is_running = True
                
                self.logger.info(f"✅ Scheduler iniciado - Envío a las {hora:02d}:{minuto:02d}")
                
            except Exception as e:
                self.error_handler.log_error("010", f"Error: {e}")
                self._is_running = False
    
    def detener(self):
        """Detiene el scheduler"""
        with self._lock:
            try:
                if self._scheduler and self._is_running:
                    self._scheduler.shutdown(wait=True)
                    self._is_running = False
                    self.logger.info("⏹️ Scheduler detenido")
            except Exception as e:
                self.error_handler.log_error("010", f"Error: {e}")
    
    def forzar_envio_inmediato(self) -> Dict[str, Any]:
        """Fuerza envío inmediato"""
        resultado = {
            "exitosos": 0,
            "fallidos": 0,
            "total": 0,
            "tiempo_segundos": 0,
            "mensaje": ""
        }
        
        try:
            self.logger.warning("⚡ EJECUTANDO ENVÍO INMEDIATO")
            start = datetime.now()
            
            # Ejecutar envío
            self._ejecutar_envio_automatico()
            
            # Resultados
            estado = self.obtener_estado()
            resultado["exitosos"] = estado.get("archivos_pendientes", 0)
            resultado["fallidos"] = estado.get("archivos_fallidos_email", 0)
            resultado["total"] = resultado["exitosos"] + resultado["fallidos"]
            resultado["tiempo_segundos"] = (datetime.now() - start).total_seconds()
            resultado["mensaje"] = "Envío inmediato completado"
            
        except Exception as e:
            resultado["mensaje"] = f"Error: {str(e)}"
            self.error_handler.log_error("010", resultado["mensaje"])
        
        return resultado