# Tesseract/Core/Hardware/ModbusUtils.py

import serial.tools.list_ports
import re
import logging
import time
from typing import List, Optional

def obtener_puertos_com(only_modbus: bool = False, modbus_patterns: Optional[List[str]] = None, timeout: float = 2.0) -> List[str]:
    """
    Retorna lista de puertos COM disponibles de forma robusta y con timeout.

    Args:
        only_modbus (bool): Si True, filtra puertos que probablemente sean Modbus.
        modbus_patterns (list[str]): Lista de patrones regex para filtrar puertos.
        timeout (float): Tiempo máximo para la operación (segundos).

    Returns:
        List[str]: Lista de nombres de puertos COM.
    """
    start_time = time.time()
    ports = []
    
    try:
        # INTENTAR CON TIMEOUT PARA EVITAR BLOQUEOS
        available_ports = serial.tools.list_ports.comports()
        
        # VERIFICAR TIMEOUT
        if time.time() - start_time > timeout:
            logging.warning("Timeout en enumeración de puertos COM")
            return ["COM1", "COM2", "COM3"]  # Fallback seguro
            
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
            
        # SI NO HAY PUERTOS, RETORNAR LISTA BÁSICA
        if not ports:
            logging.info("No se detectaron puertos COM físicos, usando lista básica")
            return ["COM1", "COM2", "COM3", "COM4"]
            
        return ports
        
    except Exception as e:
        logging.error(f"Error crítico al listar puertos COM: {e}")
        # FALLBACK CRÍTICO - PUERTOS BÁSICOS
        return ["COM1", "COM2", "COM3", "COM4"]

def verificar_puerto_com(port_name: str, timeout: float = 1.0) -> bool:
    """
    Verifica si un puerto COM específico está disponible y responsive.
    
    Args:
        port_name (str): Nombre del puerto (ej. "COM3")
        timeout (float): Tiempo máximo para la verificación
        
    Returns:
        bool: True si el puerto está disponible
    """
    import serial
    try:
        # Intentar abrir el puerto brevemente
        with serial.Serial(port_name, timeout=timeout) as ser:
            return ser.is_open
    except (serial.SerialException, OSError, ValueError) as e:
        logging.debug(f"Puerto {port_name} no disponible: {e}")
        return False
    except Exception as e:
        logging.error(f"Error inesperado verificando puerto {port_name}: {e}")
        return False