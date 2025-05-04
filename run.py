# Modificación a run.py para añadir soporte WebSocket

import os
from flask import Response
from flask_migrate import Migrate
from flask_minify import Minify
from flask_socketio import SocketIO
from sys import exit
import logging
from flask import jsonify

from apps import create_app, db
from apps.config import config_dict
from apps.arduino.controller import arduino_controller, init_arduino

# Importamos las funciones desde el archivo video_processing.py
from video_processing import gen_video_feed

# WARNING: Don't run with debug turned on in production!
DEBUG = (os.getenv('DEBUG', 'False') == 'True')

# The configuration
get_config_mode = 'Debug' if DEBUG else 'Production'

try:
    # Load the configuration using the default values
    app_config = config_dict[get_config_mode.capitalize()]
except KeyError:
    exit('Error: Invalid <config_mode>. Expected values [Debug, Production] ')

app = create_app(app_config)
Migrate(app, db)

# Inicializar Socket.IO con el app de Flask
socketio = SocketIO(app, cors_allowed_origins="*")
app.config['SOCKETIO'] = socketio
app.logger.info("Socket.IO inicializado en run.py")

# Configurar el contexto global para video_processing
from video_processing import set_app_context
set_app_context(app, socketio)
app.logger.info("Contexto de aplicación establecido en video_processing")

# Registrar en el bridge
from arduino_bridge import register_arduino_controller, register_socketio, set_connection_status, set_controller
register_arduino_controller(arduino_controller)
set_controller(arduino_controller)
register_socketio(socketio)
app.logger.info(f"Controlador Arduino registrado globalmente: {arduino_controller is not None}")

# IMPORTANTE: Verifica primero si el controlador existe y está conectado
if arduino_controller is not None and arduino_controller.is_connected():
    app.logger.info("Arduino conectado, estableciendo estado en bridge")
    set_connection_status(True)
else:
    app.logger.info("Arduino desconectado, estado en bridge permanece False")

# Variable global para mantener el estado de conexión de Arduino
arduino_connection = {
    'is_connected': False,
    'connection_type': None,
    'host': None,
    'port': None,
    'serial_port': None
}

# Añadir a la configuración de la aplicación
app.config['ARDUINO_CONNECTION'] = arduino_connection

if not DEBUG:
    Minify(app=app, html=True, js=False, cssless=False)

if DEBUG:
    app.logger.info('DEBUG       = ' + str(DEBUG))
    app.logger.info('DBMS        = ' + app_config.SQLALCHEMY_DATABASE_URI)
    app.logger.info('ASSETS_ROOT = ' + app_config.ASSETS_ROOT)

