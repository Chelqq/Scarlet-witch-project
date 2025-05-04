"""Módulo puente para comunicación entre Arduino y otros procesos"""

import logging
from threading import RLock

# Configurar logger
logger = logging.getLogger(__name__)

# Singleton para estado global
_arduino_controller = None
_socketio = None
_connected = False
_lock = RLock()

def register_arduino_controller(controller):
    """Registra el controlador Arduino para uso global"""
    global _arduino_controller
    with _lock:
        _arduino_controller = controller
        logger.info("Arduino controller registrado en bridge")
    
def register_socketio(socketio_instance):
    """Registra la instancia de Socket.IO para uso global"""
    global _socketio
    with _lock:
        _socketio = socketio_instance
        logger.info("Socket.IO registrado en bridge")

def set_connection_status(status):
    """Establece el estado de conexión"""
    global _connected
    with _lock:
        _connected = status
        logger.info(f"Estado de conexión establecido en: {status}")

def is_connected():
    """Retorna el estado de conexión real del controlador"""
    with _lock:
        controller = _arduino_controller
        connected = _connected
    
    # Verificar el estado real del controlador, no solo la bandera
    if controller is not None and controller.is_connected():
        # Si el controlador está conectado pero la bandera dice lo contrario, actualizar la bandera
        if not connected:
            set_connection_status(True)
        return True
    else:
        # Si el controlador no está conectado pero la bandera dice lo contrario, actualizar la bandera
        if connected:
            set_connection_status(False)
        return False

def move_servo(servo_id, angle):
    """Mueve un servo usando el controlador o Socket.IO, según disponibilidad"""
    with _lock:
        controller = _arduino_controller
        socketio = _socketio
        connected = _connected
    
    if not connected:
        logger.warning(f"Intento de mover servo {servo_id} sin conexión activa")
        return False
    
    try:
        # Intentar primero con controlador directo
        if controller is not None and controller.is_connected():
            logger.info(f"COMANDO: Moviendo servo {servo_id} a {angle}° con controlador directo")
            
            # Imprimir detalles del controlador para debug
            logger.info(f"Detalles del controlador: use_tcp={controller.use_tcp}, connected={controller.connected}")
            if controller.use_tcp:
                logger.info(f"TCP info: host={controller.host}, port={controller.tcp_port}")
            else:
                logger.info(f"Serial info: port={controller.serial_port}, baud_rate={controller.baud_rate}")
            
            success, message = controller.set_servo(servo_id, angle)
            logger.info(f"Resultado de comando: success={success}, message={message}")
            return success
        
        # Si no hay controlador o no está conectado, usar Socket.IO
        elif socketio is not None:
            logger.info(f"COMANDO: Moviendo servo {servo_id} a {angle}° con Socket.IO")
            socketio.emit('set_servo', {
                'servo_id': servo_id, 
                'angle': angle
            })
            return True
        
        else:
            logger.warning("No hay mecanismo disponible para mover servos")
            return False
            
    except Exception as e:
        logger.error(f"Error al mover servo {servo_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def move_multiple_servos(servo_commands):
    """Mueve múltiples servos a la vez"""
    results = []
    
    for cmd in servo_commands:
        servo_id = cmd.get('servo_id')
        angle = cmd.get('angle')
        
        if servo_id is None or angle is None:
            logger.warning("Comando inválido de servo - falta servo_id o angle")
            results.append(False)
            continue
            
        success = move_servo(servo_id, angle)
        results.append(success)
    
    return all(results)