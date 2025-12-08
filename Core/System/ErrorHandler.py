# TESERACTO-UTR/Core/System/ErrorHandler.py

import logging
import time
from datetime import datetime
from typing import List, Dict, Tuple
from Core.System.PathManager import path_manager

class ErrorHandler:
    KER_ERRORS = {
        # Errores originales del sistema
        "001": "Falta conexión a internet",
        "002": "Fallo en conexión FTP", 
        "005": "Error en puerto COM",
        "007": "Error de comunicación con medidor",
        "010": "Fallo general del sistema",
        "011": "Error en envío de SMS",
        
        # Nuevos códigos para errores del medidor M2000
        "101": "Error de detector en medidor",
        "102": "Error de tubería vacía en medidor",
        "103": "Error de rango completo en medidor",
        "104": "Error de desbordamiento de totalizador",
        "105": "Error de sincronización de pulso",
        "106": "Error de interrupción ADC",
        "107": "Error de rango ADC",
        "108": "Error de watchdog reset",
        "109": "Error fatal del sistema",
        "110": "Error de token",
        "111": "Error de checksum OIMLR49",
        
        
        # Errores de la aplicación
        "301": "Error de configuración",
        "302": "Error de unidad de medida",
        "303": "Error de conversión de unidades",
        "304": "Error de formato de reporte",
        "305": "Error de archivo de reporte",
        # NUEVOS CÓDIGOS FTP MEJORADOS
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
        
        # CÓDIGOS DE CONFIGURACIÓN
        "CONFIG-LOAD": "Error cargando configuración",
        "CONFIG-SAVE": "Error guardando configuración", 
        "CONFIG-SYNC": "Error sincronizando configuración",
        
        # CÓDIGOS EMAIL
        "EMAIL-TEST": "Error en prueba de email",
    }

    def __init__(self, notificadores: List[object] = None):
        self.notificadores = notificadores or []
        self.logger = self._configurar_logger()
        self._last_msg = None
        self._last_time = 0.0
        self._repeat_count = 0
        self.ultimo_error = "000"  # Código KER por defecto (sin error)
        self.historial_errores = []  # Para mantener un historial de errores
        self.errores_comunicacion = {
            'port_a': {'crc': 0, 'parity': 0, 'framing': 0, 'overrun': 0, 'break': 0},
            'port_b': {'crc': 0, 'parity': 0, 'framing': 0, 'overrun': 0, 'break': 0}
        }

    # Modificar en _configurar_logger para utiliza rutas absolutas para empaquetamiento
    def _configurar_logger(self):
        logger = logging.getLogger("TelemetríaApp")
        logger.setLevel(logging.DEBUG)
        
        # Evitar múltiples handlers
        if logger.handlers:
            return logger
            
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Handler para archivo (recoge todo) - MODIFICADO
        log_path = path_manager.get_db_path("errores.log")
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Handler para consola (solo warnings y errores)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        return logger

    def log_error(self, codigo: str, contexto: str = ""):
        # Validar código KER
        if codigo not in self.KER_ERRORS:
            codigo = "010"  # Fallo general del sistema para códigos desconocidos
            
        mensaje = f"KER-{codigo}: {self.KER_ERRORS.get(codigo, 'Error desconocido')} | {contexto}"
        now = time.time()
        
        # Actualizar último error
        self.ultimo_error = codigo
        self.historial_errores.append({
            'codigo': codigo,
            'mensaje': mensaje,
            'timestamp': now,
            'fecha_hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # Mantener solo los últimos 100 errores
        if len(self.historial_errores) > 100:
            self.historial_errores.pop(0)
        
        # Supresión de repeticiones en consola
        if mensaje == self._last_msg and (now - self._last_time) < 1.0:
            self._repeat_count += 1
            return
            
        # Emitir resumen de repeticiones acumuladas
        if self._repeat_count > 0:
            resumen = f"{self._last_msg}  (repetido {self._repeat_count} veces)"
            self.logger.error(resumen)
            self._repeat_count = 0
            
        # Log error normal
        self.logger.error(mensaje)
        self._last_msg = mensaje
        self._last_time = now
        
        # Notificadores externos
        for canal in self.notificadores:
            if hasattr(canal, 'enviar_alerta'):
                try:
                    canal.enviar_alerta(mensaje)
                except Exception as e:
                    self.logger.error(f"Error enviando alerta: {str(e)}")
    
    # ESTE MÉTODO NUEVO LIMPIA KER CUANDO TODO ESTÁ BIEN
    def reset_ker_normal(self):
        """Restablecer el código KER a '000' cuando el sistema funciona normalmente"""
        self.ultimo_error = "000"
    
    def log_meter_error(self, meter_status: int):
        """Registra errores del medidor basado en el estado"""
        if meter_status == 0:
            return
        # Mapear bits a códigos KER
        errors = []
        if meter_status & 0x01:  # Bit 0: Detector error
            errors.append("101")
        if meter_status & 0x02:  # Bit 1: Empty pipe error
            errors.append("102")
        if meter_status & 0x04:  # Bit 2: Full scale flow error
            errors.append("103")
        if meter_status & 0x08:  # Bit 3: Totalizer rollover error
            errors.append("104")
        if meter_status & 0x10:  # Bit 4: Totalizer rollover warning
            errors.append("104")  # Mismo código por simplicidad
        if meter_status & 0x40:  # Bit 6: Dig pulse sync status
            errors.append("105")
        if meter_status & 0x80:  # Bit 7: ADC int error
            errors.append("106")
        if meter_status & 0x100:  # Bit 8: ADC range error
            errors.append("107")
        if meter_status & 0x200:  # Bit 9: WDT reset error
            errors.append("108")
        if meter_status & 0x400:  # Bit 10: WDT reset
            errors.append("108")  # Mismo código
        if meter_status & 0x800:  # Bit 11: Fatal error
            errors.append("109")
        if meter_status & 0x1000:  # Bit 12: Token error
            errors.append("110")
        if meter_status & 0x2000:  # Bit 13: OIMLR49 checksum error
            errors.append("111")
        if errors:
            for code in errors:
                self.log_error(code, f"Medidor reporta error: {meter_status}")
        else:
            # Si hay bits set pero no mapeados, registrar error general
            self.log_error("110", f"Medidor reporta estado desconocido: {meter_status}")
    
    def log_conexion(self, estado: bool, puerto: str):
        mensaje = f"Conexión {'exitosa' if estado else 'fallida'} en {puerto}"
        self.logger.info(mensaje)
        if not estado:
            self.log_error("005", f"Reconexión en progreso en {puerto}")

    def log_evento(self, contexto: str, codigo_personalizado: str = "100"):
        mensaje = f"KER-{codigo_personalizado}: {contexto}"
        self.logger.info(mensaje)

    def get_ker_code(self) -> str:
        """Devuelve el último código KER registrado"""
        return self.ultimo_error

    def get_ker_history(self, limit: int = 10) -> List[Dict]:
        """Devuelve el historial de errores KER"""
        return self.historial_errores[-limit:] if self.historial_errores else []

    def clear_ker_history(self):
        """Limpia el historial de errores"""
        self.historial_errores = []

    def update_communication_errors(self, diagnostics: Dict[str, Dict[str, int]]):
        """
        Actualiza los contadores de errores de comunicación desde los diagnósticos del medidor
        """
        if not diagnostics:
            return
            
        for port in ['port_a', 'port_b']:
            if port in diagnostics:
                for error_type, count in diagnostics[port].items():
                    # Mapear nombres de error
                    mapped_type = error_type.replace('_errors', '').replace('_detects', '')
                    if mapped_type in self.errores_comunicacion[port]:
                        self.errores_comunicacion[port][mapped_type] = count
                        
                        # Generar alerta si hay errores nuevos
                        if count > 0:
                            ker_code = self._get_communication_ker_code(port, mapped_type)
                            self.log_error(ker_code, f"{mapped_type} errors in {port}: {count}")

    def _get_communication_ker_code(self, port: str, error_type: str) -> str:
        """Mapea tipo de error de comunicación a código KER"""
        mapping = {
            ('port_a', 'crc'): '201',
            ('port_a', 'parity'): '202',
            ('port_a', 'framing'): '203',
            ('port_a', 'overrun'): '204',
            ('port_a', 'break'): '205',
            ('port_b', 'crc'): '206',
            ('port_b', 'parity'): '207',
            ('port_b', 'framing'): '208',
            ('port_b', 'overrun'): '209',
            ('port_b', 'break'): '210',
        }
        return mapping.get((port, error_type), '211')  # Default: múltiples errores

    def get_communication_summary(self) -> str:
        """Devuelve resumen de errores de comunicación para reportes"""
        summary = []
        for port, errors in self.errores_comunicacion.items():
            for error_type, count in errors.items():
                if count > 0:
                    summary.append(f"{port.upper()}_{error_type.upper()}:{count}")
        return ";".join(summary) if summary else "Sin errores de comunicación"

    def reset_communication_errors(self):
        """Reinicia los contadores de errores de comunicación"""
        for port in self.errores_comunicacion:
            for error_type in self.errores_comunicacion[port]:
                self.errores_comunicacion[port][error_type] = 0

    def add_notificador(self, notificador):
        """Añade un nuevo notificador a la lista"""
        if notificador not in self.notificadores:
            self.notificadores.append(notificador)

    def remove_notificador(self, notificador):
        """Remueve un notificador de la lista"""
        if notificador in self.notificadores:
            self.notificadores.remove(notificador)