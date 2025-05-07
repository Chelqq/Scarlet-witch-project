from apps.arduino import blueprint
from flask import request, jsonify, current_app
from flask_login import login_required
from apps.arduino.controller import arduino_controller, init_arduino
import time
import logging
import os
import json

# Configurar logger
logger = logging.getLogger(__name__)

# Directorio para almacenar las secuencias guardadas
SEQUENCES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sequences')

os.makedirs(SEQUENCES_DIR, exist_ok=True)

@blueprint.route('/sequences', methods=['GET'])
@login_required
def get_sequences():
    """Obtiene todas las secuencias guardadas"""
    try:
        sequences = []
        
        # Verificar que el directorio existe
        logger.info(f"Buscando secuencias en directorio: {SEQUENCES_DIR}")
        if not os.path.exists(SEQUENCES_DIR):
            logger.error(f"El directorio de secuencias no existe: {SEQUENCES_DIR}")
            os.makedirs(SEQUENCES_DIR, exist_ok=True)
            logger.info(f"Directorio creado")
        
        # Listar archivos en el directorio
        files = os.listdir(SEQUENCES_DIR)
        logger.info(f"Archivos encontrados: {files}")
        
        # Leer todos los archivos JSON en el directorio de secuencias
        for filename in files:
            if filename.endswith('.json'):
                file_path = os.path.join(SEQUENCES_DIR, filename)
                try:
                    with open(file_path, 'r') as f:
                        sequence = json.load(f)
                        sequences.append(sequence)
                        logger.info(f"Secuencia cargada: {sequence.get('name', 'Sin nombre')}")
                except Exception as e:
                    logger.error(f"Error al leer archivo de secuencia {filename}: {str(e)}")
        
        logger.info(f"Total de secuencias cargadas: {len(sequences)}")
        return jsonify({
            'status': 'success',
            'sequences': sequences
        })
    
    except Exception as e:
        import traceback
        logger.error(f"Error al obtener secuencias: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Error al obtener secuencias: {str(e)}',
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
        
        # Asegurarse de que el directorio existe
        os.makedirs(SEQUENCES_DIR, exist_ok=True)
        
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
        logger.error(f"Error al guardar secuencia: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Error al guardar secuencia: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

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

@blueprint.route('/sequences/<sequence_id>', methods=['DELETE'])
@login_required
def delete_sequence(sequence_id):
    """Elimina una secuencia existente"""
    try:
        # Formar la ruta al archivo de secuencia
        file_path = os.path.join(SEQUENCES_DIR, f"{sequence_id}.json")
        
        # Verificar si el archivo existe
        if not os.path.exists(file_path):
            return jsonify({
                'status': 'error',
                'message': f'La secuencia con ID {sequence_id} no existe'
            }), 404
        
        # Eliminar el archivo
        os.remove(file_path)
        
        return jsonify({
            'status': 'success',
            'message': 'Secuencia eliminada correctamente',
            'sequence_id': sequence_id
        })
    
    except Exception as e:
        import traceback
        logger.error(f"Error al eliminar secuencia: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Error al eliminar secuencia: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

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
            
            current_app.logger.info(f"Attempting to connect via TCP/IP to ESP32 at {host}:{port}")
            
            if arduino_controller is None:
                current_app.logger.info("Controller is None, initializing with TCP parameters")
                arduino_controller = init_arduino(
                    host=host, 
                    tcp_port=port, 
                    use_tcp=True
                )
                
                if arduino_controller is None:
                    current_app.logger.error("Failed to initialize controller")
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
                    current_app.logger.info(f"Updated TCP settings: {host}:{port}")
        else:
            # Modo serie directo con Arduino
            serial_port = data.get('serial_port', 'COM12')
            baud_rate = data.get('baud_rate', 9600)
            
            current_app.logger.info(f"Attempting to connect directly to Arduino on {serial_port}")
            
            if arduino_controller is None:
                current_app.logger.info("Controller is None, initializing with Serial parameters")
                arduino_controller = init_arduino(
                    serial_port=serial_port, 
                    baud_rate=baud_rate,
                    use_tcp=False
                )
                
                if arduino_controller is None:
                    current_app.logger.error("Failed to initialize controller")
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
                    current_app.logger.info(f"Updated serial settings: {serial_port}, {baud_rate}")
        
        current_app.logger.info("Attempting to connect")
        success = arduino_controller.connect()
        current_app.logger.info(f"Connection result: {success}")
        
        # Notificar a todos los clientes a través de Socket.IO sobre el cambio de estado
        try:
            # Verificar si Socket.IO está disponible
            socketio = current_app.config.get('SOCKETIO')
            if socketio:
                # Crear mensaje para Socket.IO
                connection_info = {
                    'is_connected': success,
                    'connection_type': 'wifi' if arduino_controller.use_tcp else 'serial',
                }
                
                if arduino_controller.use_tcp:
                    connection_info['host'] = arduino_controller.host
                    connection_info['port'] = arduino_controller.tcp_port
                else:
                    connection_info['serial_port'] = arduino_controller.serial_port
                
                # Emitir mensaje a todos los clientes
                socketio.emit('connection_status', connection_info)
        except Exception as e:
            current_app.logger.error(f"Error emitting Socket.IO event: {str(e)}")
            
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
        current_app.logger.error(f"Error en conexión: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500