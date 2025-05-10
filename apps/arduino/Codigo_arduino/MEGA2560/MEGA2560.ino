#include <Servo.h>

//192.168.0.21  en IZZI CASA
//192.168.161.85 en HOTSPOT

Servo servos[20];  // Array para 20 servos (excluimos pines 14 y 15)
int servo_pins[20] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 16, 17, 18, 19, 20, 21};

// Variables para watchdog y sistema de timeout
unsigned long lastCommandTime = 0;
const unsigned long WATCHDOG_TIMEOUT = 30000; // 30 segundos

void setup() {
    Serial3.begin(9600);  // Inicializar comunicación Serial3
    Serial3.setTimeout(50); // Reducir el timeout de lectura a 50ms
    delay(1000);  // Esperar 1 segundo para inicializar - reducido de 2s

    // Asociar los pines con los servos
    for (int i = 0; i < 20; i++) {
        servos[i].attach(servo_pins[i]);
        servos[i].write(0);  // Inicializar servos en 0°
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

            // Validar rango de servo_id (0-13 y 16-21) y ángulo (0-180)
            if (((servo_id >= 0 && servo_id <= 13) || (servo_id >= 16 && servo_id <= 21)) && angle >= 0 && angle <= 180) {
                int servo_index;
                if (servo_id <= 13) {
                    servo_index = servo_id; // Para pines 0-13
                } else {
                    servo_index = servo_id - 2; // Para pines 16-21, ajustar por los pines 14-15 saltados
                }
                
                // Verificar que el servo existe antes de intentar moverlo
                if (servo_index >= 0 && servo_index < 20) {
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
                Serial3.print("Error: valores fuera de rango. Servo ID debe ser 0-13 o 16-21, ángulo 0-180. Recibido: ");
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