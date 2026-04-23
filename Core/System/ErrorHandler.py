# TESERACTO-UTR/Core/System/ErrorHandler.py

import logging
from logging.handlers import RotatingFileHandler  # NUEVO: Para autolimpieza del archivo
import time
from datetime import datetime
from typing import List, Dict, Tuple
from Core.System.PathManager import path_manager

class ErrorHandler:
    KER_ERRORS = {
        # ========== ERRORES DEL SISTEMA (SOFTWARE) ==========
        "001": "Falta conexión a internet",
        "002": "Fallo en conexión FTP", 
        "005": "Error en puerto COM",
        "007": "Error de comunicación con medidor",
        "010": "Fallo general del sistema",
        "011": "Error en envío de SMS",
        
        # ========== ERRORES DEL MEDIDOR BADGER M2000 ==========
        "101": "Badger - Error de detector",
        "102": "Badger - Tubería vacía",
        "103": "Badger - Rango completo",
        "104": "Badger - Desbordamiento de totalizador",
        "105": "Badger - Error de sincronización de pulso",
        "106": "Badger - Error de interrupción ADC",
        "107": "Badger - Error de rango ADC",
        "108": "Badger - Error de watchdog reset",
        "109": "Badger - Error fatal del sistema",
        "110": "Badger - Error de token",
        "111": "Badger - Error de checksum OIMLR49",
        "112": "Badger - Error desconocido del medidor",
        
        # ========== ERRORES DEL MEDIDOR ISOMAG ==========
        "120": "ISOMAG - Tubería vacía",
        "121": "ISOMAG - Error de excitación de bobinas",
        "122": "ISOMAG - Error de señal de entrada",
        "123": "ISOMAG - Error de amplificador",
        "124": "ISOMAG - Error de rango ADC",
        "125": "ISOMAG - Desbordamiento de pulso canal 1",
        "126": "ISOMAG - Desbordamiento de pulso canal 2", 
        "127": "ISOMAG - Desbordamiento de flujo",
        "128": "ISOMAG - Error desconocido del medidor",
        
        # ========== ERRORES DE LA APLICACIÓN (SISTEMA) ==========
        "301": "Error de configuración",
        "302": "Error de unidad de medida",
        "303": "Error de conversión de unidades",
        "304": "Error de formato de reporte",
        "305": "Error de archivo de reporte",
        
        # NUEVOS CÓDIGOS FTP MEJORADOS (SISTEMA)
        "FTP-DNS": "Error de resolución DNS en servidor FTP",
        "FTP-PORT": "Puerto FTP inaccesible", 
        "FTP-CONNECT": "Error de conectividad al servidor FTP",
        "FTP-CONNECTION": "Conexión FTP fallida",
        "FTP-UNEXPECTED": "Error inesperado en conexión FTP",
        "FTP-DIRECTORY": "Error creando directorios FTP",
        "FTP-FORMAT": "Error validando formato de archivo",
        "FTP-FORMAT-INVALID": "Formato de archivo inválido",
        "FTP-PERMISSION": "Error de permisos FTP",
        "FTP-UPLOAD": "Error subiendo archivo FTP",
        "FTP-VERIFY": "Error verificando conexión FTP",
        "FTP-TEST": "Error en prueba de conexión FTP",
        
        # CÓDIGOS DE CONFIGURACIÓN (SISTEMA)
        "CONFIG-LOAD": "Error cargando configuración",
        "CONFIG-SAVE": "Error guardando configuración", 
        "CONFIG-SYNC": "Error sincronizando configuración",
        
        # CÓDIGOS EMAIL (SISTEMA)
        "EMAIL-TEST": "Error en prueba de email",
    }

    def __init__(self, notificadores: List[object] = None):
        self.notificadores = notificadores or []
        self.logger = self._configurar_logger()
        
        # APORTACIÓN: Filtro Anti-Spam Inteligente
        self._spam_filter = {}  # Formato: {mensaje: {'last_time': float, 'count': int}}
        self.SPAM_WINDOW = 60.0 # Segundos de espera antes de repetir un error en el log visual
        
        # CÓDIGOS KER SEPARADOS: sistema vs medidor
        self.ultimo_error_sistema = "000"
        self.ultimo_error_medidor = "000"
        
        self.historial_errores_sistema = []
        self.historial_errores_medidor = []
        self.errores_comunicacion = {
            'port_a': {'crc': 0, 'parity': 0, 'framing': 0, 'overrun': 0, 'break': 0},
            'port_b': {'crc': 0, 'parity': 0, 'framing': 0, 'overrun': 0, 'break': 0}
        }

    def _configurar_logger(self):
        logger = logging.getLogger("TelemetríaApp")
        logger.setLevel(logging.DEBUG)
        
        if logger.handlers:
            return logger
            
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # APORTACIÓN: RotatingFileHandler limita el archivo a 5MB y guarda hasta 2 respaldos viejos
        log_path = path_manager.get_db_path("errores.log")
        file_handler = RotatingFileHandler(
            log_path, 
            mode='a', 
            maxBytes=5*1024*1024, # 5 MB
            backupCount=2,        # Mantiene errores.log.1 y errores.log.2
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        return logger

    def log_error(self, codigo: str, contexto: str = "", es_error_sistema: bool = True):
        if codigo not in self.KER_ERRORS:
            if es_error_sistema:
                codigo = "010"
            else:
                if "ISOMAG" in contexto or any(str(x) in codigo for x in range(120, 129)):
                    codigo = "128"
                else:
                    codigo = "112"
            
        mensaje_base = f"KER-{codigo}: {self.KER_ERRORS.get(codigo, 'Error desconocido')} | {contexto}"
        now = time.time()
        
        # Lógica de historiales internos
        if es_error_sistema:
            self.ultimo_error_sistema = codigo
            self.historial_errores_sistema.append({
                'codigo': codigo,
                'mensaje': mensaje_base,
                'timestamp': now,
                'fecha_hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'tipo': 'sistema'
            })
            if len(self.historial_errores_sistema) > 100:
                self.historial_errores_sistema.pop(0)
        else:
            self.ultimo_error_medidor = codigo
            self.historial_errores_medidor.append({
                'codigo': codigo,
                'mensaje': mensaje_base,
                'timestamp': now,
                'fecha_hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'tipo': 'medidor'
            })
            if len(self.historial_errores_medidor) > 100:
                self.historial_errores_medidor.pop(0)
        
        # ==========================================
        # APORTACIÓN: SUPRESIÓN DE REPETICIONES (Anti-Spam)
        # ==========================================
        if mensaje_base in self._spam_filter:
            spam_data = self._spam_filter[mensaje_base]
            # Si el error ocurrió hace menos del tiempo de gracia (SPAM_WINDOW)
            if (now - spam_data['last_time']) < self.SPAM_WINDOW:
                spam_data['count'] += 1
                spam_data['last_time'] = now
                return  # Omitimos el registro en el archivo de texto y consola visual
            else:
                # Si ya pasó el tiempo, verificamos si hubo repeticiones ocultas
                if spam_data['count'] > 0:
                    resumen = f"{mensaje_base} (Repetido {spam_data['count']} veces ocultas en los últimos {self.SPAM_WINDOW}s)"
                    self.logger.error(resumen)
                
                # Reiniciamos el contador para este error
                self._spam_filter[mensaje_base] = {'last_time': now, 'count': 0}
        else:
            # Es un error nuevo, lo registramos en el diccionario
            self._spam_filter[mensaje_base] = {'last_time': now, 'count': 0}
            
        # Log error normal
        self.logger.error(mensaje_base)
        
        # Notificadores externos
        if es_error_sistema:
            for canal in self.notificadores:
                if hasattr(canal, 'enviar_alerta'):
                    try:
                        canal.enviar_alerta(mensaje_base)
                    except Exception as e:
                        self.logger.error(f"Error enviando alerta: {str(e)}")

    # (El resto de métodos de ErrorHandler se mantienen exactamente igual)
    def reset_ker_normal(self):
        self.ultimo_error_sistema = "000"
    
    def log_meter_error(self, meter_status: int, tipo_medidor: str = "Badger M2000"):
        if meter_status == 0:
            return
        if tipo_medidor == "Badger M2000":
            errors = []
            if meter_status & 0x01: errors.append("101")
            if meter_status & 0x02: errors.append("102")
            if meter_status & 0x04: errors.append("103")
            if meter_status & 0x08: errors.append("104")
            if meter_status & 0x10: errors.append("104")
            if meter_status & 0x40: errors.append("105")
            if meter_status & 0x80: errors.append("106")
            if meter_status & 0x100: errors.append("107")
            if meter_status & 0x200: errors.append("108")
            if meter_status & 0x400: errors.append("108")
            if meter_status & 0x800: errors.append("109")
            if meter_status & 0x1000: errors.append("110")
            if meter_status & 0x2000: errors.append("111")
            
            if errors:
                for code in errors:
                    self.log_error(code, f"Badger reporta error: {meter_status} (0x{meter_status:04X})", es_error_sistema=False)
            else:
                self.log_error("112", f"Badger reporta estado desconocido: {meter_status} (0x{meter_status:04X})", es_error_sistema=False)
        
        elif tipo_medidor == "ISOMAG":
            flags2 = meter_status & 0xFF
            flags1 = (meter_status >> 8) & 0xFF
            errors = []
            if flags2 & 0x01: errors.append("120")
            if flags2 & 0x02: errors.append("121")
            if flags2 & 0x04: errors.append("122")
            if flags2 & 0x08: errors.append("123")
            if flags2 & 0x10: errors.append("124")
            if flags2 & 0x20: errors.append("125")
            if flags2 & 0x40: errors.append("126")
            if flags2 & 0x80: errors.append("127")
            
            if errors:
                for code in errors:
                    self.log_error(code, f"ISOMAG reporta error: flags1=0x{flags1:02X}, flags2=0x{flags2:02X}", es_error_sistema=False)
            else:
                if flags2 != 0:
                    self.log_error("128", f"ISOMAG reporta error no mapeado: flags1=0x{flags1:02X}, flags2=0x{flags2:02X}", es_error_sistema=False)
                elif flags1 != 0:
                    self.logger.info(f"ISOMAG estado operativo: flags1=0x{flags1:02X}, flags2=0x{flags2:02X}")
    
    def log_conexion(self, estado: bool, puerto: str):
        mensaje = f"Conexión {'exitosa' if estado else 'fallida'} en {puerto}"
        self.logger.info(mensaje)
        if not estado:
            self.log_error("005", f"Reconexión en progreso en {puerto}", es_error_sistema=True)

    def log_evento(self, contexto: str, codigo_personalizado: str = "100"):
        mensaje = f"KER-{codigo_personalizado}: {contexto}"
        self.logger.info(mensaje)

    def get_ker_code(self) -> str: return self.ultimo_error_sistema
    def get_meter_error_code(self) -> str: return self.ultimo_error_medidor

    def get_ker_history(self, limit: int = 10, tipo: str = "sistema") -> List[Dict]:
        if tipo == "sistema": historial = self.historial_errores_sistema
        elif tipo == "medidor": historial = self.historial_errores_medidor
        else: historial = self.historial_errores_sistema + self.historial_errores_medidor
        return historial[-limit:] if historial else []

    def clear_ker_history(self, tipo: str = "all"):
        if tipo == "sistema" or tipo == "all": self.historial_errores_sistema = []
        if tipo == "medidor" or tipo == "all": self.historial_errores_medidor = []

    def update_communication_errors(self, diagnostics: Dict[str, Dict[str, int]]):
        if not diagnostics: return
        for port in ['port_a', 'port_b']:
            if port in diagnostics:
                for error_type, count in diagnostics[port].items():
                    mapped_type = error_type.replace('_errors', '').replace('_detects', '')
                    if mapped_type in self.errores_comunicacion[port]:
                        self.errores_comunicacion[port][mapped_type] = count
                        if count > 0:
                            ker_code = self._get_communication_ker_code(port, mapped_type)
                            self.log_error(ker_code, f"{mapped_type} errors in {port}: {count}", es_error_sistema=True)

    def _get_communication_ker_code(self, port: str, error_type: str) -> str:
        mapping = {
            ('port_a', 'crc'): '201', ('port_a', 'parity'): '202', ('port_a', 'framing'): '203',
            ('port_a', 'overrun'): '204', ('port_a', 'break'): '205', ('port_b', 'crc'): '206',
            ('port_b', 'parity'): '207', ('port_b', 'framing'): '208', ('port_b', 'overrun'): '209',
            ('port_b', 'break'): '210',
        }
        return mapping.get((port, error_type), '211')

    def get_communication_summary(self) -> str:
        summary = []
        for port, errors in self.errores_comunicacion.items():
            for error_type, count in errors.items():
                if count > 0: summary.append(f"{port.upper()}_{error_type.upper()}:{count}")
        return ";".join(summary) if summary else "Sin errores de comunicación"

    def reset_communication_errors(self):
        for port in self.errores_comunicacion:
            for error_type in self.errores_comunicacion[port]:
                self.errores_comunicacion[port][error_type] = 0

    def add_notificador(self, notificador):
        if notificador not in self.notificadores: self.notificadores.append(notificador)

    def remove_notificador(self, notificador):
        if notificador in self.notificadores: self.notificadores.remove(notificador)

    def get_error_summary(self) -> Dict:
        return {
            'ultimo_error_sistema': self.ultimo_error_sistema,
            'ultimo_error_medidor': self.ultimo_error_medidor,
            'total_errores_sistema': len(self.historial_errores_sistema),
            'total_errores_medidor': len(self.historial_errores_medidor),
            'errores_comunicacion': self.errores_comunicacion
        }