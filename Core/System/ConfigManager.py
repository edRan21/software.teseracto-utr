# TESERACTO-UTR/Core/System/ConfigManager.py

import json 
import os
import re
import string
import logging
from passlib.hash import pbkdf2_sha256
from typing import Dict, Any, List, Optional
from Core.System.PathManager import path_manager

# Configurar logging
logger = logging.getLogger(__name__)

class ConfigManager:
    _cache = {}
    
    # ✅ CONSTANTES PARA NIPs POR DEFECTO
    NIP_TESERACTO_DEFAULT = "1974"
    NIP_GENERICO_DEFAULT = ""

    @staticmethod
    def _validar_unidad(unidad: str):
        unidades_validas = ["L/s", "m³/h", "GPM"]
        if unidad not in unidades_validas:
            raise ValueError(f"Unidad no válida: {unidad}. Use: {', '.join(unidades_validas)}")
    
    @classmethod
    def cargar_config_general(cls) -> Dict[str, Any]:
        if 'general' in cls._cache:
            return cls._cache['general']
            
        config_path = path_manager.get_config_path("config.json")
        cfg = cls._cargar_archivo(config_path)
        
        # ✅ SOLO CARGAR - NUNCA CREAR ARCHIVOS AUTOMÁTICAMENTE
        if not cfg:
            logger.warning("Archivo config.json no encontrado, usando valores por defecto en memoria")
            return {
                "RFC": "", "NSM": "", "NSUE": "", "NSUT": "",  # ✅ AGREGADO NSUT
                "Lat": 0, "Long": 0,
                "unidad_visualizacion": "m³/h",
                "storage_path": str(path_manager.get_storage_path())
            }
        
        for key in ["RFC", "NSM", "NSUE", "NSUT", "Lat", "Long"]:  # ✅ AGREGADO NSUT
            if key not in cfg:
                raise ValueError(f"Falta '{key}' en la configuración general")
            
        cfg.setdefault("unidad_visualizacion", "m³/h")
        cfg.setdefault("storage_path", str(path_manager.get_storage_path()))
        
        cls._cache['general'] = cfg
        return cfg

    @classmethod
    def guardar_config_general(cls, config: Dict[str, Any]) -> None:
        cls._validar_rfc(config.get("RFC", ""))
        cls._validar_coordenadas(config.get("Lat"), config.get("Long"))
        cls._cache.clear()
        
        if "storage_path" not in config:
            config["storage_path"] = str(path_manager.get_storage_path())
        
        if not cls._es_ruta_windows_valida(config["storage_path"]):
            config["storage_path"] = str(path_manager.get_storage_path())
        
        config_path = path_manager.get_config_path("config.json")
        cls._guardar_archivo(config_path, config)
        
    @staticmethod
    def _es_ruta_windows_valida(ruta: str) -> bool:
        try:
            return len(ruta) > 1 and ruta[1] == ":" and ruta[0].upper() in string.ascii_uppercase
        except:
            return False

    # ✅ NUEVO: MÉTODOS PARA GESTIÓN DE NIPs DE VENTANAS
    @classmethod
    def cargar_nips_ventanas(cls) -> Dict[str, Any]:
        """Carga la configuración de NIPs para ventanas bloqueadas"""
        if 'nips_ventanas' in cls._cache:
            return cls._cache['nips_ventanas']
            
        config_path = path_manager.get_config_path("nip_config.json")
        nips = cls._cargar_archivo(config_path)
        
        if not nips:
            logger.warning("Archivo nip_config.json no encontrado, creando configuración inicial")
            nips = {
                "FTPConaguaWindow": {
                    "nip_teseracto": pbkdf2_sha256.hash(cls.NIP_TESERACTO_DEFAULT, salt_size=16),
                    "nip_generico": pbkdf2_sha256.hash(cls.NIP_GENERICO_DEFAULT, salt_size=16),
                    "nip_unidad_inspeccion": None  # Se configurará posteriormente
                }
            }
            cls._guardar_archivo(config_path, nips)
        
        cls._cache['nips_ventanas'] = nips
        return nips

    @classmethod
    def guardar_nips_ventanas(cls, nips: Dict[str, Any]) -> None:
        """Guarda la configuración de NIPs para ventanas bloqueadas"""
        config_path = path_manager.get_config_path("nip_config.json")
        cls._guardar_archivo(config_path, nips)
        cls._cache.pop('nips_ventanas', None)

    @classmethod
    def obtener_nip_ventana(cls, ventana: str, tipo_nip: str) -> Optional[str]:
        """Obtiene el NIP (hasheado) de una ventana específica"""
        nips = cls.cargar_nips_ventanas()
        ventana_nips = nips.get(ventana, {})
        return ventana_nips.get(tipo_nip)

    @classmethod
    def guardar_nip_ventana(cls, ventana: str, tipo_nip: str, nip: str) -> None:
        """Guarda un NIP para una ventana específica (lo hashea automáticamente)"""
        nips = cls.cargar_nips_ventanas()
        
        if ventana not in nips:
            nips[ventana] = {}
        
        # Hashear el NIP antes de guardarlo
        hashed_nip = pbkdf2_sha256.hash(nip, salt_size=16)
        nips[ventana][tipo_nip] = hashed_nip
        
        cls.guardar_nips_ventanas(nips)
        cls._cache.pop('nips_ventanas', None)

    @classmethod
    def validar_nip_ventana(cls, ventana: str, tipo_nip: str, nip_ingresado: str) -> bool:
        """Valida si el NIP ingresado es correcto para una ventana específica"""
        nip_almacenado = cls.obtener_nip_ventana(ventana, tipo_nip)
        
        if not nip_almacenado:
            # Si no hay NIP almacenado, validar contra valores por defecto
            if tipo_nip == "nip_teseracto":
                return nip_ingresado == cls.NIP_TESERACTO_DEFAULT
            elif tipo_nip == "nip_generico":
                return nip_ingresado == cls.NIP_GENERICO_DEFAULT
            return False
        
        # Validar usando hash
        return pbkdf2_sha256.verify(nip_ingresado, nip_almacenado)

    @classmethod
    def existe_nip_unidad_inspeccion(cls, ventana: str) -> bool:
        """Verifica si ya existe un NIP de unidad de inspección configurado"""
        nips = cls.cargar_nips_ventanas()
        ventana_nips = nips.get(ventana, {})
        return ventana_nips.get("nip_unidad_inspeccion") is not None

    @classmethod
    def cambiar_nip_teseracto(cls, nuevo_nip: str) -> None:
        """Permite cambiar el NIP Teseracto (solo para administradores)"""
        cls.guardar_nip_ventana("FTPConaguaWindow", "nip_teseracto", nuevo_nip)
        logger.info("NIP Teseracto actualizado correctamente")

    @classmethod
    def cargar_config_ftp(cls) -> Dict[str, Any]:
        if 'ftp' in cls._cache:
            return cls._cache['ftp']
        
        config_path = path_manager.get_config_path("ftp_config.json")
        cfg = cls._cargar_archivo(config_path)
        
        # ✅ SOLO CARGAR - NUNCA CREAR ARCHIVOS AUTOMÁTICAMENTE
        if not cfg:
            logger.warning("Archivo ftp_config.json no encontrado, usando valores por defecto en memoria")
            return {
                "host": "", "usuario": "", "clave": "",
                "ruta_remota": "/", "port": 21, "timeout": 60, "secure": False
            }
        
        # Validación mejorada que no lanza excepciones
        config_valida = True
        campos_requeridos = ["host", "usuario", "clave"]
        
        for campo in campos_requeridos:
            if campo not in cfg or not cfg[campo]:
                config_valida = False
                cfg[campo] = ""
        
        # Establecer valores por defecto
        cfg.setdefault("ruta_remota", "/")
        cfg.setdefault("port", 21)
        cfg.setdefault("timeout", 60)
        cfg.setdefault("secure", False)
        
        if not config_valida:
            logger.warning("Configuración FTP incompleta, usando valores por defecto")
        
        cls._cache['ftp'] = cfg
        return cfg

    @classmethod
    def guardar_config_ftp(cls, config: Dict[str, Any]) -> None:
        for key in ["host", "usuario", "clave"]:
            if key not in config:
                raise ValueError(f"Falta '{key}' en la configuración FTP")
        config_path = path_manager.get_config_path("ftp_config.json")
        cls._guardar_archivo(config_path, config)
        cls._cache.pop('ftp', None)

    @classmethod
    def cargar_config_sms(cls) -> Dict[str, Any]:
        if 'sms' in cls._cache:
            return cls._cache['sms']
            
        config_path = path_manager.get_config_path("sms_config.json")
        cfg = cls._cargar_archivo(config_path)
        
        # ✅ SOLO CARGAR - NUNCA CREAR ARCHIVOS AUTOMÁTICAMENTE
        if not cfg:
            logger.warning("Archivo sms_config.json no encontrado, usando valores por defecto en memoria")
            return {"numero_destino": "", "api_key": ""}
        
        if "numero_destino" not in cfg:
            raise ValueError(f"Falta 'numero_destino' en la configuración SMS")
        cfg.setdefault("api_key", "")
        cls._cache['sms'] = cfg
        return cfg

    @classmethod
    def guardar_config_sms(cls, config: Dict[str, Any]) -> None:
        for key in ["numero_destino", "api_key"]:
            if key not in config:
                raise ValueError(f"Falta '{key}' en la configuración SMS")
        config_path = path_manager.get_config_path("sms_config.json")
        cls._guardar_archivo(config_path, config)
        cls._cache.pop('sms', None)


    @classmethod
    def guardar_config_email(cls, config: Dict[str, Any]) -> None:
        """Guarda configuración de email en email_config.json"""
        # Validar campos requeridos
        campos_requeridos = ["smtp_server", "smtp_port", "from", "to"]
        for campo in campos_requeridos:
            if campo not in config:
                raise ValueError(f"Falta '{campo}' en la configuración de email")
        
        config_path = path_manager.get_config_path("email_config.json")
        cls._guardar_archivo(config_path, config)
        cls._cache.pop('email', None)

    @classmethod
    def cargar_config_email(cls) -> Dict[str, Any]:
        """Carga configuración de email desde email_config.json"""
        if 'email' in cls._cache:
            return cls._cache['email']
        
        config_path = path_manager.get_config_path("email_config.json")
        cfg = cls._cargar_archivo(config_path)
        
        if not cfg:
            logger.warning("Archivo email_config.json no encontrado, usando valores por defecto")
            return {
                "smtp_server": "",
                "smtp_port": 587,
                "from": "",
                "to": [],
                "subject": "Reporte Tesseract UTR",
                "username": "",
                "password": ""
            }
        
        cls._cache['email'] = cfg
        return cfg

    @classmethod
    def cargar_config_login(cls) -> Dict[str, Any]:
        if 'login' in cls._cache:
            return cls._cache['login']
            
        config_path = path_manager.get_config_path("login_config.json")
        cfg = cls._cargar_archivo(config_path)
        
        # ✅ SOLO CARGAR - NUNCA CREAR ARCHIVOS AUTOMÁTICAMENTE
        if not cfg:
            logger.warning("Archivo login_config.json no encontrado, usando valores por defecto en memoria")
            return {"contraseña_maestra": "", "usuarios": {}}
        
        cls._cache['login'] = cfg
        return cfg

    @classmethod
    def guardar_config_login(cls, config: Dict[str, Any]) -> None:
        """Guarda la configuración de login soportando la nueva estructura RBAC"""
        if "contraseña_maestra" in config and not config["contraseña_maestra"].startswith("$pbkdf2-sha256$"):
            config["contraseña_maestra"] = pbkdf2_sha256.hash(config["contraseña_maestra"], salt_size=16)
            
        if "usuarios" in config:
            for user, data in config["usuarios"].items():
                # Compatibilidad con formato viejo (solo string)
                if isinstance(data, str):
                    if not data.startswith("$pbkdf2-sha256$"):
                        config["usuarios"][user] = pbkdf2_sha256.hash(data, salt_size=16)
                # Nuevo formato RBAC (diccionario con hash y rol)
                elif isinstance(data, dict) and "hash" in data:
                    if not data["hash"].startswith("$pbkdf2-sha256$"):
                        data["hash"] = pbkdf2_sha256.hash(data["hash"], salt_size=16)

        config_path = path_manager.get_config_path("login_config.json")
        cls._guardar_archivo(config_path, config)
        cls._cache.pop('login', None)

    @classmethod
    def validar_credenciales(cls, usuario: str, contraseña: str) -> bool:
        """Verifica credenciales soportando la estructura RBAC"""
        cfg = cls.cargar_config_login()
        
        # Validar contraseña maestra (permite el acceso general)
        if pbkdf2_sha256.verify(contraseña, cfg.get("contraseña_maestra", "")):
            return True
            
        user_data = cfg.get("usuarios", {}).get(usuario, "")
        
        # Extraer el hash dependiendo de si es diccionario (nuevo) o string (viejo)
        hash_user = user_data.get("hash", "") if isinstance(user_data, dict) else user_data
            
        return bool(hash_user and pbkdf2_sha256.verify(contraseña, hash_user))

    # =================================================================
    # NUEVOS MÉTODOS DE SEGURIDAD Y GESTIÓN DE USUARIOS (RBAC)
    # =================================================================

    @classmethod
    def obtener_rol_usuario(cls, usuario: str) -> str:
        """Devuelve el rol del usuario ('admin' u 'operador')"""
        cfg = cls.cargar_config_login()
        usuarios = cfg.get("usuarios", {})
        
        if usuario in usuarios:
            user_data = usuarios[usuario]
            if isinstance(user_data, dict):
                return user_data.get("rol", "operador")
            else:
                return "admin" if usuario.lower() == "admin" else "operador"
        return "operador"

    @classmethod
    def validar_password_maestra(cls, password: str) -> bool:
        """Verifica si la contraseña ingresada es estrictamente la MAESTRA"""
        cfg = cls.cargar_config_login()
        hash_maestro = cfg.get("contraseña_maestra", "")
        try:
            return bool(hash_maestro and pbkdf2_sha256.verify(password, hash_maestro))
        except Exception:
            return False

    @classmethod
    def crear_usuario(cls, usuario: str, password: str, rol: str = "operador") -> bool:
        """Crea un nuevo usuario o actualiza su contraseña y rol"""
        cfg = cls.cargar_config_login()
        if "usuarios" not in cfg:
            cfg["usuarios"] = {}
            
        hash_nuevo = pbkdf2_sha256.hash(password, salt_size=16)
        cfg["usuarios"][usuario] = {
            "hash": hash_nuevo,
            "rol": rol
        }
        cls.guardar_config_login(cfg)
        logger.info(f"Usuario '{usuario}' configurado con rol '{rol}'")
        return True

    @classmethod
    def eliminar_usuario(cls, usuario: str) -> bool:
        """Elimina un usuario (protege al 'admin' por seguridad)"""
        if usuario.lower() == "admin":
            return False
            
        cfg = cls.cargar_config_login()
        if "usuarios" in cfg and usuario in cfg["usuarios"]:
            del cfg["usuarios"][usuario]
            cls.guardar_config_login(cfg)
            logger.info(f"Usuario '{usuario}' eliminado del sistema")
            return True
        return False
        
    @classmethod
    def obtener_lista_usuarios(cls) -> List[Dict[str, str]]:
        """Retorna todos los usuarios y sus roles para la interfaz gráfica"""
        cfg = cls.cargar_config_login()
        usuarios = cfg.get("usuarios", {})
        lista = []
        
        for user, data in usuarios.items():
            rol = data.get("rol", "operador") if isinstance(data, dict) else ("admin" if user.lower() == "admin" else "operador")
            lista.append({"usuario": user, "rol": rol})
            
        return lista

    @classmethod
    def cargar_config_sensor(cls) -> Dict[str, Any]:
        if 'sensor' in cls._cache:
            return cls._cache['sensor']
            
        config_path = path_manager.get_config_path("sensor_config.json")
        cfg = cls._cargar_archivo(config_path)
        
        # ✅ SOLO CARGAR - NUNCA CREAR ARCHIVOS AUTOMÁTICAMENTE
        if not cfg:
            logger.warning("Archivo sensor_config.json no encontrado, usando valores por defecto en memoria")
            return {"sensores": [], "perfiles_predefinidos": []}
        
        cls._cache['sensor'] = cfg
        return cfg

    @classmethod
    def guardar_config_sensor(cls, config: Dict[str, Any]) -> None:
        cls._validar_config_sensor(config)
        config_path = path_manager.get_config_path("sensor_config.json")
        cls._guardar_archivo(config_path, config)
        cls._cache.pop('sensor', None)

    @classmethod
    def _validar_config_sensor(cls, config: Dict[str, Any]):
        if "sensores" not in config:
            raise ValueError("Falta sección 'sensores' en configuración de sensores")
        for sensor in config["sensores"]:
            for param in ["modelo", "puerto_serie", "baudrate", "slave_id", "parity"]:
                if param not in sensor:
                    raise ValueError(f"Falta '{param}' en configuración de sensor")
            if "registros" not in sensor:
                raise ValueError(f"Falta 'registros' en sensor {sensor.get('modelo')}")
            for reg_name, reg_config in sensor["registros"].items():
                for key in ["address", "count", "data_type"]:
                    if key not in reg_config:
                        raise ValueError(f"Registro '{reg_name}' falta '{key}'")
                if reg_config["data_type"] == "bitmask" and "bit_map" not in reg_config:
                    raise ValueError(f"Registro bitmap '{reg_name}' falta 'bit_map'")

    @classmethod
    def obtener_perfiles_sensores(cls) -> List[Dict[str, Any]]:
        return cls.cargar_config_sensor().get("sensores", [])

    @classmethod
    def obtener_perfil_por_modelo(cls, modelo: str) -> Optional[Dict[str, Any]]:
        for sensor in cls.obtener_perfiles_sensores():
            if sensor.get("modelo") == modelo:
                return sensor
        return None

    @classmethod
    def obtener_perfiles_predefinidos(cls) -> List[Dict[str, Any]]:
        return cls.cargar_config_sensor().get("perfiles_predefinidos", [])

    @classmethod
    def guardar_perfil_sensor(cls, perfil: Dict[str, Any], es_nuevo: bool = False):
        for reg_name, reg_config in perfil.get("registros", {}).items():
            if "address" not in reg_config:
                raise ValueError(f"Registro '{reg_name}' falta 'address'")
        
            try:
                addr = int(reg_config["address"])
                if not (0 <= addr <= 65535):
                    raise ValueError(f"Dirección inválida en registro '{reg_name}': {addr}")
            except (TypeError, ValueError):
                raise ValueError(f"Dirección inválida en registro '{reg_name}': {reg_config['address']}")

        cfg = cls.cargar_config_sensor()
        cls._cache.pop('sensor', None)


    # AGREGAR EN ConfigManager.py - Método para obtener medidores por tipo
    @classmethod
    def obtener_medidores_por_tipo(cls, tipo_medidor: str) -> List[Dict[str, Any]]:
        """Obtiene todos los sensores de un tipo específico"""
        sensores = cls.obtener_perfiles_sensores()
        return [sensor for sensor in sensores if sensor.get("tipo_medidor") == tipo_medidor]

    @classmethod 
    def obtener_tipos_medidor_disponibles(cls) -> List[str]:
        """Obtiene lista de tipos de medidores disponibles"""
        sensores = cls.obtener_perfiles_sensores()
        tipos = set()
        for sensor in sensores:
            if "tipo_medidor" in sensor:
                tipos.add(sensor["tipo_medidor"])
        return list(tipos)
    
    @classmethod
    def obtener_perfiles_predefinidos_por_tipo(cls, tipo_medidor: str) -> List[Dict[str, Any]]:
        """Obtiene perfiles predefinidos filtrados por tipo de medidor"""
        perfiles = cls.obtener_perfiles_predefinidos()
        return [perfil for perfil in perfiles if perfil.get("tipo_medidor") == tipo_medidor]


    @classmethod
    def obtener_parametro(cls, clave: str) -> Any:
        return cls.cargar_config_general().get(clave)

    @classmethod
    def obtener_config_alertas(cls) -> Dict[str, Any]:
        return cls.cargar_config_general().get("alertas", {})

    @classmethod
    def guardar_config_alertas(cls, alertas: Dict[str, Any]) -> None:
        cfg = cls.cargar_config_general()
        cfg["alertas"] = alertas
        config_path = path_manager.get_config_path("config.json")
        cls._guardar_archivo(config_path, cfg)
        cls._cache.pop('general', None)

    @staticmethod
    def _cargar_archivo(ruta: str) -> Dict[str, Any]:
        if not os.path.exists(ruta):
            return {}
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _guardar_archivo(ruta: str, datos: Dict[str, Any]):
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)

    @staticmethod
    def _validar_rfc(rfc: str):
        if not re.match(r"^[A-ZÑ&]{3,4}\d{6}[A-V0-9]{3}$", rfc):
            raise ValueError("RFC inválido")

    @staticmethod
    def _validar_coordenadas(lat: Any, long: Any):
        try:
            lat_f, long_f = float(lat), float(long)
            if not (-90 <= lat_f <= 90 and -180 <= long_f <= 180):
                raise ValueError("Coordenadas fuera de rango")
        except Exception as e:
            raise ValueError(f"Coordenadas inválidas: {e}")