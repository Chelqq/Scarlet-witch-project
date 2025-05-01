# Archivo apps/arduino/concurrency_patch.py 

import logging
import os
from functools import wraps
import threading

logger = logging.getLogger(__name__)

# Directorio para almacenar las secuencias guardadas
SEQUENCES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sequences')

# Asegurar que el directorio existe
os.makedirs(SEQUENCES_DIR, exist_ok=True)

def safe_rlock_decorator(func):
    """Decorador que asegura que un RLock siempre se libere, incluso si hay excepciones"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # Si no hay un lock definido, ejecutar normalmente
        if not hasattr(self, 'lock') or not isinstance(self.lock, threading.RLock):
            return func(self, *args, **kwargs)
            
        # Obtener el lock con timeout para evitar bloqueos
        lock_acquired = self.lock.acquire(timeout=1.0)
        if not lock_acquired:
            logger.warning(f"No se pudo adquirir el lock para {func.__name__} después de 1 segundo")
            return False, "Sistema ocupado, intente nuevamente"
            
        try:
            return func(self, *args, **kwargs)
        finally:
            # Asegurar que siempre se libere el lock
            self.lock.release()
    return wrapper

def apply_concurrency_fixes():
    """Aplica todas las mejoras de concurrencia a los módulos de la aplicación"""
    try:
        # Importar el controlador de Arduino
        from apps.arduino.controller import ArduinoController
        from apps.arduino.controller_improvements import patch_arduino_controller
        
        # Aplicar los parches
        patch_arduino_controller()
        
        logger.info("Se han aplicado las mejoras de concurrencia a la aplicación")
        return True
    except Exception as e:
        logger.error(f"Error al aplicar mejoras de concurrencia: {str(e)}")
        return False

# Inicialización automática cuando se importa este módulo
apply_concurrency_fixes()