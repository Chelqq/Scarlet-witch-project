import cv2
import mediapipe as mp
import time
import threading
import logging
import sys

# Variables globales compartidas
app_instance = None
socketio_instance = None
connection_info = None
lock = threading.RLock()
# Configure logger
logger = logging.getLogger(__name__)

# Declarar las variables globales al inicio, antes de cualquier uso
arduino_controller = None  # Declaración temprana

# Inicializar MediaPipe para hand tracking
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Variables globales para almacenar el estado de los dedos
fingers_up = {
    "thumb": False,
    "index": False,
    "middle": False,
    "ring": False,
    "pinky": False
}
last_check_time = time.time()
finger_check_interval = 5  # Comprobar cada 5 segundos

# Lock para thread safety al actualizar el estado de los dedos
status_lock = threading.RLock()

# Flag para rastrear si Arduino ha sido inicializado para procesamiento de video
arduino_initialized = False

def set_app_context(app, socketio):
    """Establece el contexto de la aplicación Flask y el controlador Arduino de forma global"""
    global app_instance, socketio_instance, connection_info, arduino_controller
    
    with lock:
        app_instance = app
        socketio_instance = socketio
        logger.info(f"Contexto de aplicación establecido: app={app is not None}, socketio={socketio is not None}")
        
        # NUEVO: Obtener el controlador Arduino directamente del módulo run
        try:
            run_module = sys.modules.get('run')
            if run_module and hasattr(run_module, 'arduino_controller'):
                arduino_controller = run_module.arduino_controller
                logger.info(f"Controlador Arduino obtenido directamente del módulo run: {arduino_controller is not None}")
                
                # Verificar estado de conexión
                if arduino_controller is not None:
                    is_connected = arduino_controller.is_connected()
                    logger.info(f"Estado de conexión del controlador Arduino: {is_connected}")
            else:
                logger.warning("No se pudo obtener el controlador Arduino del módulo run")
        except Exception as e:
            logger.error(f"Error accediendo al controlador Arduino: {str(e)}")
            
        if 'ARDUINO_CONNECTION' in app.config:
            connection_info = app.config['ARDUINO_CONNECTION']
            logger.info(f"Información de conexión cargada de app.config: {connection_info}")

