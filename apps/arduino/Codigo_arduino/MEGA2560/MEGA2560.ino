#include <Servo.h>

//192.168.0.21

Servo servos[30];  // Array para 30 servos
int servo_pins[30] = {2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39};

// Variables para watchdog y sistema de timeout
unsigned long lastCommandTime = 0;
const unsigned long WATCHDOG_TIMEOUT = 30000; // 30 segundos

void setup() {
    Serial3.begin(9600);  // Inicializar comunicación Serial3
    Serial3.setTimeout(50); // Reducir el timeout de lectura a 50ms
    delay(1000);  // Esperar 1 segundo para inicializar - reducido de 2s

    // Asociar los pines con los servos
    for (int i = 0; i < 30; i++) {
        servos[i].attach(servo_pins[i]);
        servos[i].write(0);  // Inicializar servos en 90°
    }

    Serial3.println("Listo para recibir comandos.");
    lastCommandTime = millis();
}

void loop() {
    // Implementar un watchdog básico
    if (millis() - lastCommandTime > WATCHDOG_TIMEOUT) {
        // Reiniciar comunicación Serial3 si hay un largo periodo sin comandos
        Serial3.end();
        delay(100);
        Serial3.begin(9600);
        Serial3.setTimeout(50);
        Serial3.println("Comunicación reiniciada por watchdog");
        lastCommandTime = millis();
    }
  
    if (Serial3.available() > 0) {
        String command = Serial3.readStringUntil('\n');  // Leer comando
        command.trim();
        lastCommandTime = millis(); // Actualizar tiempo del último comando

        // Procesar comando de inmediato
        int commaIndex = command.indexOf(',');  // Buscar la coma que separa los valores
        if (commaIndex > 0) {
            int servo_id = command.substring(0, commaIndex).toInt();
            int angle = command.substring(commaIndex + 1).toInt();

            if (servo_id >= 2 && servo_id <= 31 && angle >= 0 && angle <= 180) {
                int servo_index = servo_id - 2;  // Convertir pin a índice en array
                
                // Verificar que el servo existe antes de intentar moverlo
                if (servo_index >= 0 && servo_index < 30) {
                    servos[servo_index].write(angle);
                    Serial3.print("Servo ");
                    Serial3.print(servo_id);
                    Serial3.print(" ajustado a ");
                    Serial3.print(angle);
                    Serial3.println("°");
                } else {
                    Serial3.print("Error: índice de servo fuera de rango: ");
                    Serial3.println(servo_index);
                }
            } else {
                Serial3.print("Error: valores fuera de rango. Servo ID debe ser 2-31, ángulo 0-180. Recibido: ");
                Serial3.print(servo_id);
                Serial3.print(",");
                Serial3.println(angle);
            }
        } else {
            Serial3.print("Comando inválido: ");
            Serial3.println(command);
        }
        
        // Limpiar buffer Serial3 de entrada
        while (Serial3.available() > 0) {
            Serial3.read();
        }
    }
}