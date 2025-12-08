# TESERACTO-UTR/Core/Hardware/ModbusRTU_Manager.py

import logging
import time
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, Union, Optional
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
from Core.System.ErrorHandler import ErrorHandler

RegisterValue = Union[float, int, Dict[str, bool]]

class IMedidorAgua(ABC):
    """Interfaz para todos los tipos de medidores de agua"""
    @abstractmethod
    def leer_registros(self) -> Dict[str, RegisterValue]:
        pass

    @abstractmethod
    def conectar(self) -> bool:
        pass

    @abstractmethod
    def desconectar(self):
        pass

    @abstractmethod
    def obtener_unidad_flujo(self) -> str:
        pass

class ModbusDecoderStrategy(ABC):
    """Estrategia para decodificación de registros"""
    @abstractmethod
    def decodificar(self, registers: list, reg_config: Dict[str, Any], perfil: Dict[str, Any]) -> RegisterValue:
        pass

class Float32Decoder(ModbusDecoderStrategy):
    def decodificar(self, registers, reg_config, perfil) -> float:
        # OBTENER CONFIGURACIÓN DEL PERFIL
        endianness = perfil.get("endianness", "big")
        word_order = perfil.get("word_order", "big")
        
        # MAPEAR A CONSTANTES PyModbus
        byteorder = Endian.BIG if endianness == "big" else Endian.LITTLE
        wordorder = Endian.BIG if word_order == "big" else Endian.LITTLE
        
        dec = BinaryPayloadDecoder.fromRegisters(
            registers,
            byteorder=byteorder,
            wordorder=wordorder
        )
        valor = dec.decode_32bit_float()
        
        # Solo escalar si NO es unidad de usuario
        if "unidad_medidor" in reg_config and reg_config["unidad_medidor"] == "user_units":
            return valor
        return valor * reg_config.get("escala", 1.0)

class Int16Decoder(ModbusDecoderStrategy):
    def decodificar(self, registers, reg_config, perfil) -> int:
        if reg_config.get("no_escalar", False):
            return registers[0]
        return registers[0] * reg_config.get("escala", 1)

class UInt32Decoder(ModbusDecoderStrategy):
    def decodificar(self, registers, reg_config, perfil) -> int:
        # OBTENER CONFIGURACIÓN DEL PERFIL
        endianness = perfil.get("endianness", "big")
        word_order = perfil.get("word_order", "big")
        
        byteorder = Endian.BIG if endianness == "big" else Endian.LITTLE
        wordorder = Endian.BIG if word_order == "big" else Endian.LITTLE
        
        dec = BinaryPayloadDecoder.fromRegisters(
            registers,
            byteorder=byteorder,
            wordorder=wordorder
        )
        return dec.decode_32bit_uint() * reg_config.get("escala", 1)

class BitmaskDecoder(ModbusDecoderStrategy):
    def decodificar(self, registers, reg_config, perfil) -> Dict[str, bool]:
        value = registers[0]
        return {desc: bool(value & (1 << int(bit))) for bit, desc in reg_config.get("bit_map", {}).items()}

class ErrorDecoder(ModbusDecoderStrategy):
    """Decodificador para registros de error"""
    def decodificar(self, registers, reg_config, perfil) -> Dict[str, bool]:
        error_code = registers[0]
        return {
            "sensor_fault": bool(error_code & 0x01),
            "over_range": bool(error_code & 0x02),
            "empty_pipe": bool(error_code & 0x04),
        }

class IsomagFlagsDecoder(ModbusDecoderStrategy):
    def decodificar(self, registers, reg_config, perfil) -> Dict[str, bool]:
        """Decodifica los flags de proceso del registro 0020 para ISOMAG"""
        if not registers:
            return {}
        
        value = registers[0]
        flags1 = (value >> 8) & 0xFF  # MSB: Process flags 1
        flags2 = value & 0xFF         # LSB: Process flags 2
        
        return {
            # Flags 1 (MSB)
            "flow_rate_alarm_min": bool(flags1 & (1 << 7)),
            "flow_rate_alarm_max": bool(flags1 & (1 << 6)),
            "flow_direction_negative": bool(flags1 & (1 << 5)),  # Bit 5: 1 = negative
            "flow_below_cutoff": bool(flags1 & (1 << 4)),
            "measure_range_2": bool(flags1 & (1 << 3)),
            "flow_rate_reset": bool(flags1 & (1 << 2)),
            "volume_counters_locked": bool(flags1 & (1 << 1)),
            
            # Flags 2 (LSB) 
            "flow_rate_overflow": bool(flags2 & (1 << 7)),
            "pulse_ch2_overflow": bool(flags2 & (1 << 6)),
            "pulse_ch1_overflow": bool(flags2 & (1 << 5)),
            "adc_range_error": bool(flags2 & (1 << 4)),
            "amplifier_error": bool(flags2 & (1 << 3)),
            "input_signal_error": bool(flags2 & (1 << 2)),
            "coils_excitation_error": bool(flags2 & (1 << 1)),
            "pipe_empty": bool(flags2 & (1 << 0))
        }

