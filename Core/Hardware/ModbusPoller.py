# TESERACTO-UTR/Core/Hardware/ModbusPoller.py

import threading
import time
import logging
from typing import Dict, Any, Optional

class ModbusPoller:
    """
    Gobernador de Hardware (Productor Único).
    Mantiene un ciclo de lectura constante con el medidor a través del puerto serie
    y almacena el estado en una memoria compartida segura (Thread-Safe) para evitar
    el bloqueo de la interfaz gráfica y otros hilos del sistema operativo Windows.
    """
    
    def __init__(self, medidor, error_handler, frecuencia_lectura: float = 2.0):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.medidor = medidor
        self.error_handler = error_handler
        
        # Frecuencia de escaneo en segundos
        self._frecuencia_lectura = frecuencia_lectura
        
        # Control del ciclo de vida
        self._en_ejecucion = False
        self._hilo_trabajo: Optional[threading.Thread] = None
        
        # Memoria compartida y candado de exclusión mutua
        self._candado_datos = threading.Lock()
        self._ultimo_paquete: Dict[str, Any] = self._generar_paquete_vacio()
        self._ultimos_datos_validos: Dict[str, Any] = {} # Memoria LKGV

    def iniciar(self) -> None:
        """Inicia el hilo en segundo plano para la lectura del hardware."""
        if self._en_ejecucion:
            self.logger.warning("El ModbusPoller ya se encuentra en ejecución.")
            return
            
        self._en_ejecucion = True
        self._hilo_trabajo = threading.Thread(
            target=self._ciclo_lectura,
            name="ModbusPoller-Thread",
            daemon=True
        )
        self._hilo_trabajo.start()
        self.logger.info("Motor ModbusPoller iniciado exitosamente en segundo plano.")

    def detener(self) -> None:
        """Detiene el hilo de lectura y libera los recursos físicos."""
        self.logger.info("Iniciando secuencia de detención del ModbusPoller...")
        self._en_ejecucion = False
        
        if self._hilo_trabajo and self._hilo_trabajo.is_alive():
            self._hilo_trabajo.join(timeout=5.0)
            
        if self.medidor:
            try:
                self.medidor.desconectar()
            except Exception as e:
                self.logger.error(f"Error al desconectar el medidor físico: {e}")
                
        self.logger.info("ModbusPoller detenido y puerto serie liberado.")

    def _ciclo_lectura(self) -> None:
        """Ciclo infinito aislado del sistema principal."""
        while self._en_ejecucion:
            tiempo_inicio = time.time()
            
            try:
                if not self.medidor.client.connected:
                    self.medidor.conectar()
                
                datos_crudos = self.medidor.leer_registros()
                
                if datos_crudos and any(v is not None for v in datos_crudos.values()):
                    # Auto-limpieza del Cerebro (KER)
                    self.error_handler.resolver_ker_sistema("007") 
                    self.error_handler.resolver_ker_sistema("010") 
                    
                    # Actualizar la memoria de rescate (LKGV)
                    self._ultimos_datos_validos = datos_crudos
                    
                    self._actualizar_paquete(conectado=True, datos=datos_crudos, error="000")
                else:
                    self.error_handler.activar_ker_sistema("007", "Sin respuesta útil del hardware")
                    # Inyectar los datos congelados (LKGV) en lugar de un diccionario vacío
                    self._actualizar_paquete(conectado=False, datos=self._ultimos_datos_validos, error="007")
                    
            except Exception as e:
                self.error_handler.activar_ker_sistema("010", f"Fallo crítico en hardware: {str(e)}")
                # ✅ Inyectar los datos congelados (LKGV) durante una excepción crítica
                self._actualizar_paquete(conectado=False, datos=self._ultimos_datos_validos, error="010")
            
            # Control de cadencia para no saturar el procesador
            tiempo_transcurrido = time.time() - tiempo_inicio
            tiempo_espera = max(0.1, self._frecuencia_lectura - tiempo_transcurrido)
            time.sleep(tiempo_espera)

    def _actualizar_paquete(self, conectado: bool, datos: dict, error: str) -> None:
        """Actualiza la tabla de memoria de forma atómica."""
        nuevo_estado = {
            "timestamp": time.time(),
            "estado_conexion": conectado,
            "codigo_error": error,
            "datos_crudos": datos
        }
        
        with self._candado_datos:
            self._ultimo_paquete = nuevo_estado

    def obtener_ultimo_paquete(self) -> Dict[str, Any]:
        """
        Método público para que los consumidores extraigan los datos
        de manera asíncrona sin interactuar con el puerto serie.
        """
        with self._candado_datos:
            return self._ultimo_paquete.copy()

    def _generar_paquete_vacio(self) -> Dict[str, Any]:
        """Estructura base para inicialización segura."""
        return {
            "timestamp": 0.0,
            "estado_conexion": False,
            "codigo_error": "000",
            "datos_crudos": {}
        }