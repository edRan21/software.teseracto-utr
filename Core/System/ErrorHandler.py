# TESERACTO-UTR/Core/System/ErrorHandler.py

import logging
from logging.handlers import RotatingFileHandler
import time
from datetime import datetime
from typing import List, Dict
from Core.System.PathManager import path_manager

class ErrorHandler:
    """
    Cerebro de Diagnóstico de TESSERACTO-UTR.
    Fusiona la auto-resolución de estados (FSM) con la persistencia visual (Niveles) y memoria RAM.
    """
    KER_ERRORS = {
        # ========== ERRORES DEL SISTEMA (SOFTWARE/RED/HARDWARE LOCAL) ==========
        "001": "Falta conexión a internet",
        "002": "Fallo en conexión FTP", 
        "005": "Error en puerto COM local",
        "007": "Error de comunicación con medidor (Cable/Timeout)",
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
        
        # ========== ERRORES DE LA APLICACIÓN (LÓGICA) ==========
        "301": "Error de configuración",
        "302": "Error de unidad de medida",
        "303": "Error de conversión de unidades",
        "304": "Error de formato de reporte",
        "305": "Error de archivo de reporte",
    }

    def __init__(self, notificadores: List[object] = None):
        self.notificadores = notificadores or []
        self.logger = self._configurar_logger_fisico()
        
        # MAPAS DE ALARMAS ACTIVAS (Para Auto-resolución y Reportes)
        self._ker_sistema_activos: Dict[str, float] = {}
        self._ker_medidor_activos: Dict[str, float] = {}
        
        # MEMORIA RAM HISTÓRICA (Para interfaz visual y resúmenes)
        self.ultimo_error_sistema = "000"
        self.ultimo_error_medidor = "000"
        self.historial_errores_sistema = []
        self.historial_errores_medidor = []
        self.errores_comunicacion = {
            'port_a': {'crc': 0, 'parity': 0, 'framing': 0, 'overrun': 0, 'break': 0},
            'port_b': {'crc': 0, 'parity': 0, 'framing': 0, 'overrun': 0, 'break': 0}
        }
        
        # Filtro Anti-Spam Inteligente
        self._spam_filter = {} 
        self.SPAM_WINDOW = 60.0 

    def _configurar_logger_fisico(self):
        """Mantiene el registro en disco duro compatible con ErrorConsoleWindow."""
        logger = logging.getLogger("Telemetria_KER")
        logger.setLevel(logging.DEBUG) 
        
        if logger.handlers:
            return logger
            
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        log_path = path_manager.get_db_path("errores.log")
        file_handler = RotatingFileHandler(
            log_path, mode='a', maxBytes=5*1024*1024, backupCount=2, encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        return logger

    # =========================================================================
    # LÓGICA DE SISTEMA (Internet, FTP, Puertos COM)
    # =========================================================================
    def activar_ker_sistema(self, codigo: str, contexto: str = ""):
        """Enciende una alarma de sistema y la inyecta en la RAM."""
        if codigo not in self.KER_ERRORS:
            codigo = "010"
            
        self._ker_sistema_activos[codigo] = time.time()
        self.ultimo_error_sistema = codigo
        
        self._agregar_historial(codigo, contexto, "sistema")
        self._escribir_log_fisico(logging.ERROR, codigo, contexto)

    def resolver_ker_sistema(self, codigo: str):
        """Apaga una alarma de sistema con nivel INFO (Color Azul)."""
        if codigo in self._ker_sistema_activos:
            del self._ker_sistema_activos[codigo]
            
            if not self._ker_sistema_activos:
                self.ultimo_error_sistema = "000"
                
            self._escribir_log_fisico(logging.INFO, codigo, "Resuelto automáticamente", resuelto=True)

    def reset_ker_normal(self):
        """Reinicio forzado invocado desde MainWindow."""
        self.ultimo_error_sistema = "000"
        self._ker_sistema_activos.clear()

    # =========================================================================
    # LÓGICA DE MEDIDORES (Modbus, Badger, ISOMAG)
    # =========================================================================
    def activar_ker_medidor(self, codigo: str, contexto: str = ""):
        if codigo not in self.KER_ERRORS:
            codigo = "112" if "Badger" in contexto else "128"
            
        self._ker_medidor_activos[codigo] = time.time()
        self.ultimo_error_medidor = codigo
        
        self._agregar_historial(codigo, contexto, "medidor")
        self._escribir_log_fisico(logging.ERROR, codigo, contexto)

    def resolver_todos_ker_medidor(self):
        if self._ker_medidor_activos:
            self._ker_medidor_activos.clear()
            self.ultimo_error_medidor = "000"
            self._escribir_log_fisico(logging.INFO, "000", "Lecturas del medidor normalizadas", resuelto=True)

    def procesar_estado_bruto_medidor(self, meter_status: int, tipo_medidor: str):
        if meter_status == 0:
            self.resolver_todos_ker_medidor()
            return
            
        errores_detectados = []
        
        if tipo_medidor == "Badger M2000":
            if meter_status & 0x01: errores_detectados.append("101")
            if meter_status & 0x02: errores_detectados.append("102")
            if meter_status & 0x04: errores_detectados.append("103")
            if meter_status & 0x08: errores_detectados.append("104")
            if meter_status & 0x10: errores_detectados.append("104")
            if meter_status & 0x40: errores_detectados.append("105")
            if meter_status & 0x80: errores_detectados.append("106")
            if meter_status & 0x100: errores_detectados.append("107")
            if meter_status & 0x200: errores_detectados.append("108")
            if meter_status & 0x400: errores_detectados.append("108")
            if meter_status & 0x800: errores_detectados.append("109")
            if meter_status & 0x1000: errores_detectados.append("110")
            if meter_status & 0x2000: errores_detectados.append("111")
            
        elif tipo_medidor == "ISOMAG":
            flags2 = meter_status & 0xFF
            if flags2 & 0x01: errores_detectados.append("120")
            if flags2 & 0x02: errores_detectados.append("121")
            if flags2 & 0x04: errores_detectados.append("122")
            if flags2 & 0x08: errores_detectados.append("123")
            if flags2 & 0x10: errores_detectados.append("124")
            if flags2 & 0x20: errores_detectados.append("125")
            if flags2 & 0x40: errores_detectados.append("126")
            if flags2 & 0x80: errores_detectados.append("127")

        if errores_detectados:
            for cod in errores_detectados:
                self.activar_ker_medidor(cod, f"Detectado en mapa de memoria: {meter_status}")
        else:
            self.activar_ker_medidor("112" if tipo_medidor == "Badger M2000" else "128", "Estado anormal no catalogado")

    # =========================================================================
    # WRAPPERS UNIVERSALES Y LECTURA PARA REPORTES
    # =========================================================================
    def log_error(self, codigo: str, mensaje: str, es_error_sistema: bool = True):
        """Enruta excepciones genéricas hacia el motor KER correspondiente."""
        if es_error_sistema or codigo.startswith("0") or codigo.startswith("3"):
            self.activar_ker_sistema(codigo, mensaje)
        else:
            self.activar_ker_medidor(codigo, mensaje)

    def log_evento(self, contexto: str, codigo_personalizado: str = "100"):
        """Eventos operacionales impresos como INFO para la UI visual."""
        mensaje = f"KER-{codigo_personalizado} [EVENTO] - {contexto}"
        self.logger.info(mensaje)

    def obtener_ker_para_reporte(self) -> str:
        todos_los_activos = {**self._ker_sistema_activos, **self._ker_medidor_activos}
        if not todos_los_activos:
            return "000"
        ultimo_ker = max(todos_los_activos.items(), key=lambda x: x[1])[0]
        return ultimo_ker

    # =========================================================================
    # MECANISMOS DE DISCO DURO Y FILTRO ANTI-SPAM
    # =========================================================================
    def _escribir_log_fisico(self, nivel: int, codigo: str, contexto: str, resuelto: bool = False):
        estado = "RESUELTO" if resuelto else "ACTIVO"
        descripcion = self.KER_ERRORS.get(codigo, "Desconocido")
        mensaje_base = f"KER-{codigo} [{estado}] - {descripcion} | {contexto}"
        
        now = time.time()
        
        # Filtro Anti-Spam solo aplica a errores (Evitamos filtrar mensajes INFO útiles)
        if nivel in [logging.ERROR, logging.WARNING]:
            if mensaje_base in self._spam_filter:
                spam_data = self._spam_filter[mensaje_base]
                if (now - spam_data['last_time']) < self.SPAM_WINDOW:
                    spam_data['count'] += 1
                    spam_data['last_time'] = now
                    return
                else:
                    if spam_data['count'] > 0:
                        resumen = f"{mensaje_base} (Repetido {spam_data['count']} veces ocultas en los últimos {self.SPAM_WINDOW}s)"
                        self.logger.log(nivel, resumen)
                    self._spam_filter[mensaje_base] = {'last_time': now, 'count': 0}
            else:
                self._spam_filter[mensaje_base] = {'last_time': now, 'count': 0}
                
        self.logger.log(nivel, mensaje_base)
        
        if nivel == logging.ERROR:
            for canal in self.notificadores:
                if hasattr(canal, 'enviar_alerta'):
                    try:
                        canal.enviar_alerta(mensaje_base)
                    except Exception: pass

    # =========================================================================
    # MANEJO DE HISTORIAL EN MEMORIA RAM (Restaurado)
    # =========================================================================
    def _agregar_historial(self, codigo: str, contexto: str, tipo: str):
        registro = {
            'codigo': codigo,
            'mensaje': f"KER-{codigo} | {contexto}",
            'timestamp': time.time(),
            'fecha_hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'tipo': tipo
        }
        if tipo == "sistema":
            self.historial_errores_sistema.append(registro)
            if len(self.historial_errores_sistema) > 100: self.historial_errores_sistema.pop(0)
        else:
            self.historial_errores_medidor.append(registro)
            if len(self.historial_errores_medidor) > 100: self.historial_errores_medidor.pop(0)

    def obtener_historial_ker(self, limite: int = 10, tipo: str = "sistema") -> List[Dict]:
        if tipo == "sistema": historial = self.historial_errores_sistema
        elif tipo == "medidor": historial = self.historial_errores_medidor
        else: historial = self.historial_errores_sistema + self.historial_errores_medidor
        return historial[-limite:] if historial else []

    def limpiar_historial_ker(self, tipo: str = "all"):
        if tipo == "sistema" or tipo == "all": self.historial_errores_sistema = []
        if tipo == "medidor" or tipo == "all": self.historial_errores_medidor = []

    def actualizar_errores_comunicacion(self, diagnostics: Dict[str, Dict[str, int]]):
        if not diagnostics: return
        for port in ['port_a', 'port_b']:
            if port in diagnostics:
                for error_type, count in diagnostics[port].items():
                    mapped_type = error_type.replace('_errors', '').replace('_detects', '')
                    if mapped_type in self.errores_comunicacion[port]:
                        self.errores_comunicacion[port][mapped_type] = count
                        if count > 0:
                            ker_code = self._get_communication_ker_code(port, mapped_type)
                            self.activar_ker_sistema(ker_code, f"{mapped_type} errors in {port}: {count}")

    def _get_communication_ker_code(self, port: str, error_type: str) -> str:
        mapping = {
            ('port_a', 'crc'): '201', ('port_a', 'parity'): '202', ('port_a', 'framing'): '203',
            ('port_a', 'overrun'): '204', ('port_a', 'break'): '205', ('port_b', 'crc'): '206',
            ('port_b', 'parity'): '207', ('port_b', 'framing'): '208', ('port_b', 'overrun'): '209',
            ('port_b', 'break'): '210',
        }
        return mapping.get((port, error_type), '211')

    def obtener_resumen_errores(self) -> Dict:
        return {
            'ultimo_error_sistema': self.ultimo_error_sistema,
            'ultimo_error_medidor': self.ultimo_error_medidor,
            'total_errores_sistema': len(self.historial_errores_sistema),
            'total_errores_medidor': len(self.historial_errores_medidor),
            'errores_comunicacion': self.errores_comunicacion
        }