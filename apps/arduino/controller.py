# -*- encoding: utf-8 -*-

import socket
import time
import threading
import logging
import serial.tools.list_ports
from apps.arduino.controller import ArduinoController

logger = logging.getLogger(__name__)

class ArduinoController:
    def __init__(self, host=None, port=8888, use_tcp=False, serial_port=None, baud_rate=9600):
        self.use_tcp = use_tcp
        
        # Configuración TCP/IP para ESP32
        self.host = host  # Dirección IP del ESP32
        self.tcp_port = port  # Puerto TCP del ESP32
        self.socket = None
        
        # Configuración serie para conexión directa con Arduino
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.arduino = None
        
        self.connected = False
        self.lock = threading.RLock()
        self.servo_pins = [i for i in range(2, 32)]
        
        # New: watchdog timer para reconexión automática
        self.watchdog_active = False
        self.watchdog_thread = None
        self.last_command_time = time.time()
        
        connection_type = f"TCP/IP ({host}:{port})" if use_tcp else f"Serial ({serial_port})"
        logger.info(f"ArduinoController initialized with {connection_type}")

    def get_available_ports(self):
        """Obtiene una lista de puertos seriales disponibles"""
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                'device': port.device,
                'description': port.description,
                'hwid': port.hwid
            })
        return ports

    def _start_watchdog(self):
        """Inicia un watchdog para mantener la conexión"""
        if self.watchdog_active:
            return
            
        self.watchdog_active = True
        
        def watchdog_function():
            while self.watchdog_active:
                try:
                    # Si han pasado más de 30 segundos desde el último comando, verificar conexión
                    if time.time() - self.last_command_time > 30:
                        logger.info("Watchdog: verificando conexión...")
                        if not self._test_connection():
                            logger.warning("Watchdog: conexión perdida, intentando reconectar...")
                            self.disconnect()
                            self.connect()
                        else:
                            logger.info("Watchdog: conexión OK")
                        self.last_command_time = time.time()
                    time.sleep(5)  # Verificar cada 5 segundos
                except Exception as e:
                    logger.error(f"Error en watchdog: {str(e)}")
        
        self.watchdog_thread = threading.Thread(target=watchdog_function, daemon=True)
        self.watchdog_thread.start()
        logger.info("Watchdog para conexión Arduino iniciado")

    def _stop_watchdog(self):
        """Detiene el watchdog de conexión"""
        self.watchdog_active = False
        if self.watchdog_thread:
            self.watchdog_thread = None
        logger.info("Watchdog para conexión Arduino detenido")

    def connect(self, retries=3, delay=0.5):
        # Desconecta primero cualquier conexión previa
        self.disconnect()

        if self.use_tcp:
            # Modo TCP/IP para ESP32
            if not self.host:
                logger.error("No se especificó dirección IP del ESP32")
                return False
                
            logger.info(f"Intentando conectar a ESP32 en {self.host}:{self.tcp_port}")
            
            for attempt in range(retries):
                try:
                    logger.info(f"Intento de conexión TCP {attempt+1}/{retries}")
                    
                    with self.lock:
                        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        self.socket.settimeout(5)  # 5 segundos de timeout
                        self.socket.connect((self.host, self.tcp_port))
                    
                    # Tiempo de espera para estabilizar conexión
                    time.sleep(1)
                    
                    test_result = self._test_connection()
                    if test_result:
                        self.connected = True
                        logger.info(f"✅ Conectado a ESP32 en {self.host}:{self.tcp_port}")
                        # Iniciar watchdog
                        self._start_watchdog()
                        return True
                    else:
                        logger.warning("La conexión no respondió a la prueba")
                        self.disconnect()
                        
                except Exception as e:
                    with self.lock:
                        if self.socket:
                            try:
                                self.socket.close()
                            except:
                                pass
                            self.socket = None
                    self.connected = False
                    logger.error(f"⚠️ Error de conexión TCP en intento {attempt+1}: {str(e)}")
                    print(f"⚠️ Error de conexión TCP en intento {attempt+1}: {str(e)}")
                    time.sleep(delay)
        else:
            # Modo serie directo con Arduino
            if not self.serial_port:
                logger.error("No se especificó ningún puerto serie")
                return False
                
            logger.info(f"Intentando conectar a Arduino en {self.serial_port} (baud_rate={self.baud_rate})")
            
            available_ports = self.get_available_ports()
            if available_ports:
                logger.info(f"Puertos disponibles: {available_ports}")
            else:
                logger.warning("No se encontraron puertos seriales disponibles")
            
            for attempt in range(retries):
                try:
                    logger.info(f"Intento de conexión serie {attempt+1}/{retries}")
                    
                    with self.lock:
                        self.arduino = serial.Serial(self.serial_port, self.baud_rate, timeout=2)
                    
                    # Tiempo de espera para autoreset del Arduino
                    time.sleep(3)
                    
                    test_result = self._test_connection()
                    if test_result:
                        self.connected = True
                        logger.info(f"✅ Conectado a Arduino en {self.serial_port}")
                        # Iniciar watchdog
                        self._start_watchdog()
                        return True
                    else:
                        logger.warning("La conexión no respondió a la prueba")
                        self.disconnect()
                        
                except serial.SerialException as e:
                    with self.lock:
                        if self.arduino:
                            try:
                                self.arduino.close()
                            except:
                                pass
                            self.arduino = None
                    self.connected = False
                    logger.error(f"⚠️ Error de conexión serie en intento {attempt+1}: {str(e)}")
                    print(f"⚠️ Error de conexión serie en intento {attempt+1}: {str(e)}")
                    time.sleep(delay)
                    
        logger.error(f"⚠️ No se pudo conectar con el dispositivo después de {retries} intentos")
        return False

    def _test_connection(self):
        """Prueba si la conexión con Arduino está funcionando"""
        try:
            with self.lock:
                if self.use_tcp:
                    if not self.socket:
                        return False
                    
                    # Limpiar buffer
                    self.socket.settimeout(0.1)
                    try:
                        while True:
                            data = self.socket.recv(1024)
                            if not data:
                                break
                    except socket.timeout:
                        pass
                    
                    # Enviar comando de prueba
                    test_cmd = "2,90\n"
                    self.socket.sendall(test_cmd.encode())
                    
                    # Intentar leer respuesta
                    self.socket.settimeout(2.0)
                    try:
                        response = self.socket.recv(1024).decode().strip()
                        logger.info(f"ESP32 respondió: {response}")
                        return True
                    except socket.timeout:
                        logger.warning("ESP32 no respondió a la prueba en el tiempo esperado")
                        return False
                else:
                    if not self.arduino or not self.arduino.is_open:
                        return False
                    
                    self.arduino.reset_input_buffer()
                    self.arduino.reset_output_buffer()
                    
                    test_cmd = "2,90\n"
                    self.arduino.write(test_cmd.encode())
                    
                    start_time = time.time()
                    while (time.time() - start_time) < 2.0:
                        if self.arduino.in_waiting > 0:
                            response = self.arduino.readline().decode().strip()
                            logger.info(f"Arduino respondió: {response}")
                            return True
                        time.sleep(0.1)
                        
                    logger.warning("Arduino no respondió a la prueba en el tiempo esperado")
                    return False
                
        except Exception as e:
            logger.error(f"Error durante prueba de conexión: {str(e)}")
            return False

    def disconnect(self):
        """Desconecta del Arduino o ESP32"""
        # Detener watchdog primero
        self._stop_watchdog()
        
        with self.lock:
            if self.use_tcp:
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                    self.socket = None
            else:
                if self.arduino and self.arduino.is_open:
                    self.arduino.close()
                    self.arduino = None
                    
            self.connected = False
            logger.info("Dispositivo desconectado")

    def is_connected(self):
        """Verifica si el controlador está conectado"""
        with self.lock:
            if self.use_tcp:
                connected = self.connected and self.socket is not None
            else:
                connected = self.connected and self.arduino and self.arduino.is_open
        return connected

    def set_servo(self, servo_id, angle):
        """Mueve un servo a una posición específica con manejo mejorado de concurrencia"""
        if not (0 <= angle <= 180):
            return False, "Ángulo fuera de rango (0-180)"
        if servo_id not in self.servo_pins:
            return False, f"ID de servo inválido, debe estar entre {min(self.servo_pins)} y {max(self.servo_pins)}"

        # Si no está conectado, intentar reconexión
        if not self.is_connected():
            logging.info("Dispositivo no conectado, intentando reconectar...")
            if not self.connect():
                return False, "No se pudo conectar al dispositivo"

        command = f"{servo_id},{angle}\n"
        logging.debug(f"Enviando comando: {command}")
        
        # Timeout para adquirir el lock (evita bloqueos indefinidos)
        lock_acquired = self.lock.acquire(timeout=1.0)
        if not lock_acquired:
            logging.warning(f"No se pudo adquirir el lock para el servo {servo_id} después de 1 segundo")
            return False, "Sistema ocupado, intente nuevamente"
        
        try:
            # Actualizar tiempo del último comando
            self.last_command_time = time.time()
            
            if self.use_tcp:
                # Enviar por TCP con timeout
                try:
                    self.socket.settimeout(0.7)  # 700ms timeout
                    self.socket.sendall(command.encode())
                    
                    # Non-blocking response check with timeout
                    try:
                        response = self.socket.recv(1024).decode().strip()
                        logging.debug(f"Respuesta del ESP32: {response}")
                    except Exception as e:
                        logging.debug(f"No se recibió respuesta del ESP32: {str(e)}")
                        
                except Exception as e:
                    logging.error(f"Error enviando comando TCP: {str(e)}")
                    self.connected = False
                    return False, f"Error de comunicación TCP: {str(e)}"
                    
            else:
                # Enviar por serie con mejor manejo de excepciones
                try:
                    if not self.arduino or not self.arduino.is_open:
                        return False, "Puerto serial no disponible"
                        
                    self.arduino.reset_input_buffer()
                    self.arduino.write(command.encode())
                    
                    # Non-blocking response check with timeout
                    start_time = time.time()
                    response = None
                    
                    while (time.time() - start_time) < 0.5:
                        if self.arduino.in_waiting > 0:
                            response = self.arduino.readline().decode().strip()
                            break
                        time.sleep(0.01)  # Más pequeño para ser más reactivo
                
                except Exception as e:
                    logging.error(f"Error enviando comando serial: {str(e)}")
                    self.connected = False
                    return False, f"Error de comunicación serial: {str(e)}"
            
            return True, f"Servo {servo_id} movido a posición {angle}"
            
        finally:
            # Asegurar que siempre se libere el lock
            self.lock.release()

    def reset_servos(self):
        """Resetea todos los servos a posición 0"""
        success = True
        messages = []
        
        for servo_id in self.servo_pins:
            result, message = self.set_servo(servo_id, 0)
            if not result:
                success = False
            messages.append(message)
            time.sleep(0.05)  # Small delay between commands
            
        return success, messages

    # Para ejecutar secuencias completas
    def run_sequence(self, commands):
        """Ejecuta una secuencia de comandos para servos con manejo de errores y concurrencia
        
        Args:
            commands: Lista de diccionarios con pares servo_id y angle [{servo_id: 2, angle: 90, delay: 0.1}, ...]
            
        Returns:
            (success, messages): Tupla con éxito global y mensajes individuales
        """
        success = True
        messages = []
        
        # Indicar ejecución de secuencia
        logging.info(f"Iniciando ejecución de secuencia con {len(commands)} pasos")
        
        # Verificar y normalizar comandos
        valid_commands = []
        for i, cmd in enumerate(commands):
            if 'servo_id' not in cmd or 'angle' not in cmd:
                messages.append(f"Paso {i+1}: comando inválido - falta servo_id o angle")
                success = False
                continue
                
            # Validar valores
            servo_id = cmd['servo_id']
            angle = cmd['angle']
            delay = cmd.get('delay', 0.1)
            
            if not isinstance(servo_id, int) or not isinstance(angle, int):
                messages.append(f"Paso {i+1}: valores no numéricos")
                success = False
                continue
                
            if servo_id not in self.servo_pins:
                messages.append(f"Paso {i+1}: ID de servo inválido ({servo_id})")
                success = False
                continue
                
            if not (0 <= angle <= 180):
                messages.append(f"Paso {i+1}: ángulo fuera de rango ({angle})")
                success = False
                continue
                
            valid_commands.append({'servo_id': servo_id, 'angle': angle, 'delay': delay})
        
        # Si hay errores de validación, no ejecutar la secuencia
        if not success:
            return False, messages
        
        # Ejecutar secuencia comando por comando
        for i, cmd in enumerate(valid_commands):
            servo_id = cmd['servo_id']
            angle = cmd['angle']
            delay = cmd['delay']
            
            # Usar el método set_servo mejorado que ya maneja los locks
            result, message = self.set_servo(servo_id, angle)
            
            if not result:
                success = False
                messages.append(f"Paso {i+1}: Error - {message}")
            else:
                messages.append(f"Paso {i+1}: {message}")
            
            # Aplicar delay entre comandos
            if i < len(valid_commands) - 1:  # No esperar después del último comando
                time.sleep(delay)
        
        logging.info(f"Secuencia completada. Éxito: {success}")
        return success, messages

        """Ejecuta una secuencia de comandos para servos con manejo de errores
        
        Args:
            commands: Lista de diccionarios con pares servo_id y angle [{servo_id: 2, angle: 90}, ...]
            
        Returns:
            (success, messages): Tupla con éxito global y mensajes individuales
        """
        success = True
        messages = []
        
        for cmd in commands:
            servo_id = cmd.get('servo_id')
            angle = cmd.get('angle')
            delay = cmd.get('delay', 0.05)  # Delay entre comandos
            
            if servo_id is None or angle is None:
                success = False
                messages.append("Comando inválido: falta servo_id o angle")
                continue
                
            result, message = self.set_servo(servo_id, angle)
            if not result:
                success = False
            messages.append(message)
            
            # Pequeño delay entre comandos para no saturar Arduino
            if delay > 0:
                time.sleep(delay)
                
        return success, messages
        
    def get_diagnostics(self):
        """Obtiene diagnóstico del estado del controlador"""
        diagnostics = {
            "configuracion_actual": {
                "modo_conexion": "TCP/IP" if self.use_tcp else "Serial",
                "puerto_configurado": self.serial_port if self.serial_port else "No configurado",
                "host_tcp": self.host if self.host else "No configurado",
                "puerto_tcp": self.tcp_port if self.use_tcp else "N/A",
                "baud_rate": self.baud_rate,
                "estado_conexion": "Conectado" if self.is_connected() else "Desconectado",
                "watchdog_activo": self.watchdog_active
            },
            "puertos_disponibles": self.get_available_ports(),
            "info_adicional": {
                "tiempo_ultimo_comando": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.last_command_time))
            }
        }
        
        return diagnostics

    # Método para instalación en la clase ArduinoController
    def patch_arduino_controller():
        """Aplica los parches a la clase ArduinoController para mejorar el manejo de concurrencia"""
        
        # Reemplazar el método set_servo con nuestra versión mejorada
        ArduinoController.set_servo = set_servo
        
        # Añadir el nuevo método run_sequence
        ArduinoController.run_sequence = run_sequence
        
        logging.info("Se han aplicado las mejoras de concurrencia a ArduinoController")
        
    # Aplica los parches cuando se importa este módulo
    patch_arduino_controller()

