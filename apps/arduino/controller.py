# -*- encoding: utf-8 -*-

import socket
import time
import threading
import logging
import serial.tools.list_ports

logger = logging.getLogger(__name__)

class ArduinoController:
    def __init__(self, host=None, port=8888, use_tcp=True, serial_port=None, baud_rate=9600):
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
        
        connection_type = f"TCP/IP ({host}:{port})" if use_tcp else f"Serial ({serial_port})"
        logger.info(f"ArduinoController initialized with {connection_type}")

    def get_available_ports(self):
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                'device': port.device,
                'description': port.description,
                'hwid': port.hwid
            })
        return ports

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
                        return True
                    else:
                        logger.warning("La conexión no respondió a la prueba")
                        
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
        with self.lock:
            if self.use_tcp:
                connected = self.connected and self.socket is not None
            else:
                connected = self.connected and self.arduino and self.arduino.is_open
        return connected

    def set_servo(self, servo_id, angle):
        if not (0 <= angle <= 180):
            return False, "Ángulo fuera de rango (0-180)"
        if servo_id not in self.servo_pins:
            return False, f"ID de servo inválido, debe estar entre {min(self.servo_pins)} y {max(self.servo_pins)}"

        command = f"{servo_id},{angle}\n"
        logger.debug(f"Enviando comando: {command}")
        
        with self.lock:
            if not self.is_connected():
                if not self.connect():
                    return False, "Dispositivo no conectado"
            
            try:
                if self.use_tcp:
                    # Enviar por TCP
                    self.socket.sendall(command.encode())
                    
                    # Non-blocking response check with timeout
                    self.socket.settimeout(0.5)  # 500ms timeout
                    try:
                        response = self.socket.recv(1024).decode().strip()
                        logger.debug(f"Respuesta del ESP32: {response}")
                    except socket.timeout:
                        logger.debug("No se recibió respuesta del ESP32 (timeout)")
                        
                else:
                    # Enviar por serie
                    self.arduino.reset_input_buffer()
                    self.arduino.write(command.encode())
                    
                    # Non-blocking response check with timeout
                    start_time = time.time()
                    response = None
                    
                    while (time.time() - start_time) < 0.5:
                        if self.arduino.in_waiting > 0:
                            response = self.arduino.readline().decode().strip()
                            break
                        time.sleep(0.05)
                
                return True, f"Servo {servo_id} movido a posición {angle}"
            except Exception as e:
                logger.error(f"Error enviando comando: {str(e)}")
                return False, f"Error: {str(e)}"

    def reset_servos(self):
        success = True
        messages = []
        
        for servo_id in self.servo_pins:
            result, message = self.set_servo(servo_id, 0)
            if not result:
                success = False
            messages.append(message)
            time.sleep(0.05)  # Small delay between commands
            
        return success, messages
        
    def get_diagnostics(self):
        diagnostics = {
            "configuracion_actual": {
                "puerto_configurado": self.port if self.port else "No configurado",
                "baud_rate": self.baud_rate,
                "estado_conexion": "Conectado" if self.is_connected() else "Desconectado"
            },
            "puertos_disponibles": self.get_available_ports(),
            "info_adicional": {}
        }
        
        return diagnostics

# Singleton para usar en toda la aplicación
arduino_controller = None
def init_arduino(port="COM12", baud_rate=9600):
    global arduino_controller
    try:
        if arduino_controller is None:
            logger.info(f"Inicializando ArduinoController con port={port}, baud_rate={baud_rate}")
            arduino_controller = ArduinoController(port, baud_rate)
            # Don't connect at initialization, wait for explicit connect request
        return arduino_controller
    except Exception as e:
        logger.error(f"Error al inicializar ArduinoController: {str(e)}")
        return None