import cv2
import mediapipe as mp
import time
import threading
import logging
from apps.arduino.controller import arduino_controller, init_arduino

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

# Modificación a la función initialize_arduino_for_video en video_processing.py

def initialize_arduino_for_video():
    """Ensure Arduino controller is properly initialized for video processing"""
    global arduino_initialized, arduino_controller
    
    # Si ya está inicializado, no hacer nada
    if arduino_initialized:
        return True
        
    try:
        # Importante: VERIFICAR si el controlador ya existe y ESTÁ CONECTADO
        if arduino_controller is not None and arduino_controller.is_connected():
            logger.info("Arduino ya está conectado, usando conexión existente")
            arduino_initialized = True
            return True
            
        # Si existe pero no está conectado, intentar reconectar con la configuración actual
        if arduino_controller is not None:
            logger.info("Arduino controller existe pero no está conectado, intentando reconectar")
            # Intentar reconectar con la configuración actual
            if arduino_controller.connect():
                arduino_initialized = True
                logger.info(f"Reconectado exitosamente a Arduino: {arduino_controller.use_tcp}")
                return True
            
        # Sólo si no hay un controlador o falló la reconexión, inicializar uno nuevo
        if arduino_controller is None:
            # Verificar en flask.current_app si hay información sobre conexiones WebSocket
            try:
                from flask import current_app
                if hasattr(current_app, 'config') and 'ARDUINO_CONNECTION' in current_app.config:
                    connection_info = current_app.config['ARDUINO_CONNECTION']
                    logger.info(f"Usando información de conexión existente: {connection_info}")
                    
                    if connection_info.get('is_connected', False):
                        if connection_info.get('connection_type') == 'wifi':
                            # Usar conexión WiFi
                            arduino_controller = init_arduino(
                                host=connection_info.get('host'),
                                tcp_port=connection_info.get('port', 8888),
                                use_tcp=True,
                                connect_now=True
                            )
                            logger.info(f"Inicializado con conexión WiFi: {connection_info.get('host')}")
                        else:
                            # Usar conexión serial
                            arduino_controller = init_arduino(
                                serial_port=connection_info.get('serial_port', 'COM12'),
                                connect_now=True
                            )
                            logger.info(f"Inicializado con conexión serial: {connection_info.get('serial_port')}")
                        
                        if arduino_controller and arduino_controller.is_connected():
                            arduino_initialized = True
                            return True
            except Exception as e:
                logger.warning(f"No se pudo obtener información de conexión desde Flask: {str(e)}")
            
            # Si no hay información de conexión previa, usar detección automática
            logger.info("No hay información de conexión previa, usando detección automática")
            from serial.tools.list_ports import comports
            available_ports = [p.device for p in comports()]
            
            if not available_ports:
                logger.error("No se encontraron puertos seriales disponibles")
                return False
            
            # Usar el primer puerto disponible
            port_to_use = available_ports[0]
            logger.info(f"Usando puerto serial detectado automáticamente: {port_to_use}")
            
            arduino_controller = init_arduino(
                serial_port=port_to_use,
                connect_now=False  # Cambiado a False para no conectar automáticamente
            )
        
        # En este punto, solo conectar si el usuario lo ha solicitado explícitamente
        # a través de la interfaz WebSocket o si no hay interfaz WebSocket disponible
        if arduino_controller and not arduino_controller.is_connected():
            try:
                from flask import current_app
                if not hasattr(current_app, 'config') or 'SOCKETIO' not in current_app.config:
                    # Si no hay SocketIO, conectar directamente
                    logger.info("No hay WebSocket, conectando directamente")
                    arduino_controller.connect()
                else:
                    # Si hay SocketIO, no conectar automáticamente
                    logger.info("WebSocket disponible, no conectando automáticamente")
            except Exception:
                # Si hay algún error, intentar conectar como último recurso
                arduino_controller.connect()
        
        arduino_initialized = True
        return arduino_controller.is_connected()
        
    except Exception as e:
        logger.error(f"Error initializing Arduino for video: {str(e)}")
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
    """Control Arduino servos based on hand finger positions"""
    global arduino_controller
    
    # Only attempt to initialize once
    if not arduino_initialized:
        initialize_arduino_for_video()
    
    # Skip if no Arduino controller or not connected
    if not arduino_controller or not arduino_controller.is_connected():
        logger.warning("Arduino not connected for servo control")
        return False
    
    try:
        # Map fingers to specific servos - adjust servo IDs as needed for your setup
        servo_mapping = {
            "thumb": 2,    # Servo on pin 2
            "index": 3,    # Servo on pin 3
            "middle": 4,   # Servo on pin 4
            "ring": 5,     # Servo on pin 5
            "pinky": 6     # Servo on pin 6
        }
        
        results = []
        
        # Set servo angles based on finger status (0° if down, 180° if up)
        for finger, servo_id in servo_mapping.items():
            angle = 180 if finger_status[finger] else 0
            success, message = arduino_controller.set_servo(servo_id, angle)
            
            if not success:
                logger.error(f"Failed to set servo for {finger}: {message}")
                results.append(False)
            else:
                logger.debug(f"Set servo {servo_id} ({finger}) to {angle}°")
                results.append(True)
        
        return all(results)  # Return True only if all servos were set successfully
    
    except Exception as e:
        logger.error(f"Error controlling servos: {str(e)}")
        return False

def process_frame(frame, hands):
    """Process each frame using MediaPipe for hand tracking."""
    global last_check_time, fingers_up
    
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
    """Create a frame with error message when camera is not available"""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(frame, "Camera Error", (200, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(frame, message, (100, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    return frame

# Ensure numpy is imported
import numpy as np