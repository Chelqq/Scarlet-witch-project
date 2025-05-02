# -*- encoding: utf-8 -*-

from apps.arduino import blueprint
from flask import request, jsonify
from flask_login import login_required
from apps.arduino.controller import arduino_controller, init_arduino
from flask import current_app as app
import time
import logging
import os
import json

# Configurar logger
logger = logging.getLogger(__name__)

# Aplicar mejoras de concurrencia
try:
    from apps.arduino import apply_improvements
    apply_improvements()
except Exception as e:
    logger.error(f"No se pudieron aplicar mejoras de concurrencia: {str(e)}")

# Directorio para almacenar las secuencias guardadas
SEQUENCES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sequences')

# Asegurar que el directorio existe
os.makedirs(SEQUENCES_DIR, exist_ok=True)

@blueprint.route('/status')
@login_required
def status():
    """Devuelve el estado de la conexión con Arduino"""
    # Ensure controller is initialized but not connected
    if arduino_controller is None:
        init_arduino()
        
    if arduino_controller and arduino_controller.is_connected():
        if arduino_controller.use_tcp:
            return jsonify({
                'status': 'connected',
                'connection_type': 'wifi',
                'host': arduino_controller.host,
                'port': arduino_controller.tcp_port
            })
        else:
            return jsonify({
                'status': 'connected',
                'connection_type': 'serial',
                'port': arduino_controller.serial_port
            })
    else:
        return jsonify({
            'status': 'disconnected'
        })