class DecoderFactory:
    _decoders = {
        "float32": Float32Decoder(),
        "int16": Int16Decoder(),
        "uint32": UInt32Decoder(),
        "bitmask": BitmaskDecoder(),
        "error": ErrorDecoder(),
        "isomag_flags": IsomagFlagsDecoder()  # NUEVO DECODIFICADOR PARA ISOMAG
    }
    
    @classmethod
    def register_decoder(cls, data_type: str, decoder: ModbusDecoderStrategy):
        cls._decoders[data_type] = decoder
        
    @classmethod
    def get_decoder(cls, data_type: str) -> Optional[ModbusDecoderStrategy]:
        return cls._decoders.get(data_type)

class MedidorAguaBase(IMedidorAgua):
    """Implementación base para medidores de agua"""
    DECODER_FACTORY = DecoderFactory
    
    def __init__(self, perfil_sensor: Dict[str, Any], error_handler: ErrorHandler):
        self.perfil = perfil_sensor
        self.error_handler = error_handler
        self.logger = logging.getLogger(f"{__name__}.{type(self).__name__}")
        self.client = None
        self._connection_lock = threading.RLock()
        self._unidad_flujo_cache = "m³/h"
        self._ultima_lectura_unidad = 0
        self._is_connected = False
        self._last_communication = 0
        self._consecutive_errors = 0
        self._max_consecutive_errors = 3
        
        # NUEVO: Configuración adaptativa de timeout
        self._adaptive_timeout = self.perfil.get("timeout", 5.0)
        self._init_client()

    def _init_client(self):
        """Inicializa cliente con timeout adaptativo"""
        with self._connection_lock:
            if self.client is None or not self._is_connected:
                self.client = ModbusSerialClient(
                    port=self.perfil["puerto_serie"],
                    baudrate=self.perfil["baudrate"],
                    parity=self._map_parity(self.perfil.get("parity", "N")),
                    stopbits=self.perfil.get("stopbits", 1),
                    bytesize=self.perfil.get("bytesize", 8),
                    timeout=self._adaptive_timeout  # Timeout adaptativo
                )

    def _map_parity(self, parity_char: str) -> str:
        mapping = {'N': 'N', 'E': 'E', 'O': 'O'}
        return mapping.get(parity_char.upper(), 'N')
    
    def conectar(self) -> bool:
        """Conexión robusta con manejo de errores mejorado"""
        with self._connection_lock:
            if self._is_connected and self.client.connected:
                return True
                
            try:
                # INTENTO DE CONEXIÓN CON TIMEOUT
                success = self.client.connect()
                
                if success:
                    self._is_connected = True
                    self._consecutive_errors = 0
                    self._adaptive_timeout = max(1.0, self._adaptive_timeout * 0.8)  # Reducir timeout si funciona
                    self.logger.info(f"Conexión exitosa. Timeout adaptativo: {self._adaptive_timeout:.2f}s")
                else:
                    self._handle_connection_error("Fallo en conexión Modbus")
                    
                return success
                
            except Exception as e:
                self._handle_connection_error(e)
                return False

    def _handle_connection_error(self, error=None):
        """Maneja errores de conexión de forma adaptativa"""
        self._consecutive_errors += 1
        self._is_connected = False
        
        # AUMENTAR TIMEOUT ADAPTATIVAMENTE
        if self._consecutive_errors > 2:
            self._adaptive_timeout = min(10.0, self._adaptive_timeout * 1.5)  # Máximo 10 segundos
            
        error_msg = f"Error conexión (intento {self._consecutive_errors}): {error}"
        if self._consecutive_errors >= self._max_consecutive_errors:
            self.error_handler.log_error("005", f"CONEXIÓN FALLIDA: {error_msg}")
            self.logger.error(f"Timeout adaptativo aumentado a: {self._adaptive_timeout:.2f}s")
        else:
            self.logger.warning(error_msg)

    # leer_registros_seguro() - IMPLEMENTACIÓN COMPLETA
    def leer_registros_seguro(self, timeout: float = None) -> Dict[str, RegisterValue]:
        """
        Versión segura de leer_registros que permite timeout específico
        sin afectar la configuración global del medidor.
        
        Args:
            timeout (float): Timeout específico para esta lectura (opcional)
            
        Returns:
            Dict[str, RegisterValue]: Resultados de la lectura
        """
        if timeout is None:
            # Usar el método normal si no se especifica timeout
            return self.leer_registros()
            
        # Guardar configuración original
        original_timeout = self._adaptive_timeout
        original_client = self.client
        
        try:
            # Configurar timeout temporal
            self._adaptive_timeout = timeout
            
            # Recrear cliente con nuevo timeout
            self._init_client()
            
            # Realizar lectura con timeout reducido
            return self.leer_registros()
            
        except Exception as e:
            self.logger.error(f"Error en lectura segura: {e}")
            return {}
            
        finally:
            # RESTAURAR CONFIGURACIÓN ORIGINAL
            self._adaptive_timeout = original_timeout
            self.client = original_client

    def leer_registros(self) -> Dict[str, RegisterValue]:
        """Lee registros con protección mejorada"""
        # VERIFICAR SI DEBERÍAMOS INTENTAR LECTURA
        if self._consecutive_errors >= self._max_consecutive_errors:
            self.logger.warning("Demasiados errores consecutivos, omitiendo lectura")
            return {}
            
        with self._connection_lock:
            start_time = time.time()
            
            try:
                if not self.client.connected and not self.conectar():
                    self._consecutive_errors += 1
                    return {}
                    
                resultados = {}
                registros_a_leer = list(self.perfil["registros"].keys())
                
                # LIMITAR CANTIDAD DE REGISTROS POR CICLO
                if len(registros_a_leer) > 10:
                    self.logger.warning(f"Demasiados registros ({len(registros_a_leer)}), limitando a 10")
                    registros_a_leer = registros_a_leer[:10]
                
                for reg_name in registros_a_leer:
                    # VERIFICAR TIMEOUT GLOBAL
                    if time.time() - start_time > self._adaptive_timeout * 2:
                        self.logger.warning("Timeout global excedido, cancelando lecturas restantes")
                        break
                        
                    try:
                        resultados[reg_name] = self._leer_registro(reg_name)
                    except ModbusException as e:
                        self.error_handler.log_error("021", f"Error registro {reg_name}: {e}")
                        resultados[reg_name] = None
                        self._consecutive_errors += 1
                    except Exception as e:
                        self.error_handler.log_error("022", f"Error decodificación {reg_name}: {e}")
                        resultados[reg_name] = None
                        self._consecutive_errors += 1

                # POST-PROCESAMIENTO Y RESET DE CONTADOR SI EXITOSO
                if resultados and any(v is not None for v in resultados.values()):
                    self._consecutive_errors = 0
                    logging.info(f"✅ Lectura exitosa con {len(resultados)} registros")
                else:
                    logging.warning("⚠️ Lectura devolvió resultados vacíos o todos None")
                    
                    if self.perfil.get("tipo_medidor") == "ISOMAG":
                        resultados = self._postprocesar_isomag(resultados)
                
                return resultados
                
            except Exception as e:
                self._handle_connection_error(e)
                return {}

    def _postprocesar_isomag(self, resultados):
        """Post-procesa los resultados para ISOMAG y los mapea al formato estándar"""
        # Mapear flags de proceso a campos estándar
        if "flags_proceso" in resultados and isinstance(resultados["flags_proceso"], dict):
            flags = resultados["flags_proceso"]
            
            # Mapear dirección de flujo (Bit 5 de flags1)
            if flags.get("flow_direction_negative"):
                resultados["direccion_flujo"] = 2  # Flujo negativo
            else:
                resultados["direccion_flujo"] = 1  # Flujo positivo
            
            # Mapear errores del sensor desde flags2
            errores_sensor = {}
            if flags.get("pipe_empty"):
                errores_sensor["empty_pipe"] = True
            if flags.get("flow_rate_overflow"):
                errores_sensor["over_range"] = True
            if flags.get("coils_excitation_error") or flags.get("input_signal_error"):
                errores_sensor["sensor_fault"] = True
            
            resultados["errores_sensor"] = errores_sensor if errores_sensor else {
                "sensor_fault": False,
                "over_range": False, 
                "empty_pipe": False
            }
        
        return resultados

    def _leer_registro(self, reg_name: str) -> RegisterValue:
        """Lee un registro individual con reintentos"""
        reg_config = self.perfil["registros"].get(reg_name)
        if not reg_config:
            raise ValueError(f"Registro {reg_name} no configurado")
        
        funcion = reg_config.get("funcion", self.perfil.get("funcion_default", 4))
        
        # Flags sin escalar para dirección de flujo en Badger
        if reg_name == "direccion_flujo" and self.perfil.get("tipo_medidor") == "Badger M2000":
            reg_config["no_escalar"] = True
            
        decoder = self.DECODER_FACTORY.get_decoder(reg_config["data_type"])
        
        if not decoder:
            raise ValueError(f"Tipo dato no soportado: {reg_config['data_type']}")

        for intento in range(3):
            try:
                # USAR FUNCIÓN ESPECÍFICA SEGÚN CONFIGURACIÓN
                if funcion == 3:
                    response = self.client.read_holding_registers(
                        address=reg_config["address"], 
                        count=reg_config["count"],
                        slave=self.perfil["slave_id"]
                    )
                elif funcion == 4:
                    response = self.client.read_input_registers(
                        address=reg_config["address"], 
                        count=reg_config["count"],
                        slave=self.perfil["slave_id"]
                    )
                else:
                    raise ModbusException(f"Función {funcion} no soportada")

                if response.isError():
                    raise ModbusException(f"Error en respuesta: {response}")
                    
                return decoder.decodificar(response.registers, reg_config, self.perfil)
                
            except ModbusException as e:
                if intento == 2:
                    raise
                time.sleep(0.2)
                self.conectar()

    def leer_estado_medidor(self) -> Dict[str, Any]:
        """
        Lee el estado del medidor (registro crítico 0x0106 para Badger)
        Devuelve diccionario con estado
        """
        with self._connection_lock:
            if not self.client.connected and not self.conectar():
                return {}

            try:
                # Para ISOMAG, leer registro de flags de proceso (0020) como estado
                if self.perfil.get("tipo_medidor") == "ISOMAG":
                    response = self.client.read_input_registers(
                        address=20,  # Registro 0020 para flags de proceso ISOMAG
                        count=1,
                        slave=self.perfil["slave_id"]
                    )
                else:
                    # Para Badger M2000, leer registro de estado estándar
                    response = self.client.read_input_registers(
                        address=0x0106,  # Meter Status para Badger
                        count=1,
                        slave=self.perfil["slave_id"]
                    )

                if response.isError():
                    return {}

                return {
                    'meter_status': response.registers[0],
                    'timestamp': time.time()
                }
                
            except Exception as e:
                self.error_handler.log_error("007", f"Error leyendo estado medidor: {str(e)}")
                return {}

    def obtener_unidad_flujo(self) -> str:
        """Obtiene la unidad de flujo con caché para mejor rendimiento"""
        ahora = time.time()
        if ahora - self._ultima_lectura_unidad > 60:  # Actualizar cada minuto
            try:
                registro = self._leer_registro("unidad_flujo")
                unidades = {
                    0: "L/s", 1: "L/min", 2: "L/h", 3: "m³/s", 4: "m³/min",
                    5: "m³/h", 6: "ft³/s", 7: "ft³/min", 8: "ft³/h",
                    9: "gal/s", 10: "GPM", 11: "gal/h", 12: "MGD"
                }
                self._unidad_flujo_cache = unidades.get(registro, "m³/h")
                self._ultima_lectura_unidad = ahora
            except Exception as e:
                self.error_handler.log_error("UNIDAD_FLUJO", f"Error leyendo unidad: {e}")
        return self._unidad_flujo_cache

    def desconectar(self):
        with self._connection_lock:
            if self.client and self.client.connected:
                try:
                    self.client.close()
                    self._is_connected = False
                    self.logger.info("Conexión Modbus cerrada correctamente")
                except Exception as e:
                    self.error_handler.log_error("015", f"Error desconexión: {e}")