def control_servos_with_hand(finger_status):
    """Control Arduino servos based on hand finger positions using direct access to the Arduino controller"""
    global arduino_controller
    
    # Imprimir estado de dedos para debug
    up_fingers = [f for f, is_up in finger_status.items() if is_up]
    logger.info(f"Controlando servos con dedos levantados: {', '.join(up_fingers)}")
    
    # Probar controlador antes de usarlo
    if arduino_controller is None:
        logger.warning("Controlador Arduino no disponible para control por gestos")
        return False
    
    # Verificar conexión
    if not arduino_controller.is_connected():
        # Intentar reconectar una vez
        try:
            logger.info("Intentando reconectar Arduino para control por gestos")
            reconnect_success = arduino_controller.connect()
            logger.info(f"Resultado de reconexión: {reconnect_success}")
            
            if not reconnect_success:
                logger.warning("No se pudo reconectar con Arduino")
                return False
        except Exception as e:
            logger.error(f"Error en reconexión: {str(e)}")
            return False
    
    try:
        # Mapear dedos a servos específicos
        servo_mapping = {
            "thumb": 2,    # Servo en pin 2
            "index": 3,    # Servo en pin 3
            "middle": 4,   # Servo en pin 4
            "ring": 5,     # Servo en pin 5
            "pinky": 6     # Servo en pin 6
        }
        
        results = []
        for finger, servo_id in servo_mapping.items():
            angle = 180 if finger_status[finger] else 0
            logger.info(f"GESTO_DIRECTO: Servo {servo_id} ({finger}) -> {angle}°")
            
            # Usar directamente el controlador
            success, message = arduino_controller.set_servo(servo_id, angle)
            logger.info(f"Resultado: {success}, {message}")
            results.append(success)
        
        all_success = all(results)
        if all_success:
            logger.info("Todos los comandos de servo enviados correctamente")
        else:
            logger.warning("Algunos comandos de servo fallaron")
        
        return all_success
    
    except Exception as e:
        logger.error(f"Error controlando servos: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def initialize_arduino_for_video():
    """Asegurar que el controlador Arduino está correctamente inicializado para procesamiento de video"""
    global arduino_initialized, arduino_controller
    
    if arduino_initialized:
        return True
    
    try:
        # Intentar obtener el controlador directamente de run.py si aún no lo tenemos
        if arduino_controller is None:
            run_module = sys.modules.get('run')
            if run_module and hasattr(run_module, 'arduino_controller'):
                global arduino_controller
                arduino_controller = run_module.arduino_controller
                logger.info(f"Controlador obtenido durante inicialización: {arduino_controller is not None}")
        
        # Si tenemos controlador, verificar conexión
        if arduino_controller is not None:
            is_connected = arduino_controller.is_connected()
            logger.info(f"Estado de conexión durante inicialización: {is_connected}")
            
            if not is_connected:
                # Intentar conectar una vez
                try:
                    logger.info("Intentando conectar Arduino durante inicialización")
                    connect_success = arduino_controller.connect()
                    logger.info(f"Resultado de conexión inicial: {connect_success}")
                except Exception as e:
                    logger.error(f"Error conectando durante inicialización: {str(e)}")
        
        # Marcar como inicializado independientemente del resultado
        arduino_initialized = True
        return True
        
    except Exception as e:
        logger.error(f"Error inicializando Arduino para video: {str(e)}")
        arduino_initialized = True  # Marcar como inicializado para evitar reintentos
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

def process_frame(frame, hands):
    """Procesa cada fotograma usando MediaPipe para rastreo de manos."""
    global last_check_time, fingers_up, arduino_controller
    
    if frame is None:
        return None
    
    # Voltear horizontalmente para efecto espejo
    frame = cv2.flip(frame, 1)
    
    # Convertir la imagen de BGR a RGB para MediaPipe
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Procesar el fotograma con MediaPipe
    results = hands.process(rgb_frame)
    
    # Dibujar landmarks de manos en la imagen
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS,
                mp_drawing_styles.get_default_hand_landmarks_style(),
                mp_drawing_styles.get_default_hand_connections_style()
            )
            
            # Verificar dedos levantados cada 5 segundos
            current_time = time.time()
            if current_time - last_check_time >= finger_check_interval:
                current_fingers = check_fingers_raised(hand_landmarks)
                
                # Imprimir dedos levantados
                raised_fingers = [f for f, up in current_fingers.items() if up]
                logger.info(f"Fingers raised: {', '.join(raised_fingers)}")
                
                # Controlar servos Arduino basado en estado de dedos
                control_result = control_servos_with_hand(current_fingers)
                if control_result:
                    logger.info("Comandos de servo enviados correctamente")
                else:
                    logger.warning("Failed to send servo commands")
                
                last_check_time = current_time
    
    # Mostrar estado de dedos en el fotograma
    y_pos = 30
    with status_lock:
        for finger, is_up in fingers_up.items():
            status = "UP" if is_up else "DOWN"
            color = (0, 255, 0) if is_up else (0, 0, 255)
            cv2.putText(frame, f"{finger}: {status}", (10, y_pos), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            y_pos += 30
    
    # Mostrar tiempo hasta próxima verificación
    time_left = max(0, finger_check_interval - (time.time() - last_check_time))
    cv2.putText(frame, f"Next check in: {time_left:.1f}s", (10, y_pos), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    
    # Mostrar estado de conexión
    y_pos += 30
    if arduino_controller and arduino_controller.is_connected():
        cv2.putText(frame, "Arduino: Connected", (10, y_pos), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    else:
        cv2.putText(frame, "Arduino: Disconnected", (10, y_pos), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    
    # Mostrar tipo de conexión si está disponible
    if arduino_controller and arduino_controller.is_connected():
        y_pos += 30
        connection_type = "WiFi (ESP32)" if arduino_controller.use_tcp else "Serial USB"
        cv2.putText(frame, f"Connection: {connection_type}", (10, y_pos), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    
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
