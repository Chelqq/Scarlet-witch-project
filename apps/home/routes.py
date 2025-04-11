# -*- encoding: utf-8 -*-"""

from apps.home import blueprint
from flask import render_template, request
from flask_login import login_required
from jinja2 import TemplateNotFound
import serial
import time
from flask import jsonify
from apps.arduino.controller import arduino_controller, init_arduino


@blueprint.route('/index')
@login_required
def index():

    return render_template('home/index.html', segment='index')


@blueprint.route('/<template>')
@login_required
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'index'

        return segment

    except:
        return None
    
# @blueprint.route('/debug_info')
# @login_required
# def debug_info():
#     """Obtiene información detallada de depuración"""
#     try:
#         if arduino_controller is None:
#             init_arduino()
            
#         if arduino_controller:
#             debug_info = arduino_controller.get_debug_info()
#             return jsonify(debug_info)
#         else:
#             return jsonify({
#                 'status': 'error',
#                 'message': 'No se pudo inicializar el controlador de Arduino'
#             }), 500
#     except Exception as e:
#         import traceback
#         return jsonify({
#             'status': 'error',
#             'message': str(e),
#             'traceback': traceback.format_exc()
#         }), 500
        
@blueprint.route('/debug_info')
@login_required
def debug_info():
    """Debug information endpoint"""
    try:
        from apps.arduino.controller import arduino_controller, init_arduino
        
        if arduino_controller is None:
            init_arduino()
            
        if arduino_controller is None:
            return jsonify({
                'status': 'error',
                'message': 'No se pudo inicializar el controlador de Arduino'
            })
            
        # Get connection status
        is_connected = arduino_controller.is_connected()
        
        # Try to connect if not connected
        if not is_connected:
            connect_result = arduino_controller.connect()
            is_connected = connect_result
            
        return jsonify({
            'status': 'success' if is_connected else 'error',
            'message': 'Arduino conectado' if is_connected else 'No se pudo conectar al Arduino',
            'port': arduino_controller.port,
            'baud_rate': arduino_controller.baud_rate,
            'available_ports': arduino_controller.get_available_ports()
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        })