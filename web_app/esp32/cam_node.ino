/*
 =====================================================================
  Tulsi Smart Plant Monitor — ESP32-CAM Node
 =====================================================================
  Board: AI-Thinker ESP32-CAM
  Captures a JPEG image and POSTs it to the Flask server for
  AI disease classification using MobileNetV2.

  Libraries needed (install via Arduino Library Manager / Board Manager):
    - ESP32 Arduino Core (by Espressif)  ← must have "AI Thinker ESP32-CAM" board

  No extra libraries needed — camera & WiFi are built-in.

  IMPORTANT FLASHING NOTE:
    - Connect GPIO 0 to GND before powering on to enter flash mode
    - After flashing, disconnect GPIO 0 from GND and press reset

  Sends JPEG bytes to http://<SERVER_IP>:5000/api/analyze every 30 seconds.
 =====================================================================
*/

#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>

// ── CONFIG — EDIT THESE ────────────────────────────────────────────────
const char* WIFI_SSID     = "YOUR_WIFI_SSID";       // ← change me
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";   // ← change me
const char* SERVER_IP     = "192.168.1.100";         // ← your PC's local IP
const int   SERVER_PORT   = 5000;
const int   CAPTURE_INTERVAL = 30000;  // ms between captures

// ── AI-THINKER ESP32-CAM PIN MAP ──────────────────────────────────────
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ── SETUP ──────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Serial.println("\n🌿 Tulsi ESP32-CAM Node Starting...");

  initCamera();
  connectWiFi();
}

// ── MAIN LOOP ──────────────────────────────────────────────────────────
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Reconnecting...");
    connectWiFi();
  }

  captureAndPost();
  delay(CAPTURE_INTERVAL);
}

// ── CAMERA INIT ────────────────────────────────────────────────────────
void initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // Use higher quality if PSRAM available
  if (psramFound()) {
    config.frame_size   = FRAMESIZE_VGA;   // 640x480
    config.jpeg_quality = 12;              // 0-63 lower = higher quality
    config.fb_count     = 2;
  } else {
    config.frame_size   = FRAMESIZE_QVGA;  // 320x240
    config.jpeg_quality = 20;
    config.fb_count     = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[CAM] Init failed: 0x%x\n", err);
    Serial.println("[CAM] Check wiring. Restarting in 5s...");
    delay(5000);
    ESP.restart();
  }

  // Apply camera settings for better image quality
  sensor_t* s = esp_camera_sensor_get();
  s->set_brightness(s, 0);     // -2 to 2
  s->set_contrast(s, 0);       // -2 to 2
  s->set_saturation(s, 0);     // -2 to 2
  s->set_sharpness(s, 0);      // -2 to 2
  s->set_whitebal(s, 1);       // auto white balance
  s->set_gain_ctrl(s, 1);      // auto gain
  s->set_exposure_ctrl(s, 1);  // auto exposure
  s->set_hmirror(s, 0);        // mirror
  s->set_vflip(s, 0);          // flip

  Serial.println("[CAM] Camera initialized OK");
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
    Serial.println("\n[WiFi] Connection failed. Will retry.");
  }
}

// ── CAPTURE & POST ─────────────────────────────────────────────────────
void captureAndPost() {
  // Capture frame
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[CAM] Capture failed. Retrying next cycle.");
    return;
  }

  Serial.printf("[CAM] Captured %d bytes (JPEG %dx%d)\n",
                fb->len, fb->width, fb->height);

  // POST raw JPEG bytes to server
  String url = "http://" + String(SERVER_IP) + ":" + SERVER_PORT + "/api/analyze";

  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/octet-stream");
  http.setTimeout(15000);  // 15 second timeout for large images

  int code = http.POST(fb->buf, fb->len);

  if (code == 200) {
    String response = http.getString();
    Serial.printf("[AI] Server response: %s\n", response.c_str());
    // Parse basic result from JSON
    int labelStart = response.indexOf("\"label\":\"") + 9;
    int labelEnd   = response.indexOf("\"", labelStart);
    int confStart  = response.indexOf("\"confidence\":") + 13;
    int confEnd    = response.indexOf(",", confStart);
    if (labelStart > 9) {
      String label = response.substring(labelStart, labelEnd);
      String conf  = response.substring(confStart, confEnd);
      Serial.printf("[AI] ► %s (%.1s%%)\n", label.c_str(), conf.c_str());
    }
  } else {
    Serial.printf("[HTTP] POST failed: HTTP %d\n", code);
  }

  http.end();
  esp_camera_fb_return(fb);  // IMPORTANT: return frame buffer
}
