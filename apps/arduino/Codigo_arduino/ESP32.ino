#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>

const char* ssid = "_JIMENEZ_";
const char* password = "7163350391";

WebServer server(80);

void setup() {
  Serial.begin(9600);  // Mismo baudrate que usa tu Arduino Mega
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
  
  // Manejador para solicitudes OPTIONS (CORS)
  server.on("/set_servo", HTTP_OPTIONS, []() {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");
    server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
    server.send(204); // No content
  });
  
  server.on("/set_servo", HTTP_POST, handleServo);
  server.on("/test", HTTP_GET, handleTest);
  
  server.begin();
  
  Serial.println("ESP32 IP: " + WiFi.localIP().toString());
}

void loop() {
  server.handleClient();
}

void handleTest() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "text/plain", "ESP32 esta en linea");
}

void handleServo() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");
  server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
  
  if (server.hasArg("plain")) {
    String body = server.arg("plain");
    DynamicJsonDocument doc(1024);
    
    DeserializationError error = deserializeJson(doc, body);
    if (!error) {
      int servo_id = doc["servo_id"];  // Mantiene el mismo formato que usa tu aplicación
      int angle = doc["angle"];
      
      // Formar el mismo formato de comando que espera tu Arduino Mega
      String command = String(servo_id) + "," + String(angle) + "\n";
      
      // Enviar al Arduino Mega
      Serial.print(command);
      
      server.send(200, "application/json", "{\"status\":\"success\",\"message\":\"Comando enviado\"}");
    } else {
      server.send(400, "application/json", "{\"status\":\"error\",\"message\":\"Invalid JSON\"}");
    }
  } else {
    server.send(400, "application/json", "{\"status\":\"error\",\"message\":\"No data received\"}");
  }
}