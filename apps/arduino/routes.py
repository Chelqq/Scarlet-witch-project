# -*- encoding: utf-8 -*-

from apps.arduino import blueprint
from flask import request, jsonify
from flask_login import login_required
from apps.arduino.controller import arduino_controller, init_arduino
import serial
import serial.tools.list_ports
from flask import current_app as app
import time

@blueprint.route('/status')
@login_required
def status():
    """Devuelve el estado de la conexión con Arduino"""
    # Ensure controller is initialized but not connected
    if arduino_controller is None:
        init_arduino()
        
    if arduino_controller and arduino_controller.is_connected():
        return jsonify({
            'status': 'connected',
            'port': arduino_controller.port
        })
    else:
        return jsonify({
            'status': 'disconnected'
        })

@blueprint.route('/connect', methods=['POST'])
@login_required
def connect():
    """Intenta conectar con Arduino"""
    try:
        global arduino_controller
        data = request.json or {}
        port = data.get('port', 'COM12')
        baud_rate = data.get('baud_rate', 9600)
        
        app.logger.info(f"Attempting to connect to port {port} with baud rate {baud_rate}")
        
        if arduino_controller is None:
            app.logger.info("Controller is None, initializing with provided parameters")
            arduino_controller = init_arduino(port=port, baud_rate=baud_rate)
            
            if arduino_controller is None:
                app.logger.error("Failed to initialize controller")
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to initialize Arduino controller'
                }), 500
        else:
            if port != arduino_controller.port:
                arduino_controller.port = port
                app.logger.info(f"Updated port to {port}")
            if baud_rate != arduino_controller.baud_rate:
                arduino_controller.baud_rate = baud_rate
                app.logger.info(f"Updated baud rate to {baud_rate}")
        
        app.logger.info("Attempting to connect")
        success = arduino_controller.connect()
        app.logger.info(f"Connection result: {success}")
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'Conectado a Arduino en {port}'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'No se pudo conectar con Arduino'
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
            app.logger.error("Controller is None, trying to initialize with specific port")
            arduino_controller = init_arduino(port="COM12")
            
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
            app.logger.info("Not connected, please connect first")
            return jsonify({
                'status': 'error',
                'message': 'Arduino not connected. Please connect first.'
            }), 400
        
        # Set timeout for the operation
        start_time = time.time()
        success, message = arduino_controller.set_servo(servo_id, angle)
        
        if time.time() - start_time > 1.0:  # If operation took too long
            app.logger.error(f"Command execution took long time for servo_id {servo_id}, angle {angle}")
        
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
        
        puertos = []
        for p in serial.tools.list_ports.comports():
            puertos.append({
                'dispositivo': p.device,
                'descripcion': p.description,
                'hwid': p.hwid
            })
        
        config_actual = {
            'puerto_configurado': arduino_controller.port if arduino_controller else 'No inicializado',
            'baud_rate': arduino_controller.baud_rate if arduino_controller else 'No inicializado',
            'estado_conexion': 'Conectado' if (arduino_controller and arduino_controller.is_connected()) else 'Desconectado'
        }
        
        info_adicional = {}
        if arduino_controller and arduino_controller.arduino:
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