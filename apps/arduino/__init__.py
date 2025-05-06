# -*- encoding: utf-8 -*-

from flask import Blueprint
import logging

# Configurar logger
logger = logging.getLogger(__name__)

blueprint = Blueprint(
    'arduino_blueprint',
    __name__,
    url_prefix='/arduino'
)


def apply_improvements():
    """Aplica las mejoras de concurrencia después que toda la app se ha inicializado"""
    try:
        # Importamos después de que todo se haya inicializado
        from apps.arduino.controller_improvements import patch_arduino_controller
        
        # Aplicar parches
        if patch_arduino_controller():
            logger.info("Mejoras de concurrencia aplicadas correctamente")
        else:
            logger.warning("No se pudieron aplicar todas las mejoras de concurrencia")
    except Exception as e:
        logger.error(f"Error al inicializar mejoras de concurrencia: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
