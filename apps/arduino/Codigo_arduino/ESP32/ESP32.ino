#include <WiFi.h>
#include <HardwareSerial.h>

// Configuración Wi-Fi - cambia estos valores a tu red WiFi
const char* ssid = "IZZI-97F2";
const char* password = "F0AF855197F2";

// Puerto del servidor TCP
const int serverPort = 8888;
WiFiServer server(serverPort);
WiFiClient client;

// Puerto serie para comunicación con Arduino MEGA
HardwareSerial ArduinoSerial(2); // UART2 en ESP32

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
  
  // Comprobar si hay datos desde el cliente TCP
  if (client && client.connected() && client.available()) {
    String data = client.readStringUntil('\n');
    Serial.print("Recibido del cliente: ");
    Serial.println(data);
    
    // Reenviar datos al Arduino
    ArduinoSerial.println(data);
  }
  
  // Comprobar si hay datos desde el Arduino
  if (ArduinoSerial.available()) {
    String response = ArduinoSerial.readStringUntil('\n');
    Serial.print("Recibido del Arduino: ");
    Serial.println(response);
    
    // Reenviar respuesta al cliente TCP
    if (client && client.connected()) {
      client.println(response);
    }
  }
}