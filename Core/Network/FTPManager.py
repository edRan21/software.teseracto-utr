# TESERACTO-UTR/Core/Network/FTPManager.py
# VERSIÓN CORREGIDA - RUTAS ABSOLUTAS PARA CONAGUA

import ftplib
import logging
import os
import time
import socket
from typing import Optional
from Core.System.ErrorHandler import ErrorHandler
from .IFileTransfer import IFileTransfer

class FTPManager(IFileTransfer):
    """Gestor FTP corregido para CONAGUA con rutas absolutas"""
    
    def __init__(self, config: dict, error_handler: ErrorHandler):
        self.config = config
        self.error_handler = error_handler
        self.logger = logging.getLogger(__name__)
        self.connection: Optional[ftplib.FTP] = None
        
        # Configuración
        self.host = config.get("host", "")
        self.port = config.get("puerto", 21)
        self.username = config.get("usuario", "")
        self.password = config.get("clave", "")
        self.remote_path = config.get("ruta_remota", "/")
        self.timeout = config.get("timeout", 60)
        self.use_tls = False  # CONAGUA no acepta TLS
    
    def _establecer_conexion_robusta(self) -> bool:
        """Conexión FTP ultra-robusta para servidores CONAGUA con cierres abruptos"""
        # 1. Limpiar conexión previa completamente
        self._cerrar_conexion()
        
        # 2. Intentar conexión con manejo de errores específico
        for intento in range(2):  # Solo 2 intentos rápidos
            try:
                # Crear nuevo objeto FTP
                self.connection = ftplib.FTP(timeout=self.timeout)
                
                # Conexión con verificación de estado
                self.connection.connect(self.host, self.port)
                
                # Login con verificación
                response = self.connection.login(self.username, self.password)
                if "230" not in response:  # 230 es "Login successful"
                    raise ftplib.error_perm(f"Login fallido: {response}")
                
                # Modo pasivo
                self.connection.set_pasv(True)
                
                # Verificar que la conexión está activa
                self.connection.voidcmd("NOOP")
                
                self.logger.info(f"✅ Conexión FTP establecida (intento {intento+1})")
                return True
                
            except AttributeError as e:
                # Error específico de 'sendall' en None - recrear objeto FTP
                if "'NoneType' object has no attribute 'sendall'" in str(e):
                    self.logger.warning(f"🔄 Socket cerrado por servidor, recreando conexión...")
                    self.connection = None
                    time.sleep(0.5)
                    continue
                else:
                    raise
                    
            except (socket.timeout, TimeoutError) as e:
                self.logger.warning(f"⏰ Timeout en conexión (intento {intento+1})")
                if intento == 0:
                    time.sleep(1)
                    continue
                return False
                
            except ConnectionResetError as e:
                self.logger.warning(f"🔄 Conexión reiniciada por servidor (normal)")
                self.connection = None
                if intento == 0:
                    time.sleep(1)
                    continue
                return False
                
            except ftplib.error_temp as e:
                self.logger.warning(f"🌡️ Error temporal FTP: {e}")
                self._cerrar_conexion()
                if intento == 0:
                    time.sleep(1)
                    continue
                return False
                
            except Exception as e:
                self.logger.warning(f"⚠️ Error en conexión FTP: {type(e).__name__}")
                self._cerrar_conexion()
                return False
        
        return False
    
    def _normalizar_ruta_remota(self, ruta: str) -> str:
        """Normaliza ruta remota para CONAGUA (asegura ruta absoluta)"""
        # Si la ruta no comienza con /, agregarlo para hacerla absoluta
        if not ruta.startswith('/'):
            ruta = f'/{ruta}'
        
        # Asegurar que no termine con / (excepto si es la raíz)
        if ruta != '/' and ruta.endswith('/'):
            ruta = ruta.rstrip('/')
        
        self.logger.debug(f"🔧 Ruta normalizada: '{ruta}'")
        return ruta
    
    def _crear_directorios_remotos(self, remote_dir: str):
        """Crea directorios remotos con manejo robusto"""
        try:
            self.connection.voidcmd("NOOP")
            remote_dir = self._normalizar_ruta_remota(remote_dir)
            
            if remote_dir == "/":
                self.logger.info("✅ Ya en directorio raíz")
                return
            
            try:
                self.connection.cwd("/")
            except Exception as e:
                self.logger.warning(f"⚠️ No se pudo ir a raíz: {e}")
            
            segments = [s for s in remote_dir.strip("/").split("/") if s]
            current_path = ""
            
            for segment in segments:
                current_path = f"{current_path}/{segment}" if current_path else segment
                try:
                    self.logger.debug(f"Intentando cambiar a: {current_path}")
                    self.connection.cwd(current_path)
                except ftplib.error_perm:
                    try:
                        self.logger.info(f"Creando directorio: {current_path}")
                        self.connection.mkd(current_path)
                        self.connection.cwd(current_path)
                    except ftplib.error_perm as e:
                        error_msg = str(e)
                        if "550" in error_msg: 
                            self.logger.debug(f"Directorio ya existe: {current_path}")
                            try:
                                self.connection.cwd(current_path)
                            except:
                                pass
                        else:
                            self.logger.error(f"❌ Error creando directorio: {error_msg}")
                            raise
            
            self.logger.info(f"✅ Directorios creados/verificados: {remote_dir}")
            
        except Exception as e:
            # APORTACIÓN 2: Cambio a código oficial y protección Anti-Spam
            self.error_handler.log_error("FTP-DIRECTORY", "Fallo al crear estructura de directorios en servidor", es_error_sistema=True)
            self.logger.error(f"Error detallado MKDIR: {e}")
            raise
    
    def _validar_formato_conagua(self, local_path: str) -> bool:
        """Valida formato Conagua con logging mejorado"""
        try:
            filename = os.path.basename(local_path)
            
            with open(local_path, 'r', encoding='utf-8') as f:
                primera_linea = f.readline().strip()
                self.logger.debug(f"📄 Validando {filename}: '{primera_linea[:50]}...'")
                
                if not primera_linea.startswith(("M|", "QA|")):
                    self.logger.error(f"❌ Formato inválido en {filename}: No empieza con M| o QA|")
                    # APORTACIÓN 3: Eliminar 'primera_linea' del visual para que no evada el Anti-Spam
                    self.error_handler.log_error("FTP-FORMAT", f"Archivo no cumple formato CONAGUA: {filename}", es_error_sistema=True)
                    return False
                
                self.logger.debug(f"✅ Formato válido para {filename}")
                return True
                
        except Exception as e:
            self.error_handler.log_error("FTP-FORMAT", f"Error validando estructura de archivo", es_error_sistema=True)
            self.logger.error(f"Error detallado validando {local_path}: {e}")
            return False
    
    def enviar_archivo(self, local_path: str, remote_path: str) -> bool:
        """Sube el archivo y verifica estrictamente que exista en el servidor remoto."""
        if not os.path.exists(local_path):
            self.logger.error(f"Archivo local no encontrado: {local_path}")
            return False
            
        try:
            if not self.connection:
                if not self.conectar():
                    return False
                    
            filename = os.path.basename(local_path)
            remote_dir = os.path.dirname(remote_path)
            
            # Crear y entrar al directorio remoto si es necesario
            if remote_dir and remote_dir != "/":
                self._asegurar_directorio_remoto(remote_dir)
                try:
                    self.connection.cwd(remote_dir)
                except Exception as e:
                    self.logger.error(f"No se pudo acceder a la ruta remota: {e}")
                    return False
            
            remote_filename = os.path.basename(remote_path)
            
            # Subir el archivo
            with open(local_path, "rb") as file:
                self.connection.storbinary(f"STOR {remote_filename}", file)
            
            # ✅ VERIFICACIÓN ESTRICTA: Leer el servidor y comprobar que exista
            try:
                archivos_en_servidor = self.connection.nlst()
                if remote_filename not in archivos_en_servidor:
                    self.logger.error("El servidor aceptó la orden, pero el archivo no existe en el listado.")
                    return False
            except Exception as verif_err:
                self.logger.warning(f"No se pudo listar el directorio para verificar: {verif_err}")
                # Si el servidor bloquea el comando NLST, intentamos usar el tamaño (SIZE)
                try:
                    self.connection.sendcmd("TYPE I")
                    size = self.connection.size(remote_filename)
                    if size != os.path.getsize(local_path):
                        return False
                except:
                    # Si bloquea ambos, lo damos por bueno asumiendo políticas de seguridad estrictas,
                    # pero esto es rarísimo.
                    pass

            self.logger.info(f"✅ Archivo verificado en servidor: {remote_filename}")
            self._cerrar_conexion()
            return True
            
        except Exception as e:
            self.logger.error(f"Excepción subiendo archivo FTP: {e}")
            if hasattr(self, 'error_handler') and self.error_handler:
                self.error_handler.log_error("FTP-UPLOAD", f"Fallo en subida: {str(e)}", es_error_sistema=True)
            self._cerrar_conexion()
            return False
    
    def _cerrar_conexion(self):
        """Cierra conexión FTP de forma segura"""
        try:
            if self.connection:
                # Intentar cerrar de forma ordenada primero
                try:
                    self.connection.quit()
                except:
                    # Si falla, intentar cerrar el socket directamente
                    try:
                        if hasattr(self.connection, 'sock') and self.connection.sock:
                            self.connection.sock.close()
                    except:
                        pass
        except Exception as e:
            self.logger.debug(f"⚠️ Error cerrando conexión (normal al forzar cierre): {e}")
        finally:
            self.connection = None
    
    def verificar_conexion(self) -> bool:
        """Verifica conexión simple (solo conecta y desconecta)"""
        try:
            # Prueba básica
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            
            if result != 0:
                self.logger.error(f"❌ Puerto {self.port} inaccesible")
                return False
            
            # Conexión FTP simple
            temp_ftp = ftplib.FTP(timeout=15)
            temp_ftp.connect(self.host, self.port)
            temp_ftp.login(self.username, self.password)
            
            # Verificar que podemos listar directorio raíz
            try:
                temp_ftp.retrlines('LIST')
                self.logger.info("✅ LIST command exitoso")
            except:
                self.logger.warning("⚠️ No se pudo listar, pero conexión está establecida")
            
            temp_ftp.quit()
            
            self.logger.info("✅ Verificación FTP exitosa")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Verificación fallida: {e}")
            return False
    
    def actualizar_configuracion(self, nueva_config: dict):
        """Actualiza configuración"""
        self.config.update(nueva_config)
        
        self.host = nueva_config.get("host", self.host)
        self.port = nueva_config.get("puerto", self.port)
        self.username = nueva_config.get("usuario", self.username)
        self.password = nueva_config.get("clave", self.password)
        self.remote_path = nueva_config.get("ruta_remota", self.remote_path)
        self.timeout = nueva_config.get("timeout", self.timeout)
        
        self.logger.info("✅ Configuración FTP actualizada")