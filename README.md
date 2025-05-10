# 🤖 Scarlet Witch Project (Robot Control System)

> Control servomotors with precision through an intuitive web interface. Power up your robotics projects with direct control, programmable sequences, and hand gesture recognition!

![GitHub](https://img.shields.io/badge/https%3A%2F%2Fgithub.com%2FChelqq%2FScarlet-witch-project%2Fblob%2FW_ESP32_compat%2F)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/flask-2.0+-green.svg)
![Arduino](https://img.shields.io/badge/arduinoMEGA-compatible-teal.svg)

### @hairygael thank u! <- owner of Inmoov project

<div align="center">
  <img src="https://inmoov.fr/wp-content/uploads/2015/06/referencesv2.jpg" alt="Robot Control System" width="800">
</div>

## ✨ Features

- **🎮 Direct Servo Control** - Individually control up to 30 servomotors with intuitive sliders
- **⏱️ Programmable Sequences** - Create, save, and execute custom movement sequences
- **👋 Gesture Control** - Control servos with hand gestures through computer vision
- **🔌 Flexible Connectivity** - Direct serial connection or WiFi through ESP32
- **🔐 User Authentication** - Secure your robot with login and OAuth GitHub support
- **📱 Responsive Interface** - Beautiful Bootstrap-based dashboard that works on desktop and mobile
- **💾 Persistent Storage** - Save your sequences for future use

<div align="center">
  <img src="https://www.ez-robot.com/uploads/1/2/6/9/126941806/s237119158784252105_p88_i2_w5184.jpeg?width=2560" alt="Control Interface" width="700">
</div>

## 🛠️ Architecture

The system is built with a modern architecture that connects your web browser to Arduino hardware through a Flask backend:

```
Web Browser ↔️ Flask Application ↔️ Arduino Controller ↔️ Servomotors
                    ↕️
                 Database
```

### Hardware Supported:
- Arduino MEGA 2560
- ESP32 (for WiFi connectivity)
- Standard servo motors (up to 30)

## 📋 Requirements

### Software
- Python 3.10.0+
- Flask and dependencies (see requirements.txt)
- Arduino IDE
- Modern web browser

### Hardware
- Arduino MEGA 2560 or compatible
- ESP32 (optional, for WiFi connectivity)
- Servo motors
- Computer with webcam (for gesture control)

## 🚀 Installation

### Backend Setup

1. Clone this repository:
```bash
git clone https://github.com/Chelqq/Scarlet-witch-project.git
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
# Create a .env file with:
DEBUG=True
SECRET_KEY=your-secret-key
GITHUB_ID=your-github-oauth-id
GITHUB_SECRET=your-github-oauth-secret
```

### Arduino Setup

1. Upload the appropriate sketch to your Arduino:
   - For direct control: Upload MEGA2560.ino to your Arduino MEGA
   - For WiFi control: Upload ESP32.ino to your ESP32

2. Connect your servos to the Arduino:
   - Servos should be connected to pins 2-31 on the Arduino MEGA
   - Power supply should be adequate for the number of servos

<div align="center">
  <img src="https://inmoov.fr/wp-content/uploads/2013/12/Map-ConnectionsV2-scaled.jpg" alt="Hardware Setup" width="600">
</div>

## 🎯 Usage

1. Start the Flask application:
```bash
python run.py
```

2. Open your browser and navigate to `http://localhost:5000`

3. Log in with your credentials or via GitHub

4. Connect to your Arduino:
   - For direct connection: Select the COM port (e.g., COM12)
   - For WiFi connection: Enter the ESP32's IP address

5. Control your servos:
   - Use the sliders to directly control individual servos
   - Create and run sequences for complex movements
   - Enable your webcam for hand gesture control

## 🔍 Detailed Architecture

The system consists of the following components:

1. **Web Interface**: Built with Flask, Jinja2 templates, and Bootstrap
2. **Authentication System**: User management with Flask-Login and GitHub OAuth
3. **Arduino Controller**: Python class that manages communication with hardware
4. **Video Processing**: MediaPipe-based hand tracking for gesture control
5. **Database**: SQLAlchemy for user and sequence storage

<div align="center">
  <img src="https://github.com/Chelqq/Scarlet-witch-project/blob/43e2d2930f13a3c4230d24b2abaeb09419d90bd9/Diagramas/Arquitectura%20de%20la%20Aplicaci%C3%B3n.drawio.png" alt="System Architecture" width="700">
</div>

## 📊 Performance

The system is designed for:
- **Low latency**: Commands are sent to Arduino with minimal delay
- **Reliable communication**: Error handling and automatic reconnection
- **Smooth interface**: Reactive UI that provides immediate feedback

## 🧩 API Endpoints

The REST API provides the following endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/arduino/status` | GET | Get connection status |
| `/arduino/connect` | POST | Connect to Arduino |
| `/arduino/set_servo` | POST | Control a specific servo |
| `/arduino/reset_servos` | POST | Reset all servos to 0° |
| `/arduino/sequences` | GET | Get all saved sequences |
| `/arduino/sequences` | POST | Save a new sequence |
| `/arduino/run_sequence` | POST | Execute a sequence |
| `/video_feed_0` | GET | Access webcam 0 stream |
| `/video_feed_1` | GET | Access webcam 1 stream |

## ⚙️ Configuration

The system can be configured through:
- Environment variables
- `config.py` file
- Web interface settings

## 🤝 Contributing

Contributions are welcome! 
Get in touch: 
 
 `send a DM to the owner of the repo`

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgements

- [Gael Langevin](https://inmoov.fr/) - Creator of InMoov Robot
- [MediaPipe](https://mediapipe.dev/) - Hand tracking solution
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [Bootstrap](https://getbootstrap.com/) - Frontend framework
- [Arduino](https://www.arduino.cc/) - Hardware platform

---

<div align="center">

  <p>Made with ❤️ by  Chris CJ</p>
</div>