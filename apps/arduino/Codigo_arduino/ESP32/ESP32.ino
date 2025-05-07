#include <WiFi.h>
#include <HardwareSerial.h>

// Configuración Wi-Fi - cambia estos valores a tu red WiFi
const char* ssid = "IZZI-97F2";
const char* password = "F0AF855197F2";
//192.168.0.21
// Puerto del servidor TCP
const int serverPort = 8888;
WiFiServer server(serverPort);
WiFiClient client;

// Puerto serie para comunicación con Arduino MEGA
HardwareSerial ArduinoSerial(2); // UART2 en ESP32

// Variables para controlar la sincronización de comandos
bool awaitingResponse = false;
String lastCommand = "";
unsigned long commandSentTime = 0;
const unsigned long RESPONSE_TIMEOUT = 500; // 500ms timeout para esperar respuesta

void setup() {
  // Iniciar puerto serie de depuración
  Serial.begin(115200);
  delay(10);
  
  // Iniciar puerto serie para comunicación con Arduino MEGA
  ArduinoSerial.begin(9600, SERIAL_8N1, 16, 17); // RX=16, TX=17 (puedes cambiar a los pines que uses)
  
  // Conectar a WiFi
  Serial.println();
  Serial.print("Conectando a ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("");
  Serial.println("WiFi conectado");
  Serial.println("Dirección IP: ");
  Serial.println(WiFi.localIP());
  
  // Iniciar servidor TCP
  server.begin();
  Serial.println("Servidor TCP iniciado");
}

void loop() {
  // Comprobar si hay clientes nuevos
  if (!client || !client.connected()) {
    client = server.available();
    if (client) {
      Serial.println("Nuevo cliente conectado");
      client.println("Conectado al puente ESP32-Arduino");
    }
  }
  
  // Si estamos esperando respuesta, comprobar si ha llegado o si ha vencido el timeout
  if (awaitingResponse) {
    if (ArduinoSerial.available()) {
      String response = ArduinoSerial.readStringUntil('\n');
      response.trim();
      Serial.print("Recibido del Arduino: ");
      Serial.println(response);
      
      // Reenviar respuesta al cliente TCP
      if (client && client.connected()) {
        client.println(response);
      }
      
      // Marcar que ya no estamos esperando respuesta
      awaitingResponse = false;
    } else if (millis() - commandSentTime > RESPONSE_TIMEOUT) {
      // Si ha pasado el timeout sin respuesta
      Serial.println("Timeout esperando respuesta del Arduino");
      if (client && client.connected()) {
        client.println("ERROR: Timeout esperando respuesta del Arduino");
      }
      awaitingResponse = false;
    }
  }
  // Solo procesar nuevos comandos si no estamos esperando respuesta
  else if (client && client.connected() && client.available()) {
    String data = client.readStringUntil('\n');
    data.trim();
    Serial.print("Recibido del cliente: ");
    Serial.println(data);
    
    // Limpiar buffer serial antes de enviar nuevo comando
    while (ArduinoSerial.available()) {
      ArduinoSerial.read();
    }
    
    // Reenviar datos al Arduino
    ArduinoSerial.println(data);
    
    // Guardar información del comando enviado
    lastCommand = data;
    commandSentTime = millis();
    awaitingResponse = true;
  }
}