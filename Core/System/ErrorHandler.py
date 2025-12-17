# TESERACTO-UTR/Core/System/ErrorHandler.py - VERSIÓN CORREGIDA PARA ISOMAG

import logging
import time
from datetime import datetime
from typing import List, Dict, Tuple
from Core.System.PathManager import path_manager

class ErrorHandler:
    KER_ERRORS = {
        # ========== ERRORES DEL SISTEMA (SOFTWARE) ==========
        # Estos SÍ generan código KER en reportes
        "001": "Falta conexión a internet",
        "002": "Fallo en conexión FTP", 
        "005": "Error en puerto COM",
        "007": "Error de comunicación con medidor",
        "010": "Fallo general del sistema",
        "011": "Error en envío de SMS",
        
        # ========== ERRORES DEL MEDIDOR BADGER M2000 ==========
        # Estos NO generan código KER en reportes (solo en log)
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
        # Estos NO generan código KER en reportes (solo en log)
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
        self._last_msg = None
        self._last_time = 0.0
        self._repeat_count = 0
        
        # CÓDIGOS KER SEPARADOS: sistema vs medidor
        self.ultimo_error_sistema = "000"  # Solo errores del sistema (se incluyen en reporte)
        self.ultimo_error_medidor = "000"  # Solo errores del medidor (NO se incluyen en reporte)
        
        self.historial_errores_sistema = []  # Historial de errores del sistema
        self.historial_errores_medidor = []  # Historial de errores del medidor
        self.errores_comunicacion = {
            'port_a': {'crc': 0, 'parity': 0, 'framing': 0, 'overrun': 0, 'break': 0},
            'port_b': {'crc': 0, 'parity': 0, 'framing': 0, 'overrun': 0, 'break': 0}
        }

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

        # Handler para archivo (recoge todo)
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

    def log_error(self, codigo: str, contexto: str = "", es_error_sistema: bool = True):
        """
        Método principal para registrar errores.
        
        Args:
            codigo: Código de error (ej: "005", "101", etc.)
            contexto: Descripción detallada del error
            es_error_sistema: True si es error del sistema, False si es del medidor
                              Los errores del sistema generan KER en reportes
                              Los errores del medidor solo aparecen en el log
        """
        # Validar código KER
        if codigo not in self.KER_ERRORS:
            # Si es error del sistema y código desconocido → "010"
            # Si es error del medidor y código desconocido → "112" (Badger) o "127" (ISOMAG)
            if es_error_sistema:
                codigo = "010"  # Fallo general del sistema
            else:
                # Determinar si es error Badger o ISOMAG basado en el contexto
                if "ISOMAG" in contexto or any(str(x) in codigo for x in range(120, 129)):
                    codigo = "128"  # Error desconocido ISOMAG
                else:
                    codigo = "112"  # Error desconocido Badger
            
        mensaje = f"KER-{codigo}: {self.KER_ERRORS.get(codigo, 'Error desconocido')} | {contexto}"
        now = time.time()
        
        # ACTUALIZAR EL CONTADOR CORRECTO SEGÚN EL TIPO DE ERROR
        if es_error_sistema:
            # ERROR DEL SISTEMA: actualiza código para reporte
            self.ultimo_error_sistema = codigo
            self.historial_errores_sistema.append({
                'codigo': codigo,
                'mensaje': mensaje,
                'timestamp': now,
                'fecha_hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'tipo': 'sistema'
            })
            
            # Mantener solo los últimos 100 errores del sistema
            if len(self.historial_errores_sistema) > 100:
                self.historial_errores_sistema.pop(0)
        else:
            # ERROR DEL MEDIDOR: solo registra en log, no actualiza código para reporte
            self.ultimo_error_medidor = codigo
            self.historial_errores_medidor.append({
                'codigo': codigo,
                'mensaje': mensaje,
                'timestamp': now,
                'fecha_hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'tipo': 'medidor'
            })
            
            # Mantener solo los últimos 100 errores del medidor
            if len(self.historial_errores_medidor) > 100:
                self.historial_errores_medidor.pop(0)
        
        # SUPRESIÓN DE REPETICIONES EN CONSOLA
        if mensaje == self._last_msg and (now - self._last_time) < 1.0:
            self._repeat_count += 1
            return
            
        # Emitir resumen de repeticiones acumuladas
        if self._repeat_count > 0:
            resumen = f"{self._last_msg}  (repetido {self._repeat_count} veces)"
            self.logger.error(resumen)
            self._repeat_count = 0
            
        # Log error normal (ambos tipos van al archivo errores.log)
        self.logger.error(mensaje)
        self._last_msg = mensaje
        self._last_time = now
        
        # Notificadores externos (solo para errores del sistema por defecto)
        if es_error_sistema:
            for canal in self.notificadores:
                if hasattr(canal, 'enviar_alerta'):
                    try:
                        canal.enviar_alerta(mensaje)
                    except Exception as e:
                        self.logger.error(f"Error enviando alerta: {str(e)}")
    
    def reset_ker_normal(self):
        """Restablecer el código KER del SISTEMA a '000' cuando funciona normalmente"""
        self.ultimo_error_sistema = "000"
    
    def log_meter_error(self, meter_status: int, tipo_medidor: str = "Badger M2000"):
        """
        Registra errores del medidor basado en el estado.
        
        Args:
            meter_status: Estado del medidor (valor crudo del registro)
            tipo_medidor: Tipo de medidor ("Badger M2000" o "ISOMAG")
        """
        if meter_status == 0:
            return
        
        # DIFERENCIAR ENTRE TIPOS DE MEDIDOR
        if tipo_medidor == "Badger M2000":
            # Lógica original para Badger M2000
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
            if meter_status & 0x1000:  # Bit 12: Token error en medidor
                errors.append("110")
            if meter_status & 0x2000:  # Bit 13: OIMLR49 checksum error en medidor
                errors.append("111")
            
            if errors:
                for code in errors:
                    # ERRORES DEL MEDIDOR BADGER: es_error_sistema=False (no generan KER en reporte)
                    self.log_error(code, f"Badger reporta error: {meter_status} (0x{meter_status:04X})", es_error_sistema=False)
            else:
                # ERRORES NO MAPEADOS DEL BADGER → Código 112
                # Si hay bits set pero no mapeados
                self.log_error("112", f"Badger reporta estado desconocido: {meter_status} (0x{meter_status:04X})", es_error_sistema=False)
        
        elif tipo_medidor == "ISOMAG":
            # NUEVA LÓGICA PARA ISOMAG - NO USAR TOKEN ERROR (110)
            # El registro 0020 del ISOMAG tiene 2 bytes: [MSB: flags1, LSB: flags2]
            flags2 = meter_status & 0xFF  # Byte bajo (Process Flags 2)
            flags1 = (meter_status >> 8) & 0xFF  # Byte alto (Process Flags 1)
            
            errors = []
            
            # Decodificar Process Flags 2 (LSB) - Errores del medidor ISOMAG
            if flags2 & 0x01:  # Bit 0: pipe_empty
                errors.append("120")
            if flags2 & 0x02:  # Bit 1: coils_excitation_error
                errors.append("121")
            if flags2 & 0x04:  # Bit 2: input_signal_error
                errors.append("122")
            if flags2 & 0x08:  # Bit 3: amplifier_error
                errors.append("123")
            if flags2 & 0x10:  # Bit 4: adc_range_error
                errors.append("124")
            if flags2 & 0x20:  # Bit 5: pulse_ch1_overflow
                errors.append("125")
            if flags2 & 0x40:  # Bit 6: pulse_ch2_overflow
                errors.append("126")
            if flags2 & 0x80:  # Bit 7: flow_rate_overflow
                errors.append("127")
            
            if errors:
                for code in errors:
                    # ERRORES DEL MEDIDOR ISOMAG: es_error_sistema=False (no generan KER en reporte)
                    self.log_error(code, f"ISOMAG reporta error: flags1=0x{flags1:02X}, flags2=0x{flags2:02X}", es_error_sistema=False)
            else:
                # ⚠️ CORRECCIÓN: Manejar bits no mapeados en flags2 como errores desconocidos
                # Si hay bits set en flags1 (estado operativo, no errores)
                # Verificar si hay bits activos en flags2 que no están mapeados (aunque según manual, todos están mapeados)
                # Pero también podría haber bits futuros o errores de transmisión
                if flags2 != 0:
                    # Hay bits activos en flags2 pero no están mapeados → error desconocido
                    self.log_error("128", f"ISOMAG reporta error no mapeado: flags1=0x{flags1:02X}, flags2=0x{flags2:02X}", es_error_sistema=False)
                elif flags1 != 0:
                    # Solo flags1 activo (estado operativo, no errores) → log informativo
                    self.logger.info(f"ISOMAG estado operativo: flags1=0x{flags1:02X}, flags2=0x{flags2:02X}")
    
    def log_conexion(self, estado: bool, puerto: str):
        """Log de conexión - siempre es error del sistema si falla"""
        mensaje = f"Conexión {'exitosa' if estado else 'fallida'} en {puerto}"
        self.logger.info(mensaje)
        if not estado:
            # Error de conexión es del SISTEMA (genera KER en reporte)
            self.log_error("005", f"Reconexión en progreso en {puerto}", es_error_sistema=True)

    def log_evento(self, contexto: str, codigo_personalizado: str = "100"):
        """Log de eventos informativos - no son errores, no generan KER"""
        mensaje = f"KER-{codigo_personalizado}: {contexto}"
        self.logger.info(mensaje)

    def get_ker_code(self) -> str:
        """Devuelve SOLO el último código KER del SISTEMA (para incluir en reportes)"""
        return self.ultimo_error_sistema

    def get_meter_error_code(self) -> str:
        """Devuelve el último código de error del MEDIDOR (solo para diagnóstico)"""
        return self.ultimo_error_medidor

    def get_ker_history(self, limit: int = 10, tipo: str = "sistema") -> List[Dict]:
        """Devuelve el historial de errores del tipo especificado"""
        if tipo == "sistema":
            historial = self.historial_errores_sistema
        elif tipo == "medidor":
            historial = self.historial_errores_medidor
        else:
            historial = self.historial_errores_sistema + self.historial_errores_medidor
            
        return historial[-limit:] if historial else []

    def clear_ker_history(self, tipo: str = "all"):
        """Limpia el historial de errores especificado"""
        if tipo == "sistema" or tipo == "all":
            self.historial_errores_sistema = []
        if tipo == "medidor" or tipo == "all":
            self.historial_errores_medidor = []

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
                        
                        # Generar alerta si hay errores nuevos (son errores del SISTEMA)
                        if count > 0:
                            ker_code = self._get_communication_ker_code(port, mapped_type)
                            self.log_error(ker_code, f"{mapped_type} errors in {port}: {count}", es_error_sistema=True)

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

    def get_error_summary(self) -> Dict:
        """Devuelve resumen de todos los errores para diagnóstico"""
        return {
            'ultimo_error_sistema': self.ultimo_error_sistema,
            'ultimo_error_medidor': self.ultimo_error_medidor,
            'total_errores_sistema': len(self.historial_errores_sistema),
            'total_errores_medidor': len(self.historial_errores_medidor),
            'errores_comunicacion': self.errores_comunicacion
        }