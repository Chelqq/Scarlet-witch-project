import cv2
import mediapipe as mp
import time
import threading
import logging
from apps.arduino.controller import arduino_controller, init_arduino

def ensure_bridge_initialized():
    """Asegura que el bridge está inicializado correctamente"""
    from arduino_bridge import register_arduino_controller, set_controller
    
    # Intentar conseguir el controlador global
    try:
        import sys
        run_module = sys.modules.get('run')
        if run_module and hasattr(run_module, 'arduino_controller'):
            ctrl = run_module.arduino_controller
            if ctrl is not None:
                logger.info("Registrando controlador desde run.py en bridge")
                register_arduino_controller(ctrl)
                set_controller(ctrl)
                return True
    except Exception as e:
        logger.error(f"Error al inicializar bridge: {str(e)}")
    
    return False

# Llamar a esta función de inicialización al cargar el módulo
ensure_bridge_initialized()

DISABLE_AUTO_CONNECT = True  # Nueva bandera global

# Variables globales compartidas
app_instance = None
socketio_instance = None
connection_info = None
lock = threading.RLock()
# Configure logger
logger = logging.getLogger(__name__)


# Initialize MediaPipe for hand tracking
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Global variables to store finger status
fingers_up = {
    "thumb": False,
    "index": False,
    "middle": False,
    "ring": False,
    "pinky": False
}
last_check_time = time.time()
finger_check_interval = 5  # Check every 5 seconds

# Lock for thread safety when updating finger status
status_lock = threading.RLock()

# Flag to track if Arduino has been initialized for video processing
arduino_initialized = False

def set_app_context(app, socketio):
    """Establece el contexto de la aplicación Flask de forma global"""
    global app_instance, socketio_instance, connection_info
    with lock:
        app_instance = app
        socketio_instance = socketio
        if 'ARDUINO_CONNECTION' in app.config:
            connection_info = app.config['ARDUINO_CONNECTION']
        
        logger.info(f"Contexto inicializado en video_processing: app={app is not None}, socketio={socketio is not None}")
        
        # Verificar que socketio_instance es válido
        if socketio_instance is not None:
            try:
                # Probar emisión de evento para verificar que funciona
                socketio_instance.emit('video_processing_initialized', {'status': 'success'})
                logger.info("Socket.IO inicializado correctamente en video_processing")
            except Exception as e:
                logger.error(f"Error al verificar Socket.IO en video_processing: {str(e)}")