@blueprint.route('/connect', methods=['POST'])
@login_required
def connect():
    """Intenta conectar con Arduino (directo o a través de ESP32)"""
    try:
        global arduino_controller
        data = request.json or {}
        
        # Verificar si es conexión TCP o serie
        use_tcp = data.get('use_tcp', False)
        
        if use_tcp:
            # Modo TCP/IP a través de ESP32
            host = data.get('host', '')
            port = data.get('port', 8888)
            
            app.logger.info(f"Attempting to connect via TCP/IP to ESP32 at {host}:{port}")
            
            if arduino_controller is None:
                app.logger.info("Controller is None, initializing with TCP parameters")
                arduino_controller = init_arduino(
                    host=host, 
                    tcp_port=port, 
                    use_tcp=True
                )
                
                if arduino_controller is None:
                    app.logger.error("Failed to initialize controller")
                    return jsonify({
                        'status': 'error',
                        'message': 'Failed to initialize ESP32 WiFi controller'
                    }), 500
            else:
                # Update settings if changed
                if host != arduino_controller.host or port != arduino_controller.tcp_port or not arduino_controller.use_tcp:
                    arduino_controller.host = host
                    arduino_controller.tcp_port = port
                    arduino_controller.use_tcp = True
                    app.logger.info(f"Updated TCP settings: {host}:{port}")
        else:
            # Modo serie directo con Arduino
            serial_port = data.get('serial_port', 'COM12')
            baud_rate = data.get('baud_rate', 9600)
            
            app.logger.info(f"Attempting to connect directly to Arduino on {serial_port}")
            
            if arduino_controller is None:
                app.logger.info("Controller is None, initializing with Serial parameters")
                arduino_controller = init_arduino(
                    serial_port=serial_port, 
                    baud_rate=baud_rate,
                    use_tcp=False
                )
                
                if arduino_controller is None:
                    app.logger.error("Failed to initialize controller")
                    return jsonify({
                        'status': 'error',
                        'message': 'Failed to initialize Arduino controller'
                    }), 500
            else:
                # Update settings if changed
                if serial_port != arduino_controller.serial_port or baud_rate != arduino_controller.baud_rate or arduino_controller.use_tcp:
                    arduino_controller.serial_port = serial_port
                    arduino_controller.baud_rate = baud_rate
                    arduino_controller.use_tcp = False
                    app.logger.info(f"Updated serial settings: {serial_port}, {baud_rate}")
        
        app.logger.info("Attempting to connect")
        success = arduino_controller.connect()
        app.logger.info(f"Connection result: {success}")
        
        if success:
            connection_type = "ESP32 WiFi" if arduino_controller.use_tcp else "Arduino directo"
            connection_details = f"ESP32 en {arduino_controller.host}:{arduino_controller.tcp_port}" if arduino_controller.use_tcp else f"Arduino en {arduino_controller.serial_port}"
            
            return jsonify({
                'status': 'success',
                'message': f'Conectado a {connection_details}',
                'connection_type': connection_type
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'No se pudo conectar con el dispositivo'
            }), 500
    
    except Exception as e:
        import traceback
        app.logger.error(f"Error in connect: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500
            
@blueprint.route('/set_servo', methods=['POST'])
@login_required
def set_servo():
    """Controla un servo específico"""
    try:
        global arduino_controller
        if arduino_controller is None:
            app.logger.error("Controller is None, trying to initialize with default settings")
            arduino_controller = init_arduino()
            
        if arduino_controller is None:
            app.logger.error("Controller is still None after initialization attempt")
            return jsonify({
                'status': 'error',
                'message': 'Arduino controller not initialized. Try connecting first.'
            }), 500
            
        data = request.json
        servo_id = int(data['servo_id'])
        angle = int(data['angle'])
        
        app.logger.info(f"Setting servo_id {servo_id} to angle {angle}")
        
        if not arduino_controller.is_connected():
            app.logger.info("Not connected, attempting to connect")
            if not arduino_controller.connect():
                return jsonify({
                    'status': 'error',
                    'message': 'Arduino not connected. Please connect first.'
                }), 400
        
        # Set timeout for the operation
        start_time = time.time()
        success, message = arduino_controller.set_servo(servo_id, angle)
        
        if time.time() - start_time > 1.0:  # If operation took too long
            app.logger.warning(f"Command execution took long time for servo_id {servo_id}, angle {angle}")
        
        app.logger.info(f"set_servo result: success={success}, message={message}")
        
        if success:
            return jsonify({
                'status': 'success',
                'servo_id': servo_id,
                'angle': angle,
                'message': message
            })
        else:
            return jsonify({
                'status': 'error',
                'message': message
            }), 400
            
    except Exception as e:
        import traceback
        app.logger.error(f"Error in set_servo: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error', 
            'message': f'Exception: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

@blueprint.route('/reset_servos', methods=['POST'])
@login_required
def reset_servos():
    """Resetea todos los servos a posición central"""
    if arduino_controller is None:
        init_arduino()
        
    if arduino_controller is None:
        return jsonify({
            'status': 'error',
            'message': 'Arduino controller not initialized'
        }), 500
        
    if not arduino_controller.is_connected():
        # Intentar conectar automáticamente
        if not arduino_controller.connect():
            return jsonify({
                'status': 'error',
                'message': 'Arduino not connected. Please connect first.'
            }), 400
        
    success, messages = arduino_controller.reset_servos()
    
    if success:
        return jsonify({
            'status': 'success',
            'message': 'Todos los servos han sido reseteados'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Error al resetear algunos servos',
            'details': messages
        }), 500

@blueprint.route('/diagnostico')
@login_required
def diagnostico():
    """Diagnóstico de puertos y conexión Arduino"""
    try:
        import serial
        import serial.tools.list_ports
        
        if arduino_controller is None:
            init_arduino()
            
        puertos = []
        for p in serial.tools.list_ports.comports():
            puertos.append({
                'dispositivo': p.device,
                'descripcion': p.description,
                'hwid': p.hwid
            })
        
        config_actual = {
            'puerto_configurado': arduino_controller.serial_port if arduino_controller else 'No inicializado',
            'baud_rate': arduino_controller.baud_rate if arduino_controller else 'No inicializado',
            'estado_conexion': 'Conectado' if (arduino_controller and arduino_controller.is_connected()) else 'Desconectado'
        }
        
        info_adicional = {}
        if arduino_controller:
            if arduino_controller.use_tcp:
                info_adicional['modo_conexion'] = 'TCP/IP'
                info_adicional['host'] = arduino_controller.host
                info_adicional['tcp_port'] = arduino_controller.tcp_port
            else:
                info_adicional['modo_conexion'] = 'Serial'
                if arduino_controller.arduino:
                    try:
                        info_adicional['arduino_abierto'] = arduino_controller.arduino.is_open
                        info_adicional['arduino_nombre'] = arduino_controller.arduino.name
                        info_adicional['arduino_timeout'] = arduino_controller.arduino.timeout
                    except Exception as e:
                        info_adicional['error'] = f'No se pudo obtener información adicional: {str(e)}'
        
        import pkg_resources
        pyserial_version = pkg_resources.get_distribution("pyserial").version
        
        return jsonify({
            'pyserial_version': pyserial_version,
            'puertos_disponibles': puertos,
            'configuracion_actual': config_actual,
            'info_adicional': info_adicional
        })
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': error_trace
        }), 500

@blueprint.route('/diagnostics')
@login_required
def diagnostics():
    """Returns detailed diagnostic information"""
    if arduino_controller is None:
        init_arduino()
        
    if arduino_controller is None:
        return jsonify({
            'status': 'error',
            'message': 'No se pudo inicializar el controlador de Arduino'
        })
    
    diagnostics = arduino_controller.get_diagnostics()
    
    import serial
    diagnostics['pyserial_version'] = serial.__version__
    
    return jsonify(diagnostics)