@app.route('/video_feed_0')
def video_feed_0():
    return Response(gen_video_feed(1), # si, asi aparecen en orden
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed_1')
def video_feed_1():
    return Response(gen_video_feed(0), # si, asi aparecen en orden
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# Manejadores de eventos Socket.IO
@socketio.on('connect')
def handle_connect():
    app.logger.info('Cliente conectado a WebSocket')
    # Enviar estado actual de conexión al cliente
    socketio.emit('connection_status', arduino_connection)

@socketio.on('disconnect')
def handle_disconnect():
    app.logger.info('Cliente desconectado de WebSocket')

# En el controlador de Socket.IO, actualizar el almacenamiento global:
@socketio.on('connect_arduino')
def handle_connect_arduino(data):
    global arduino_controller, arduino_connection
    
    app.logger.info(f'Solicitud de conexión Arduino recibida: {data}')
    
    use_tcp = data.get('use_tcp', False)
    success = False
    message = ""
    
    try:
        if use_tcp:
            # Modo TCP/IP a través de ESP32
            host = data.get('host', '')
            port = data.get('port', 8888)
            
            app.logger.info(f"Intentando conectar vía TCP/IP a ESP32 en {host}:{port}")
            
            if arduino_controller is None:
                arduino_controller = init_arduino(
                    host=host, 
                    tcp_port=port, 
                    use_tcp=True
                )
            else:
                # Actualizar configuración si ha cambiado
                if host != arduino_controller.host or port != arduino_controller.tcp_port or not arduino_controller.use_tcp:
                    arduino_controller.host = host
                    arduino_controller.tcp_port = port
                    arduino_controller.use_tcp = True
        else:
            # Modo serie directo con Arduino
            serial_port = data.get('serial_port', 'COM12')
            baud_rate = data.get('baud_rate', 9600)
            
            app.logger.info(f"Intentando conectar directamente a Arduino en {serial_port}")
            
            if arduino_controller is None:
                arduino_controller = init_arduino(
                    serial_port=serial_port, 
                    baud_rate=baud_rate,
                    use_tcp=False
                )
            else:
                # Actualizar configuración si ha cambiado
                if serial_port != arduino_controller.serial_port or baud_rate != arduino_controller.baud_rate or arduino_controller.use_tcp:
                    arduino_controller.serial_port = serial_port
                    arduino_controller.baud_rate = baud_rate
                    arduino_controller.use_tcp = False
        
        if arduino_controller is None:
            success = False
            message = "No se pudo inicializar el controlador Arduino"
        else:
            success = arduino_controller.connect()
            
            if success:
                from arduino_bridge import set_connection_status
                set_connection_status(True)
                logger.info("Estado de conexión en bridge actualizado a CONECTADO")
                
                arduino_connection['is_connected'] = True
                arduino_connection['connection_type'] = 'wifi' if use_tcp else 'serial'
                
                if use_tcp:
                    arduino_connection['host'] = host
                    arduino_connection['port'] = port
                    arduino_connection['serial_port'] = None
                    message = f"Conectado a ESP32 en {host}:{port}"
                else:
                    arduino_connection['host'] = None
                    arduino_connection['port'] = None
                    arduino_connection['serial_port'] = serial_port
                    message = f"Conectado a Arduino en {serial_port}"
                
                # IMPORTANTE: Actualizar la configuración de la aplicación
                app.config['ARDUINO_CONNECTION'] = arduino_connection
            else:
                from arduino_bridge import set_connection_status
                set_connection_status(False)
                app.logger.info("Estado de conexión en bridge actualizado a DESCONECTADO")
                message = "No se pudo conectar con el dispositivo"
    
    except Exception as e:
        app.logger.error(f"Error en conexión: {str(e)}")
        success = False
        message = f"Error: {str(e)}"
    
    # Emitir estado actualizado a todos los clientes
    response = {
        'status': 'success' if success else 'error',
        'message': message,
        'connection_info': arduino_connection
    }
    socketio.emit('arduino_connection_result', response)
    return response

@socketio.on('set_servo')
def handle_set_servo(data):
    global arduino_controller
    
    app.logger.info(f'Solicitud para controlar servo: {data}')
    
    if arduino_controller is None or not arduino_controller.is_connected():
        response = {
            'status': 'error',
            'message': 'Arduino no está conectado'
        }
    else:
        try:
            servo_id = int(data['servo_id'])
            angle = int(data['angle'])
            
            success, message = arduino_controller.set_servo(servo_id, angle)
            
            response = {
                'status': 'success' if success else 'error',
                'message': message,
                'servo_id': servo_id,
                'angle': angle
            }
        except Exception as e:
            app.logger.error(f"Error al controlar servo: {str(e)}")
            response = {
                'status': 'error',
                'message': f"Error: {str(e)}"
            }
    
    return response

@socketio.on('reset_servos')
def handle_reset_servos(data=None):  # Ahora acepta un parámetro
    global arduino_controller
    
    if arduino_controller is None or not arduino_controller.is_connected():
        response = {
            'status': 'error',
            'message': 'Arduino no está conectado'
        }
    else:
        try:
            success, messages = arduino_controller.reset_servos()
            
            response = {
                'status': 'success' if success else 'error',
                'message': 'Todos los servos han sido reseteados' if success else 'Error al resetear servos',
                'details': messages
            }
        except Exception as e:
            app.logger.error(f"Error al resetear servos: {str(e)}")
            response = {
                'status': 'error',
                'message': f"Error: {str(e)}"
            }
    
    socketio.emit('reset_servos_result', response)
    return response

@socketio.on('run_sequence')
def handle_run_sequence(data):
    global arduino_controller
    
    if arduino_controller is None:
        response = {
            'status': 'error',
            'message': 'Arduino controller not initialized'
        }
    else:
        try:
            sequence = data.get('sequence', {})
            
            if not sequence or 'steps' not in sequence or not sequence['steps']:
                response = {
                    'status': 'error',
                    'message': 'Secuencia inválida o vacía'
                }
            else:
                # Verificar si Arduino está conectado
                if not arduino_controller.is_connected():
                    if not arduino_controller.connect():
                        response = {
                            'status': 'error',
                            'message': 'No se pudo conectar con Arduino'
                        }
                        socketio.emit('run_sequence_result', response)
                        return response
                
                # Formatear comandos para Arduino
                commands = []
                for step in sequence['steps']:
                    servo_id = step.get('servo_id')
                    angle = step.get('angle')
                    
                    if servo_id is None or angle is None:
                        response = {
                            'status': 'error',
                            'message': 'Paso inválido: falta servo_id o angle'
                        }
                        socketio.emit('run_sequence_result', response)
                        return response
                    
                    commands.append({
                        'servo_id': servo_id,
                        'angle': angle,
                        'delay': step.get('delay', sequence.get('defaultDelay', 100)) / 1000.0  # Convertir ms a segundos
                    })
                
                # Ejecutar la secuencia
                if hasattr(arduino_controller, 'run_sequence'):
                    success, messages = arduino_controller.run_sequence(commands)
                else:
                    # Fallback si run_sequence no está disponible
                    success = True
                    messages = []
                    
                    for cmd in commands:
                        result, message = arduino_controller.set_servo(cmd['servo_id'], cmd['angle'])
                        if not result:
                            success = False
                            messages.append(message)
                        import time
                        time.sleep(cmd['delay'])
                
                response = {
                    'status': 'success' if success else 'error',
                    'message': 'Secuencia ejecutada correctamente' if success else 'Error al ejecutar la secuencia',
                    'details': messages if not success else []
                }
        except Exception as e:
            import traceback
            app.logger.error(f"Error in run_sequence: {str(e)}")
            app.logger.error(traceback.format_exc())
            response = {
                'status': 'error',
                'message': f'Exception: {str(e)}',
                'traceback': traceback.format_exc()
            }
    
    socketio.emit('run_sequence_result', response)
    return response

@socketio.on('get_connection_status')
def handle_get_connection_status(sid=None):  # Añadir el parámetro sid
    """Maneja la solicitud de estado de conexión desde el cliente"""
    global arduino_controller, arduino_connection
    
    # Actualizar el estado actual
    if arduino_controller:
        arduino_connection['is_connected'] = arduino_controller.is_connected()
    else:
        arduino_connection['is_connected'] = False
    
    return arduino_connection

@app.route('/test_servo/<int:servo_id>/<int:angle>')
def test_servo(servo_id, angle):
    """Endpoint para probar el envío directo de comandos a servos"""
    global arduino_controller
    
    if arduino_controller is None:
        return jsonify({
            'status': 'error',
            'message': 'Arduino controller no inicializado'
        }), 400
        
    if not arduino_controller.is_connected():
        return jsonify({
            'status': 'error',
            'message': 'Arduino no conectado'
        }), 400
    
    try:
        success, message = arduino_controller.set_servo(servo_id, angle)
        
        return jsonify({
            'status': 'success' if success else 'error',
            'message': message,
            'servo_id': servo_id,
            'angle': angle
        })
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/arduino_diagnostics')
def arduino_diagnostics():
    """Obtiene diagnóstico detallado del estado del Arduino"""
    global arduino_controller
    
    if arduino_controller is None:
        return jsonify({
            'status': 'error',
            'message': 'Arduino controller no inicializado'
        }), 400
    
    # Obtener diagnóstico del controlador
    try:
        diagnostics = arduino_controller.get_diagnostics()
        return jsonify(diagnostics)
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500

@socketio.on('hand_gesture_servo')
def handle_hand_gesture_servo(data):
    """Maneja eventos de servo basados en gestos de mano"""
    global arduino_controller
    
    app.logger.info(f'Recibido evento de gesto de mano para servo: {data}')
    
    if arduino_controller is None or not arduino_controller.is_connected():
        app.logger.warning('Arduino no está conectado para procesar gesto de mano')
        response = {
            'status': 'error',
            'message': 'Arduino no está conectado'
        }
    else:
        try:
            servo_id = int(data['servo_id'])
            angle = int(data['angle'])
            finger = data.get('finger', 'unknown')
            
            app.logger.info(f'Procesando gesto para {finger} - Servo {servo_id} a {angle}°')
            
            success, message = arduino_controller.set_servo(servo_id, angle)
            
            response = {
                'status': 'success' if success else 'error',
                'message': message,
                'servo_id': servo_id,
                'angle': angle,
                'finger': finger
            }
            
            app.logger.info(f'Resultado del gesto: {success} - {message}')
        except Exception as e:
            app.logger.error(f"Error al procesar gesto para servo: {str(e)}")
            response = {
                'status': 'error',
                'message': f"Error: {str(e)}"
            }
    
    # Emitimos resultado a todos los clientes
    socketio.emit('hand_gesture_result', response)
    return response

if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Iniciar el servidor con Socket.IO en lugar de app.run()
    socketio.run(app, debug=DEBUG, host='0.0.0.0')