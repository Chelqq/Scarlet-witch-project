# Archivo apps/arduino/controller_improvements.py - Versión corregida

import time
import threading
import logging
import serial

logger = logging.getLogger(__name__)

def improved_set_servo(self, servo_id, angle):
    """Mueve un servo a una posición específica con manejo mejorado de concurrencia"""
    if not (0 <= angle <= 180):
        return False, "Ángulo fuera de rango (0-180)"
    if servo_id not in self.servo_pins:
        return False, f"ID de servo inválido, debe estar entre {min(self.servo_pins)} y {max(self.servo_pins)}"

    # Si no está conectado, intentar reconexión
    if not self.is_connected():
        logger.info("Dispositivo no conectado, intentando reconectar...")
        if not self.connect():
            return False, "No se pudo conectar al dispositivo"

    command = f"{servo_id},{angle}\n"
    logger.debug(f"Enviando comando: {command}")
    
    # Timeout para adquirir el lock (evita bloqueos indefinidos)
    lock_acquired = self.lock.acquire(timeout=1.0)
    if not lock_acquired:
        logger.warning(f"No se pudo adquirir el lock para el servo {servo_id} después de 1 segundo")
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
                    logger.debug(f"Respuesta del ESP32: {response}")
                except Exception as e:
                    logger.debug(f"No se recibió respuesta del ESP32: {str(e)}")
                    
            except Exception as e:
                logger.error(f"Error enviando comando TCP: {str(e)}")
                self.connected = False
                return False, f"Error de comunicación TCP: {str(e)}"
                
        else:
            # Enviar por serie con mejor manejo de excepciones
            try:
                if not self.arduino or not self.arduino.is_open:
                    return False, "Puerto serial no disponible"
                    
                # Proteger contra errores de buffer
                try:
                    self.arduino.reset_input_buffer()
                except Exception as e:
                    logger.warning(f"No se pudo resetear buffer de entrada: {str(e)}")
                    
                try:
                    self.arduino.write(command.encode())
                except serial.SerialTimeoutException:
                    logger.error("Timeout al escribir en puerto serial")
                    return False, "Timeout al enviar comando"
                except Exception as e:
                    logger.error(f"Error escribiendo en puerto serial: {str(e)}")
                    return False, f"Error al enviar comando: {str(e)}"
                
                # Non-blocking response check with timeout
                start_time = time.time()
                response = None
                
                try:
                    while (time.time() - start_time) < 0.5:
                        if self.arduino.in_waiting > 0:
                            response = self.arduino.readline().decode().strip()
                            break
                        time.sleep(0.01)  # Más pequeño para ser más reactivo
                except Exception as e:
                    logger.warning(f"Error al leer respuesta: {str(e)}")
            
            except Exception as e:
                logger.error(f"Error enviando comando serial: {str(e)}")
                self.connected = False
                return False, f"Error de comunicación serial: {str(e)}"
        
        return True, f"Servo {servo_id} movido a posición {angle}"
        
    finally:
        # Asegurar que siempre se libere el lock
        self.lock.release()

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
    logger.info(f"Iniciando ejecución de secuencia con {len(commands)} pasos")
    
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
    step_success = True
    for i, cmd in enumerate(valid_commands):
        servo_id = cmd['servo_id']
        angle = cmd['angle']
        delay = cmd['delay']
        
        # Usar el método set_servo mejorado que ya maneja los locks
        result, message = self.set_servo(servo_id, angle)
        
        if not result:
            step_success = False
            messages.append(f"Paso {i+1}: Error - {message}")
        else:
            messages.append(f"Paso {i+1}: {message}")
        
        # Aplicar delay entre comandos
        if i < len(valid_commands) - 1:  # No esperar después del último comando
            time.sleep(delay)
    
    success = step_success
    logger.info(f"Secuencia completada. Éxito: {success}")
    return success, messages

def safe_connect(self, retries=3, delay=0.5):
    """Versión con mejor manejo de excepciones para el método connect"""
    from functools import wraps
    
    @wraps(self.connect)
    def wrapper(*args, **kwargs):
        try:
            return self.connect(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error en connect(): {str(e)}")
            self.connected = False
            return False
            
    return wrapper

def patch_arduino_controller():
    """Aplica los parches a la clase ArduinoController para mejorar el manejo de concurrencia"""
    try:
        # Importamos desde el contexto global, NO como importación directa
        import sys
        # Conseguimos el módulo de controller
        controller_module = sys.modules.get('apps.arduino.controller')
        
        if controller_module and hasattr(controller_module, 'ArduinoController'):
            # Accedemos a la clase ArduinoController
            ArduinoController = controller_module.ArduinoController
            
            # Reemplazar el método set_servo con nuestra versión mejorada
            ArduinoController.set_servo = improved_set_servo
            
            # Añadir el nuevo método run_sequence
            ArduinoController.run_sequence = run_sequence
            
            logger.info("Se han aplicado las mejoras de concurrencia a ArduinoController")
            return True
        else:
            logger.error("No se pudo acceder a ArduinoController")
            return False
    except Exception as e:
        logger.error(f"Error al aplicar parches: {str(e)}")
        return False