# Rutas para secuencias
@blueprint.route('/sequences', methods=['GET'])
@login_required
def get_sequences():
    """Obtiene todas las secuencias guardadas"""
    try:
        sequences = []
        
        # Leer todos los archivos JSON en el directorio de secuencias
        for filename in os.listdir(SEQUENCES_DIR):
            if filename.endswith('.json'):
                file_path = os.path.join(SEQUENCES_DIR, filename)
                with open(file_path, 'r') as f:
                    sequence = json.load(f)
                    sequences.append(sequence)
        
        return jsonify({
            'status': 'success',
            'sequences': sequences
        })
    
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': f'Error al obtener secuencias: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

@blueprint.route('/sequences/<sequence_id>', methods=['GET'])
@login_required
def get_sequence(sequence_id):
    """Obtiene una secuencia específica por ID"""
    try:
        file_path = os.path.join(SEQUENCES_DIR, f"{sequence_id}.json")
        
        if not os.path.exists(file_path):
            return jsonify({
                'status': 'error',
                'message': f'Secuencia con ID {sequence_id} no encontrada'
            }), 404
        
        with open(file_path, 'r') as f:
            sequence = json.load(f)
        
        return jsonify({
            'status': 'success',
            'sequence': sequence
        })
    
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': f'Error al obtener secuencia: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

@blueprint.route('/sequences', methods=['POST'])
@login_required
def save_sequence():
    """Guarda una nueva secuencia o actualiza una existente"""
    try:
        sequence = request.json
        
        # Validar datos mínimos
        if not sequence.get('name'):
            return jsonify({
                'status': 'error',
                'message': 'El nombre de la secuencia es obligatorio'
            }), 400
        
        if not sequence.get('steps') or not isinstance(sequence['steps'], list) or len(sequence['steps']) == 0:
            return jsonify({
                'status': 'error',
                'message': 'La secuencia debe tener al menos un paso'
            }), 400
        
        # Generar ID si es una nueva secuencia
        if not sequence.get('id'):
            sequence['id'] = f"seq_{int(time.time())}"
        
        # Guardar la secuencia en un archivo JSON
        file_path = os.path.join(SEQUENCES_DIR, f"{sequence['id']}.json")
        
        with open(file_path, 'w') as f:
            json.dump(sequence, f, indent=2)
        
        return jsonify({
            'status': 'success',
            'message': 'Secuencia guardada correctamente',
            'sequence_id': sequence['id']
        })
    
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': f'Error al guardar secuencia: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

@blueprint.route('/sequences/<sequence_id>', methods=['DELETE'])
@login_required
def delete_sequence(sequence_id):
    """Elimina una secuencia existente"""
    try:
        file_path = os.path.join(SEQUENCES_DIR, f"{sequence_id}.json")
        
        if not os.path.exists(file_path):
            return jsonify({
                'status': 'error',
                'message': f'Secuencia con ID {sequence_id} no encontrada'
            }), 404
        
        # Eliminar el archivo
        os.remove(file_path)
        
        return jsonify({
            'status': 'success',
            'message': 'Secuencia eliminada correctamente'
        })
    
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': f'Error al eliminar secuencia: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

@blueprint.route('/run_sequence', methods=['POST'])
@login_required
def run_sequence():
    """Ejecuta una secuencia de comandos para servos"""
    global arduino_controller
    
    try:
        if arduino_controller is None:
            init_arduino()
            
        if arduino_controller is None:
            return jsonify({
                'status': 'error',
                'message': 'Arduino controller not initialized'
            }), 500
        
        # Obtener datos de la secuencia
        data = request.json
        sequence = data.get('sequence')
        
        if not sequence or 'steps' not in sequence or not sequence['steps']:
            return jsonify({
                'status': 'error',
                'message': 'Secuencia inválida o vacía'
            }), 400
        
        # Verificar si Arduino está conectado
        if not arduino_controller.is_connected():
            if not arduino_controller.connect():
                return jsonify({
                    'status': 'error',
                    'message': 'No se pudo conectar con Arduino'
                }), 500
        
        # Formatear comandos para Arduino
        commands = []
        for step in sequence['steps']:
            servo_id = step.get('servo_id')
            angle = step.get('angle')
            
            if servo_id is None or angle is None:
                return jsonify({
                    'status': 'error',
                    'message': 'Paso inválido: falta servo_id o angle'
                }), 400
            
            commands.append({
                'servo_id': servo_id,
                'angle': angle,
                'delay': step.get('delay', sequence.get('defaultDelay', 100)) / 1000.0  # Convertir ms a segundos
            })
        
        # Ejecutar la secuencia (si run_sequence está disponible)
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
                time.sleep(cmd['delay'])
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Secuencia ejecutada correctamente'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Error al ejecutar la secuencia',
                'details': messages
            }), 500
            
    except Exception as e:
        import traceback
        current_app.logger.error(f"Error in run_sequence: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Exception: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500