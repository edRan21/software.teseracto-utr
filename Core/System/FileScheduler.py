# TESERACTO-UTR/Core/System/FileScheduler.py

import os
import time
import threading
import logging
import json
import shutil
from datetime import datetime
from typing import Callable, Dict, Any, List, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from Core.Network.IFileTransfer import IFileTransfer
from Core.System.ErrorHandler import ErrorHandler
from Core.System.PathManager import path_manager

class FileScheduler:
    """
    Planificador de Telemetría Industrial.
    Implementa APScheduler para sincronización cronométrica y gestión de colas FIFO 
    para la recuperación de datos tras caídas prolongadas de red.
    """
    def __init__(
        self,
        transfer_service: IFileTransfer,
        email_manager: Any,
        api_manager: Any,
        config: Dict[str, Any],
        get_plantilla_fn: Callable[[str], Dict[str, Any]],
        error_handler: ErrorHandler,
    ):
        # Inyección de Dependencias (DIP)
        self.transfer_service = transfer_service
        self.email_manager = email_manager 
        self.api_manager = api_manager # NUEVO
        self.config = config
        self.get_plantilla = get_plantilla_fn
        self.error_handler = error_handler
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self._scheduler: Optional[BackgroundScheduler] = None
        self._lock = threading.RLock()
        self._is_running = False
        self._is_processing = False
        self._last_successful_run: Optional[datetime] = None
        self._consecutive_failures = 0
        
        # Rutas dinámicas seguras para entornos empaquetados
        self.backup_dir = path_manager.get_writable_path() / "backups_envios"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._verificar_estructura_directorios()

    def actualizar_configuracion_completa(self, ftp_config: Dict[str, Any], email_config: Optional[Dict[str, Any]] = None):
        with self._lock:
            if hasattr(self.transfer_service, 'actualizar_configuracion'):
                self.transfer_service.actualizar_configuracion(ftp_config)
            if email_config and hasattr(self.email_manager, 'actualizar_configuracion'):
                self.email_manager.actualizar_configuracion(email_config)
            
            self.config["hora_envio"] = ftp_config.get("hora_envio", self.config.get("hora_envio", "23:59"))
            self.config["ruta_remota"] = ftp_config.get("ruta_remota", self.config.get("ruta_remota", "/"))
            
            # Reinicio cronométrico en caliente
            if self._is_running:
                self.detener()
                time.sleep(1)
                self.iniciar()

    def _verificar_estructura_directorios(self):
        try:
            pendientes_dir = self.config.get("directorio_pendientes", str(path_manager.get_pendientes_usb_path()))
            os.makedirs(pendientes_dir, exist_ok=True)
        except Exception as e:
            self.error_handler.log_error("010", "Fallo al inicializar topología de directorios", es_error_sistema=True)

    # =========================================================================
    # OBSERVABILIDAD PARA LA INTERFAZ GRÁFICA
    # =========================================================================
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
                except Exception: pass
            
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
                except Exception: pass
        
        # Ordenamiento crítico para la UI
        return sorted(detalles, key=lambda x: x["antiguedad_dias"], reverse=True)

    # =========================================================================
    # LÓGICA DE AUDITORÍA Y RESPALDO
    # =========================================================================
    def _crear_respaldo_seguro(self, ruta_archivo: str) -> bool:
        try:
            if not os.path.exists(ruta_archivo):
                return True
            
            filename = os.path.basename(ruta_archivo)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"{filename}.{timestamp}.backup"
            
            shutil.copy2(ruta_archivo, backup_file)
            
            # Rotación de logs inmutable (Mantiene los últimos 50)
            backups = list(self.backup_dir.glob("*.backup"))
            if len(backups) > 50:
                for old_backup in sorted(backups)[:len(backups)-50]:
                    try: old_backup.unlink()
                    except Exception: pass
            return True
        except Exception as e:
            self.logger.error(f"Error I/O creando respaldo: {e}")
            return False

    def _guardar_log_envio_detallado(self, inicio: datetime, resultados: list, modo: str):
        try:
            log_dir = path_manager.get_writable_path() / "logs_envios"
            log_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = inicio.strftime('%Y%m%d_%H%M%S')
            log_file = log_dir / f"envio_{timestamp}.json"
            
            log_data = {
                "sesion_inicio": inicio.isoformat(),
                "modo": modo,
                "servidores_activos": {
                    "protocolo_primario": True,
                    "email_activo": self.email_manager is not None
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
                
        except Exception as e:
            self.logger.error(f"Excepción de auditoría JSON: {e}")

    # =========================================================================
    # MOTOR DE TRANSACCIÓN AISLADA
    # =========================================================================
    def _procesar_archivo_individual(self, ruta_archivo: str) -> Dict[str, Any]:
        """Procesa protocolos de forma agnóstica con aislamiento estricto de excepciones."""
        filename = os.path.basename(ruta_archivo)
        resultado = {
            "ftp_ok": False,
            "ftp_msg": "No ejecutado",
            "email_ok": False,
            "api_ok": False,
            "exito_completo": False
        }
        
        try:
            plantilla = self.get_plantilla(filename)
            nombre_remoto = plantilla.get("nombre_remoto", filename)
            ruta_base = self.config.get("ruta_remota", "/").rstrip('/')
            ruta_remota = f"{ruta_base}/{nombre_remoto}" if ruta_base != "/" else f"/{nombre_remoto}"

            es_email_pendiente = filename.endswith('.email_pending')
            es_api_pendiente = filename.endswith('.api_pending')
            
            # PROTOCOLO 1: FTP
            try:
                if not es_email_pendiente and not es_api_pendiente:
                    ftp_ok, ftp_msg = self.transfer_service.enviar_archivo(ruta_archivo, ruta_remota)
                    resultado["ftp_ok"] = ftp_ok
                    resultado["ftp_msg"] = ftp_msg
                    if not ftp_ok:
                        self.error_handler.log_error("FTP-550", f"Fallo en {filename}: {ftp_msg}", es_error_sistema=True)
                else:
                    resultado["ftp_ok"] = True
                    resultado["ftp_msg"] = "Previa exitosa"
            except Exception as e_ftp:
                resultado["ftp_msg"] = f"Excepción FTP: {e_ftp}"
                self.error_handler.log_error("FTP-550", resultado["ftp_msg"], es_error_sistema=True)

            # PROTOCOLO 2: Email
            try:
                if not es_api_pendiente:
                    if hasattr(self.email_manager, 'enviar_archivo'):
                        resultado["email_ok"] = self.email_manager.enviar_archivo(ruta_archivo, filename)
                    if not resultado["email_ok"]:
                        self.error_handler.log_error("EMAIL-FAIL", f"Fallo Email en {filename}", es_error_sistema=True)
                else:
                    resultado["email_ok"] = True
            except Exception as e_email:
                self.error_handler.log_error("EMAIL-FAIL", f"Excepción Email: {e_email}", es_error_sistema=True)

            # PROTOCOLO 3: API Web (NUEVO)
            try:
                usar_api = self.config.get("usar_api", False)
                if usar_api and hasattr(self.api_manager, 'enviar_archivo'):
                    api_ok, api_msg = self.api_manager.enviar_archivo(ruta_archivo, filename)
                    resultado["api_ok"] = api_ok
                    if not api_ok:
                        self.error_handler.log_error("API-FAIL", f"Fallo API: {api_msg}", es_error_sistema=True)
                else:
                    resultado["api_ok"] = True # Se marca true si la API no está habilitada en configuración global
            except Exception as e_api:
                self.error_handler.log_error("API-FAIL", f"Excepción API: {e_api}", es_error_sistema=True)

            # EVALUACIÓN DE MÁQUINA DE ESTADOS Y ROTACIÓN DE BACKLOG
            if resultado["ftp_ok"] and resultado["email_ok"] and resultado["api_ok"]:
                resultado["exito_completo"] = True
                if self._crear_respaldo_seguro(ruta_archivo):
                    try: os.remove(ruta_archivo)
                    except Exception: pass
            else:
                # Rotación descendente de FSM
                if resultado["ftp_ok"] and resultado["email_ok"] and not resultado["api_ok"]:
                    if not es_api_pendiente:
                        nueva_ruta = ruta_archivo.replace('.email_pending', '').replace('.txt', '') + '.api_pending'
                        try: os.rename(ruta_archivo, nueva_ruta)
                        except Exception: pass
                elif resultado["ftp_ok"] and not resultado["email_ok"]:
                    if not es_email_pendiente:
                        nueva_ruta = ruta_archivo.replace('.txt', '') + '.email_pending'
                        try: os.rename(ruta_archivo, nueva_ruta)
                        except Exception: pass
            
            return resultado

        except Exception as e:
            # Captura únicamente errores estructurales (ej. fallos leyendo el sistema de archivos)
            msg = f"Error estructural crítico procesando {filename}: {str(e)}"
            self.error_handler.log_error("SYS-FAIL", msg, es_error_sistema=True)
            if not resultado["ftp_ok"] and resultado["ftp_msg"] == "No ejecutado":
                resultado["ftp_msg"] = msg
            return resultado

    # =========================================================================
    # ORQUESTADOR DE COLAS FIFO (RESILIENCIA INDUSTRIAL)
    # =========================================================================
    def _ejecutar_envio_automatico(self, modo="AUTOMÁTICO"):
        with self._lock:
            if self._is_processing:
                return
            self._is_processing = True

        inicio_sesion = datetime.now()
        resultados_sesion = []
        
        try:
            directorio = self.config.get("directorio_pendientes", str(path_manager.get_pendientes_usb_path()))
            hora_envio_str = self.config.get("hora_envio", "23:59")
            
            try:
                hora_envio_obj = datetime.strptime(hora_envio_str, "%H:%M").time()
            except ValueError:
                hora_envio_obj = datetime.strptime("23:59", "%H:%M").time()
                 
            if not os.path.exists(directorio):
                return
            
            archivos = [os.path.join(directorio, f) for f in os.listdir(directorio) if f.endswith(('.txt', '.email_pending', '.api_pending'))]
            if not archivos:
                self._last_successful_run = datetime.now()
                return
            
            # Ordenamiento determinista FIFO (First-In, First-Out)
            archivos.sort(key=os.path.getmtime)
            
            exitosos = 0
            for ruta_archivo in archivos:
                nombre = os.path.basename(ruta_archivo)
                ahora = datetime.now()
                
                try:
                    fecha_mtime = datetime.fromtimestamp(os.path.getmtime(ruta_archivo))
                    fecha_archivo = fecha_mtime.isoformat() 
                except OSError:
                    fecha_mtime = ahora
                    fecha_archivo = ahora.isoformat()
                
                # EVALUACIÓN DE REZAGO (BACKLOG PROCESSING)
                debe_enviarse = False
                
                if modo == "MANUAL":
                    debe_enviarse = True
                else:
                    if fecha_mtime.date() < ahora.date():
                        # Si es un archivo de días anteriores (Backlog), se transmite inmediatamente
                        debe_enviarse = True
                    elif fecha_mtime.date() == ahora.date():
                        # Si es del día actual, evalúa la ventana de tiempo
                        hora_envio_hoy = datetime.combine(ahora.date(), hora_envio_obj)
                        if ahora >= hora_envio_hoy:
                            debe_enviarse = True
                        else:
                            debe_enviarse = False
                    else:
                        debe_enviarse = False
                        
                if not debe_enviarse:
                    continue
                
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
                self._consecutive_failures = 0
            elif resultados_sesion:
                self._consecutive_failures += 1

        except Exception as e:
            self.logger.error(f"Falla de concurrencia en planificador: {str(e)}")
        finally:
            with self._lock:
                self._is_processing = False

    # =========================================================================
    # GESTIÓN DE CICLO DE VIDA (APScheduler)
    # =========================================================================
    def iniciar(self):
        with self._lock:
            if self._is_running:
                return
            try:
                if self._scheduler:
                    try: self._scheduler.shutdown(wait=False)
                    except Exception: pass
                
                # CORRECCIÓN: Adopción del reloj nativo del sistema operativo (Sin dependencias externas)
                self._scheduler = BackgroundScheduler(daemon=True)
                
                hora_str = self.config.get("hora_envio", "23:59")
                hora, minuto = map(int, hora_str.split(':'))
                
                # TAREA 1: Cronómetro oficial
                self._scheduler.add_job(
                    func=self._ejecutar_envio_automatico,
                    trigger=CronTrigger(hour=hora, minute=minuto),
                    id='envio_automatico_diario',
                    name=f'Transmisión Cron {hora_str}',
                    replace_existing=True
                )
                
                # TAREA 2: Recuperación de red (Reintento de backlog)
                self._scheduler.add_job(
                    func=self._ejecutar_envio_automatico,
                    trigger='interval',
                    minutes=15,
                    id='persistencia_industrial',
                    name='Recuperación de Red',
                    replace_existing=True
                )
                
                self._scheduler.start()
                self._is_running = True
            except Exception as e:
                self.error_handler.log_error("010", f"Error iniciando APScheduler: {e}")
                self._is_running = False
    
    def detener(self):
        with self._lock:
            try:
                if self._scheduler and self._is_running:
                    self._scheduler.shutdown(wait=True)
                    self._is_running = False
            except Exception: pass
    
    def forzar_envio_inmediato(self) -> Dict[str, Any]:
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
            resultado["mensaje"] = "Transmisión manual completada."
            
        except Exception as e:
            resultado["mensaje"] = f"Error crítico: {str(e)}"
            self.error_handler.log_error("010", resultado["mensaje"])
        
        return resultado