# Arduino Servo Control Web Interface

A Flask web application that provides a user interface to control up to 30 servo motors connected to an Arduino MEGA 2560.

## Features

- Web-based UI for controlling multiple servo motors
- Real-time servo position control with sliders
- Quick preset positions (0°, 90°, 180°)
- Reset all servos to center position (90°)
- Connection management for Arduino
- User authentication system with GitHub OAuth support

## Technical Overview

- **Backend**: Flask with SQLAlchemy
- **Frontend**: JavaScript/jQuery with Bootstrap
- **Communication**: Serial connection to Arduino
- **Security**: Flask-Login for authentication

## Setup Instructions

1. Upload the Arduino sketch (`Codigo_arduino.ino`) to your Arduino MEGA 2560
2. Install Python requirements:
   ```
   pip install flask flask-login flask-sqlalchemy flask-dance pyserial
   ```
3. Configure environment variables (optional):
   ```
   ARDUINO_PORT=COM12  # Default port for Arduino
   GITHUB_ID=your_github_id  # For GitHub OAuth
   GITHUB_SECRET=your_github_secret  # For GitHub OAuth
   ```
4. Run the application:
   ```
   python app.py
   ```

## Arduino Connection

The system communicates with the Arduino through serial commands in the format:
```
servo_id,angle
```

Where:
- `servo_id` is the pin number (2-31)
- `angle` is the desired position (0-180 degrees)

## System Architecture

- `apps/arduino/controller.py`: Handles communication with Arduino
- `apps/arduino/routes.py`: Flask routes for Arduino control
- `apps/authentication`: User authentication system
- `apps/home`: Main application routes
- `apps/templates`: HTML templates for the UI

## Troubleshooting

If you experience connection issues:
1. Verify the correct COM port is selected
2. Ensure the Arduino is properly connected and powered
3. Check that the correct Arduino sketch is uploaded
4. Restart the application

TREE of apps/
   # Descripción de la Estructura de Archivos

Este documento describe la estructura de carpetas y archivos dentro del proyecto.

## Estructura de Directorios

```
C:.
├───arduino
│   └───Codigo_arduino
├───authentication
├───home
├───static
│   └───assets
│       ├───css
│       ├───demo
│       ├───fonts
│       ├───img
│       ├───js
│       │   ├───core
│       │   └───plugins
│       └───scss
│           └───black-dashboard
│               ├───bootstrap
│               │   ├───mixins
│               │   ├───utilities
│               │   └───vendor
│               ├───custom
│               │   ├───cards
│               │   ├───mixins
│               │   ├───utilities
│               │   └───vendor
│               └───plugins
└───templates
    ├───accounts
    ├───home
    ├───includes
    └───layouts
```