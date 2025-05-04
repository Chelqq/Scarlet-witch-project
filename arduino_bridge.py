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
        old_status = _connected
        _connected = status
        if old_status != status:
            logger.info(f"Estado de conexión bridge actualizado: {old_status} -> {status}")

def force_connection_status_check():
    """Fuerza una comprobación del estado de conexión real"""
    global _arduino_controller, _connected
    
    if _arduino_controller is not None:
        is_really_connected = _arduino_controller.is_connected()
        set_connection_status(is_really_connected)
        logger.info(f"Verificación forzada de conexión: {is_really_connected}")
        return is_really_connected
    return False

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

def set_controller(controller):
    """Establece el controlador Arduino para uso global"""
    global _arduino_controller
    with _lock:
        _arduino_controller = controller
        logger.info(f"Controller establecido en bridge: {controller is not None}")

def get_controller():
    """Obtiene el controlador Arduino global, inicializándolo si es necesario"""
    global _arduino_controller
    with _lock:
        if _arduino_controller is None:
            try:
                # Intentar inicializar si no existe
                from apps.arduino.controller import init_arduino
                _arduino_controller = init_arduino(connect_now=False)
                if _arduino_controller:
                    logger.info("Controlador Arduino inicializado automáticamente en bridge")
            except Exception as e:
                logger.error(f"Error al inicializar controlador automáticamente: {str(e)}")
        return _arduino_controller

def ensure_controller():
    """Asegura que exista un controlador válido, intentando inicializarlo si no existe"""
    global _arduino_controller
    with _lock:
        controller = _arduino_controller
        
    if controller is None:
        try:
            # Intentar obtener desde run.py primero
            import sys
            run_module = sys.modules.get('run')
            if run_module and hasattr(run_module, 'arduino_controller'):
                controller = run_module.arduino_controller
                if controller is not None:
                    with _lock:
                        _arduino_controller = controller
                    logger.info("Controlador recuperado desde run.py")
                    return controller
            
            # Si no está disponible, crear uno nuevo
            from apps.arduino.controller import init_arduino
            controller = init_arduino(connect_now=False)
            if controller:
                with _lock:
                    _arduino_controller = controller
                logger.info("Nuevo controlador inicializado")
                return controller
        except Exception as e:
            logger.error(f"Error al intentar garantizar un controlador: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    return controller