def initialize_arduino_for_video():
    """Ensure Arduino controller is properly initialized for video processing"""
    global arduino_initialized, arduino_controller
    
    if arduino_initialized:
        return True
    
    try:
        # Importar el bridge y forzar una comprobación de estado
        from arduino_bridge import force_connection_status_check, register_arduino_controller
        
        # Verificar si hay un controlador global en run.py
        import sys
        run_module = sys.modules.get('run')
        if run_module and hasattr(run_module, 'arduino_controller'):
            arduino_controller_global = run_module.arduino_controller
            
            # Si existe el controlador y las interfaces lo están usando,
            # registrarlo en el bridge para asegurar la sincronización
            if arduino_controller_global is not None:
                logger.info("Registrando controlador global en bridge desde video_processing")
                register_arduino_controller(arduino_controller_global)
                
                # Forzar una verificación del estado real
                is_connected = force_connection_status_check()
                logger.info(f"Estado de conexión actual: {is_connected}")
                
                arduino_initialized = True
                return True
        
        logger.info("No se encontró controlador global, inicialización básica")
        arduino_initialized = True
        return False
        
    except Exception as e:
        logger.error(f"Error initializing Arduino for video: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        arduino_initialized = True  # Marcamos como inicializado para evitar reintento
        return False

def check_fingers_raised(hand_landmarks):
    """Determine which fingers are raised based on hand landmarks"""
    global fingers_up
    
    # MediaPipe hand landmarks reference:
    # - Wrist: 0
    # - Thumb tip: 4
    # - Index finger tip: 8, base: 5
    # - Middle finger tip: 12, base: 9
    # - Ring finger tip: 16, base: 13
    # - Pinky finger tip: 20, base: 17
    
    # Get hand landmarks as a list
    points = {}
    for idx, landmark in enumerate(hand_landmarks.landmark):
        points[idx] = (landmark.x, landmark.y, landmark.z)
    
    # Check if thumb is extended (comparing thumb tip to thumb CMC joint)
    thumb_up = points[4][0] < points[2][0] if points[4][0] < points[0][0] else points[4][0] > points[2][0]
    
    # Check for other fingers (if tip y position is higher than PIP joint)
    index_up = points[8][1] < points[6][1]
    middle_up = points[12][1] < points[10][1]
    ring_up = points[16][1] < points[14][1]
    pinky_up = points[20][1] < points[18][1]
    
    with status_lock:
        fingers_up["thumb"] = thumb_up
        fingers_up["index"] = index_up
        fingers_up["middle"] = middle_up
        fingers_up["ring"] = ring_up
        fingers_up["pinky"] = pinky_up
    
    return {
        "thumb": thumb_up,
        "index": index_up,
        "middle": middle_up,
        "ring": ring_up,
        "pinky": pinky_up
    }

def control_servos_with_hand(finger_status):
    """Control servos using the same mechanism as pre-programmed sequences"""
    # Obtener controlador desde el bridge (evitamos sys.modules)
    from arduino_bridge import get_controller
    
    arduino_controller = get_controller()
    
    if not arduino_controller:
        logger.error("Controlador Arduino no disponible en bridge")
        return False
    
    # Verificar conexión
    if not arduino_controller.is_connected():
        logger.warning("Arduino no conectado, intentando conectar...")
        try:
            connected = arduino_controller.connect()
            if not connected:
                logger.error("No se pudo conectar con Arduino")
                return False
            logger.info("Conexión con Arduino establecida")
        except Exception as e:
            logger.error(f"Error al conectar con Arduino: {str(e)}")
            return False
    
    # Mapeo de dedos a servos
    servo_mapping = {
        "thumb": 2,    # Servo en pin 2
        "index": 3,    # Servo en pin 3
        "middle": 4,   # Servo en pin 4
        "ring": 5,     # Servo en pin 5
        "pinky": 6     # Servo en pin 6
    }
    
    # Crear lista de comandos en el mismo formato que las secuencias
    commands = []
    for finger, servo_id in servo_mapping.items():
        angle = 180 if finger_status[finger] else 0
        commands.append({
            'servo_id': servo_id,
            'angle': angle,
            'delay': 0.1  # 100ms entre comandos
        })
    
    logger.info(f"GESTOS: Creados {len(commands)} comandos para servos")
    
    try:
        # Usar el mismo método que las secuencias
        if hasattr(arduino_controller, 'run_sequence'):
            logger.info("Ejecutando gestos con método run_sequence")
            success, messages = arduino_controller.run_sequence(commands)
            logger.info(f"Resultado: {success}, Mensajes: {str(messages)[:100]}")
        else:
            # Fallback: usar set_servo individual como en las secuencias
            logger.info("Ejecutando gestos con método set_servo individual")
            success = True
            for cmd in commands:
                logger.info(f"Enviando comando: Servo {cmd['servo_id']} a {cmd['angle']}°")
                result, message = arduino_controller.set_servo(cmd['servo_id'], cmd['angle'])
                logger.info(f"Resultado: {result}, Mensaje: {message}")
                if not result:
                    success = False
                import time
                time.sleep(cmd['delay'])
        
        if success:
            logger.info("Control por gestos ejecutado correctamente")
        else:
            logger.warning("Error al ejecutar control por gestos")
        
        return success
        
    except Exception as e:
        logger.error(f"Error al controlar servos: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def process_frame(frame, hands):
    """Process each frame using MediaPipe for hand tracking."""
    global last_check_time, fingers_up
    
    current_time = time.time()
    if current_time - last_check_time >= 10:  # Cada 10 segundos
        ensure_bridge_initialized()
    
    if frame is None:
        return None
    
    # Flip horizontally for a mirror effect
    frame = cv2.flip(frame, 1)
    
    # Convert the image from BGR to RGB for MediaPipe
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Process the frame with MediaPipe
    results = hands.process(rgb_frame)
    
    # Draw hand landmarks on the image
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS,
                mp_drawing_styles.get_default_hand_landmarks_style(),
                mp_drawing_styles.get_default_hand_connections_style()
            )
            
            # Check fingers raised every 5 seconds
            current_time = time.time()
            if current_time - last_check_time >= finger_check_interval:
                current_fingers = check_fingers_raised(hand_landmarks)
                logger.info(f"Fingers raised: {', '.join([f for f, up in current_fingers.items() if up])}")
                
                # Control Arduino servos based on finger status
                control_result = control_servos_with_hand(current_fingers)
                if control_result:
                    logger.info("Successfully sent servo commands")
                else:
                    logger.warning("Failed to send servo commands")
                
                last_check_time = current_time
    
    # Display finger status on the frame
    y_pos = 30
    with status_lock:
        for finger, is_up in fingers_up.items():
            status = "UP" if is_up else "DOWN"
            color = (0, 255, 0) if is_up else (0, 0, 255)
            cv2.putText(frame, f"{finger}: {status}", (10, y_pos), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            y_pos += 30
    
    # Display time until next check
    time_left = max(0, finger_check_interval - (time.time() - last_check_time))
    cv2.putText(frame, f"Next check in: {time_left:.1f}s", (10, y_pos), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    
    # Display connection status
    y_pos += 30
    if arduino_controller and arduino_controller.is_connected():
        cv2.putText(frame, "Arduino: Connected", (10, y_pos), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    else:
        cv2.putText(frame, "Arduino: Disconnected", (10, y_pos), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    
    return frame

def gen_video_feed(camera_id):
    """Generate video feed with hand tracking for the specified camera."""
    # Initialize Arduino connection when video feed starts
    initialize_arduino_for_video()
    
    try:
        cap = cv2.VideoCapture(camera_id)
        
        if not cap.isOpened():
            logger.error(f"Could not open camera {camera_id}")
            # Generate error frame
            error_frame = create_error_frame(f"Could not open camera {camera_id}")
            ret, buffer = cv2.imencode('.jpg', error_frame)
            error_bytes = buffer.tobytes()
            
            while True:
                yield (b'--frame\r\n'
                     b'Content-Type: image/jpeg\r\n\r\n' + error_bytes + b'\r\n')
                time.sleep(1)
        
        # Create a new instance of MediaPipe Hands for this camera
        hands = mp_hands.Hands(
            model_complexity=0,  # 0 for fastest performance, 1 for better accuracy
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7,
            max_num_hands=1
        )
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                logger.warning(f"Failed to read frame from camera {camera_id}")
                break
            
            # Process each frame with hand tracking
            processed_frame = process_frame(frame, hands)
            
            if processed_frame is None:
                continue
                
            # Encode the image to JPEG
            ret, buffer = cv2.imencode('.jpg', processed_frame)
            frame_bytes = buffer.tobytes()
            
            # Return the frame
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    
    except Exception as e:
        logger.error(f"Error in video feed generation: {str(e)}")
        error_frame = create_error_frame(f"Camera error: {str(e)}")
        ret, buffer = cv2.imencode('.jpg', error_frame)
        error_bytes = buffer.tobytes()
        
        while True:
            yield (b'--frame\r\n'
                 b'Content-Type: image/jpeg\r\n\r\n' + error_bytes + b'\r\n')
            time.sleep(1)
            
    finally:
        if 'cap' in locals() and cap.isOpened():
            cap.release()

def create_error_frame(message):
    from numpy import uint8 as np
    """Create a frame with error message when camera is not available"""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(frame, "Camera Error", (200, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(frame, message, (100, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    return frame
