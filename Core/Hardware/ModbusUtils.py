# TESERACTO-UTR/Core/Hardware/ModbusUtils.py

import serial.tools.list_ports
import re
import logging
import time
from typing import List, Optional

# APORTACIÓN 5: Importar ErrorHandler para uso opcional
from Core.System.ErrorHandler import ErrorHandler

def obtener_puertos_com(only_modbus: bool = False, modbus_patterns: Optional[List[str]] = None, timeout: float = 2.0, error_handler: Optional[ErrorHandler] = None) -> List[str]:
    """
    Retorna lista de puertos COM disponibles de forma robusta y con timeout.
    """
    start_time = time.time()
    ports = []
    
    try:
        available_ports = serial.tools.list_ports.comports()
        
        if time.time() - start_time > timeout:
            msg = "Timeout en enumeración de puertos COM"
            logging.warning(msg)
            # Notificar a la interfaz si se pasó el manejador
            if error_handler:
                error_handler.log_error("005", msg, es_error_sistema=True)
            return ["COM1", "COM2", "COM3"]
            
        if only_modbus:
            patterns = modbus_patterns or [
                r'USB.*Serial', r'COM\d+', r'FTDI', r'Prolific', r'CH340', r'CP210', 
                r'Arduino', r'Modbus', r'RS-485', r'RS485', r'USB-SERIAL'
            ]
            ports = [
                port.device for port in available_ports
                if any(re.search(pattern, str(port.description), re.IGNORECASE) for pattern in patterns)
                or any(re.search(pattern, str(port.hwid), re.IGNORECASE) for pattern in patterns)
            ]
        else:
            ports = [port.device for port in available_ports]
            
        if not ports:
            logging.info("No se detectaron puertos COM físicos, usando lista básica")
            return ["COM1", "COM2", "COM3", "COM4"]
            
        return ports
        
    except Exception as e:
        msg = "Error crítico al listar puertos COM"
        logging.error(f"{msg}: {e}")
        if error_handler:
            error_handler.log_error("005", msg, es_error_sistema=True)
        return ["COM1", "COM2", "COM3", "COM4"]

def verificar_puerto_com(port_name: str, timeout: float = 1.0) -> bool:
    import serial
    try:
        with serial.Serial(port_name, timeout=timeout) as ser:
            return ser.is_open
    except (serial.SerialException, OSError, ValueError) as e:
        logging.debug(f"Puerto {port_name} no disponible: {e}")
        return False
    except Exception as e:
        logging.error(f"Error inesperado verificando puerto {port_name}: {e}")
        return False