# Singleton para usar en toda la aplicación
arduino_controller = None

def init_arduino(serial_port="COM12", baud_rate=9600, use_tcp=False, host=None, tcp_port=8888, connect_now=False):
    """Inicializa la instancia singleton del controlador Arduino"""
    global arduino_controller
    try:
        if arduino_controller is None:
            logger.info(f"Inicializando ArduinoController...")
            if use_tcp:
                logger.info(f"Usando TCP con host={host}, port={tcp_port}")
                arduino_controller = ArduinoController(
                    host=host, 
                    port=tcp_port, 
                    use_tcp=True
                )
            else:
                logger.info(f"Usando puerto serie={serial_port}, baud_rate={baud_rate}")
                arduino_controller = ArduinoController(
                    use_tcp=False,
                    serial_port=serial_port, 
                    baud_rate=baud_rate
                )
            
            # Connect now if requested
            if connect_now:
                arduino_controller.connect()
        
        # Actualizar configuración si es necesario
        elif (use_tcp and not arduino_controller.use_tcp) or \
             (not use_tcp and arduino_controller.use_tcp) or \
             (use_tcp and arduino_controller.host != host) or \
             (use_tcp and arduino_controller.tcp_port != tcp_port) or \
             (not use_tcp and arduino_controller.serial_port != serial_port) or \
             (not use_tcp and arduino_controller.baud_rate != baud_rate):
            
            # Disconnect first
            arduino_controller.disconnect()
            
            # Update settings
            arduino_controller.use_tcp = use_tcp
            if use_tcp:
                arduino_controller.host = host
                arduino_controller.tcp_port = tcp_port
                logger.info(f"Actualizada configuración TCP: host={host}, port={tcp_port}")
            else:
                arduino_controller.serial_port = serial_port
                arduino_controller.baud_rate = baud_rate
                logger.info(f"Actualizada configuración serie: port={serial_port}, baud_rate={baud_rate}")
            
            # Connect with new settings if requested
            if connect_now:
                arduino_controller.connect()
        
        # Try to connect if requested and not already connected
        elif connect_now and not arduino_controller.is_connected():
            arduino_controller.connect()
            
        return arduino_controller
    except Exception as e:
        logger.error(f"Error al inicializar ArduinoController: {str(e)}")
        return None
