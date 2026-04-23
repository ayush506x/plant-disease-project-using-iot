/*
 =====================================================================
  Tulsi Smart Plant Monitor — ESP32 Sensor Node
 =====================================================================
  Sensors:
    - DHT11  → Temperature & Humidity
    - Capacitive Soil Moisture Sensor (analog)
    - NPK Sensor via RS-485 Modbus (UART2)

  Libraries needed (install via Arduino Library Manager):
    - DHT sensor library by Adafruit
    - Adafruit Unified Sensor
    - ArduinoJson  (v6)
    - (NPK uses raw UART — no extra library needed)

  Wiring:
    DHT11 DATA → GPIO 4
    Moisture Sensor AOUT → GPIO 34 (ADC)
    RS-485 DE/RE → GPIO 5
    RS-485 RO (receive) → GPIO 16 (UART2 RX)
    RS-485 DI (transmit) → GPIO 17 (UART2 TX)

  Sends JSON to http://<SERVER_IP>:5000/api/sensors every 10 seconds.
 =====================================================================
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

// ── CONFIG — EDIT THESE ────────────────────────────────────────────────
const char* WIFI_SSID     = "YOUR_WIFI_SSID";       // ← change me
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";   // ← change me
const char* SERVER_IP     = "192.168.1.100";         // ← your PC's local IP (printed when server starts)
const int   SERVER_PORT   = 5000;
const int   POST_INTERVAL = 10000;   // ms between sensor posts

// ── PIN DEFINITIONS ────────────────────────────────────────────────────
#define DHT_PIN       4     // DHT11 data pin
#define DHT_TYPE      DHT11
#define MOISTURE_PIN  34    // Analog moisture sensor (ADC1 channel 6)
#define RS485_DE_PIN  5     // DE/RE control pin for RS-485

// ── MOISTURE CALIBRATION ───────────────────────────────────────────────
// Measure raw ADC in dry air and fully submerged and set these:
#define MOISTURE_DRY  3500   // raw ADC when soil is dry
#define MOISTURE_WET  1200   // raw ADC when soil is wet

// ── NPK Modbus RS-485 ──────────────────────────────────────────────────
// UART2 is used for RS-485 communication with NPK sensor
// Modbus request to read N, P, K registers (standard 7-in-1 soil sensor)
static const uint8_t NPK_REQUEST[] = {0x01, 0x03, 0x00, 0x1E, 0x00, 0x03, 0x65, 0xCD};
#define NPK_REQUEST_LEN 8
#define NPK_BAUD        9600

DHT dht(DHT_PIN, DHT_TYPE);

// ── GLOBALS ────────────────────────────────────────────────────────────
float  g_temp     = 0, g_humidity = 0;
int    g_moisture = 0;
int    g_npk_n    = 0, g_npk_p = 0, g_npk_k = 0;
bool   g_npk_ok   = false;

// ── SETUP ──────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Serial.println("\n🌿 Tulsi Sensor Node Starting...");

  dht.begin();

  // RS-485 DE/RE pin
  pinMode(RS485_DE_PIN, OUTPUT);
  digitalWrite(RS485_DE_PIN, LOW); // receive mode

  // UART2 for RS-485
  Serial2.begin(NPK_BAUD, SERIAL_8N1, 16, 17);  // RX=16, TX=17

  // Connect WiFi
  connectWiFi();
}

// ── MAIN LOOP ──────────────────────────────────────────────────────────
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Reconnecting...");
    connectWiFi();
  }

  readDHT11();
  readMoisture();
  readNPK();
  postSensorData();

  delay(POST_INTERVAL);
}

// ── WIFI ───────────────────────────────────────────────────────────────
void connectWiFi() {
  Serial.printf("[WiFi] Connecting to %s", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500); Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WiFi] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[WiFi] Failed to connect. Will retry.");
  }
}

// ── DHT11 ──────────────────────────────────────────────────────────────
void readDHT11() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();  // Celsius
  if (!isnan(h) && !isnan(t)) {
    g_humidity = h;
    g_temp     = t;
    Serial.printf("[DHT11] Temp: %.1f°C  Humidity: %.1f%%\n", t, h);
  } else {
    Serial.println("[DHT11] Read failed! Check wiring.");
  }
}

// ── MOISTURE ───────────────────────────────────────────────────────────
void readMoisture() {
  int raw = analogRead(MOISTURE_PIN);
  // Map: high raw = dry, low raw = wet
  g_moisture = map(raw, MOISTURE_DRY, MOISTURE_WET, 0, 100);
  g_moisture = constrain(g_moisture, 0, 100);
  Serial.printf("[Moisture] Raw: %d  Pct: %d%%\n", raw, g_moisture);
}

// ── NPK RS-485 MODBUS ──────────────────────────────────────────────────
void readNPK() {
  // Flush incoming buffer
  while (Serial2.available()) Serial2.read();

  // Send Modbus request (set DE/RE HIGH for transmit)
  digitalWrite(RS485_DE_PIN, HIGH);
  delay(10);
  Serial2.write(NPK_REQUEST, NPK_REQUEST_LEN);
  Serial2.flush();
  delay(10);
  digitalWrite(RS485_DE_PIN, LOW);  // back to receive

  // Wait for response (up to 500ms)
  uint32_t start = millis();
  while (Serial2.available() < 11 && millis() - start < 500) delay(10);

  uint8_t buf[11] = {0};
  int len = Serial2.readBytes(buf, 11);

  if (len < 9) {
    Serial.println("[NPK] No/incomplete response. Check RS-485 wiring & baud rate.");
    g_npk_ok = false;
    return;
  }

  // Parse Modbus response:
  // Byte 0: device addr (0x01)
  // Byte 1: function code (0x03)
  // Byte 2: byte count (0x06)
  // Bytes 3-4: N (high byte first)
  // Bytes 5-6: P
  // Bytes 7-8: K
  if (buf[0] == 0x01 && buf[1] == 0x03 && buf[2] == 0x06) {
    g_npk_n = (buf[3] << 8) | buf[4];
    g_npk_p = (buf[5] << 8) | buf[6];
    g_npk_k = (buf[7] << 8) | buf[8];
    g_npk_ok = true;
    Serial.printf("[NPK] N=%d  P=%d  K=%d  mg/kg\n", g_npk_n, g_npk_p, g_npk_k);
  } else {
    Serial.printf("[NPK] Bad Modbus response. First bytes: %02X %02X %02X\n", buf[0], buf[1], buf[2]);
    g_npk_ok = false;
  }
}

// ── HTTP POST ──────────────────────────────────────────────────────────
void postSensorData() {
  if (WiFi.status() != WL_CONNECTED) return;

  String url = "http://" + String(SERVER_IP) + ":" + SERVER_PORT + "/api/sensors";

  StaticJsonDocument<256> doc;
  doc["temperature"] = round(g_temp * 10) / 10.0;
  doc["humidity"]    = round(g_humidity * 10) / 10.0;
  doc["moisture"]    = g_moisture;
  doc["npk_n"]       = g_npk_ok ? g_npk_n : (int)NULL;
  doc["npk_p"]       = g_npk_ok ? g_npk_p : (int)NULL;
  doc["npk_k"]       = g_npk_ok ? g_npk_k : (int)NULL;

  String payload;
  serializeJson(doc, payload);

  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(payload);

  if (code == 200) {
    Serial.printf("[HTTP] Sensor data sent OK (HTTP %d)\n", code);
  } else {
    Serial.printf("[HTTP] POST failed: %d  URL: %s\n", code, url.c_str());
  }
  http.end();
}
