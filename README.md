# 🌿 Tulsi Plant Disease Detection – IoT + AI System

An end-to-end smart plant monitoring system that combines **IoT sensors (ESP32)**, **deep learning (MobileNetV2)**, and a **real-time web dashboard** to detect diseases in Tulsi (Holy Basil) plants and monitor their health.

---

## 📌 Project Overview

This project integrates:
- 🔬 **AI Disease Classifier** — Trained MobileNetV2 model that classifies Tulsi leaf diseases from images
- 📡 **ESP32 IoT Nodes** — ESP32-CAM for image capture + sensor node for soil moisture, NPK, temperature & humidity (DHT11)
- 🌐 **Web Dashboard** — Real-time monitoring dashboard built with Flask and vanilla JS
- 🔁 **Live Pipeline** — ESP32 streams sensor data and images → Flask server → AI inference → Dashboard

---

## 🩺 Disease Classes

The AI model can classify 4 conditions:

| Class | Description |
|-------|-------------|
| 🦠 **Bacterial** | Bacterial leaf spot / blight |
| 🍄 **Fungal** | Fungal infections (powdery mildew, etc.) |
| ✅ **Healthy** | Normal, healthy Tulsi plant |
| 🐛 **Pests** | Insect / pest damage |

---

## 🗂️ Project Structure

```
Tulsi/
├── classifier model/
│   ├── dataset/                  # Training images (4 classes)
│   │   ├── train/
│   │   └── train_aug/            # Augmented training data
│   ├── train_model.py            # MobileNetV2 training script
│   ├── detect_disease.py         # Real-time webcam detection
│   ├── class_labels.json         # Class index mapping
│   ├── tulsi_classifier.keras    # Trained model weights
│   └── training_history.png      # Loss/accuracy training curves
│
└── web_app/
    ├── server.py                 # Flask backend + API endpoints
    ├── requirements.txt          # Python dependencies
    ├── esp32/
    │   ├── cam_node.ino          # ESP32-CAM firmware (image streaming)
    │   └── sensor_node.ino       # ESP32 sensor node firmware
    └── static/
        ├── index.html            # Dashboard UI
        ├── style.css             # Styling
        └── app.js                # Frontend logic & real-time updates
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- Arduino IDE (for ESP32 firmware)
- ESP32-CAM + ESP32 board
- Sensors: DHT11, Soil Moisture, NPK sensor

### 1. Clone the Repository
```bash
git clone https://github.com/ayush506x/plant-disease-project-using-iot.git
cd plant-disease-project-using-iot
```

### 2. Install Python Dependencies
```bash
cd web_app
pip install -r requirements.txt
```

### 3. Train the Model (Optional — pre-trained model included)
```bash
cd "classifier model"
python train_model.py
```

### 4. Run Disease Detection (Webcam Mode)
```bash
cd "classifier model"
python detect_disease.py
```

### 5. Start the Web Dashboard
```bash
cd web_app
python server.py
```
Then open your browser at `http://localhost:5000`

### 6. Flash ESP32 Firmware
- Open `web_app/esp32/cam_node.ino` in Arduino IDE → Flash to ESP32-CAM
- Open `web_app/esp32/sensor_node.ino` → Flash to ESP32 sensor node
- Update your WiFi credentials in both `.ino` files before flashing

---

## 🧠 Model Architecture

| Property | Details |
|----------|---------|
| Base Model | MobileNetV2 (ImageNet pre-trained) |
| Input Size | 224 × 224 × 3 |
| Output Classes | 4 (bacterial, fungal, healthy, pests) |
| Training | Fine-tuned with data augmentation |
| Framework | TensorFlow / Keras |

---

## 🌡️ Sensor Data Monitored

| Sensor | Parameter |
|--------|-----------|
| DHT11 | Temperature (°C), Humidity (%) |
| Soil Moisture | Soil moisture level (%) |
| NPK Sensor | Nitrogen, Phosphorus, Potassium levels |
| ESP32-CAM | Live leaf image for AI analysis |

---

## 📊 Dashboard Features

- 📸 **Live Snapshot** — View latest image from ESP32-CAM
- 🤖 **AI Diagnosis** — Real-time disease classification with confidence score
- 🌡️ **Sensor Readings** — Live temperature, humidity, moisture & NPK gauges
- 💊 **Care Advice** — Automated treatment suggestions based on diagnosis
- 📈 **History Graphs** — Trend charts for sensor data over time

---

## 📦 Dependencies

```
tensorflow
flask
flask-cors
opencv-python
numpy
pillow
requests
```

---

## 👤 Author

**Ayush Mishra**  
GitHub: [@ayush506x](https://github.com/ayush506x)

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
