import cv2
import mediapipe as mp
import time
import threading
from apps.arduino.controller import arduino_controller, init_arduino

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

# Ensure Arduino controller is initialized
if arduino_controller is None:
    init_arduino()

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
    if not arduino_controller or not arduino_controller.is_connected():
        print("Arduino not connected, attempting to connect...")
        if arduino_controller:
            arduino_controller.connect()
            if not arduino_controller.is_connected():
                print("Failed to connect to Arduino")
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
        
        # Set servo angles based on finger status (0° if down, 180° if up)
        for finger, servo_id in servo_mapping.items():
            angle = 180 if finger_status[finger] else 0
            success, message = arduino_controller.set_servo(servo_id, angle)
            if not success:
                print(f"Failed to set servo for {finger}: {message}")
        
        return True
    
    except Exception as e:
        print(f"Error controlling servos: {str(e)}")
        return False

def process_frame(frame, hands):
    """Process each frame using MediaPipe for hand tracking."""
    global last_check_time, fingers_up
    
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
                print(f"Fingers raised: {', '.join([f for f, up in current_fingers.items() if up])}")
                
                # Control Arduino servos based on finger status
                control_result = control_servos_with_hand(current_fingers)
                if control_result:
                    print("Successfully sent servo commands")
                else:
                    print("Failed to send servo commands")
                
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
    
    return frame

def gen_video_feed(camera_id):
    """Generate video feed with hand tracking for the specified camera."""
    cap = cv2.VideoCapture(camera_id)
    
    # Create a new instance of MediaPipe Hands for this camera
    hands = mp_hands.Hands(
        model_complexity=0,  # 0 for fastest performance, 1 for better accuracy
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        max_num_hands=1
    )
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        # Process each frame with hand tracking
        frame = process_frame(frame, hands)
        
        # Encode the image to JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        
        # Return the frame
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')