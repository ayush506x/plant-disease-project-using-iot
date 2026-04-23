"""
Tulsi Smart Plant Monitor - Flask Backend
==========================================
Receives sensor data from ESP32 and plant images from ESP32-CAM,
runs AI disease inference, and pushes updates to browser via WebSocket.

Run with:  python server.py

Endpoints:
    POST /api/sensors        - ESP32 sends DHT11 + moisture + NPK JSON
    POST /api/analyze        - ESP32-CAM sends JPEG bytes for AI inference
    POST /api/analyze_upload - Browser manual upload for testing
    GET  /api/snapshot       - Latest plant image (JPEG)
    GET  /api/status         - Latest state as JSON
    GET  /                   - Serves dashboard
"""

import sys
# Force UTF-8 on Windows so emoji in print() doesn't crash
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import os, json, base64, threading
from pathlib import Path
from datetime import datetime

import numpy as np
import cv2

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# ── CONFIG ────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
MODEL_DIR     = BASE_DIR.parent / "classifier model"
MODEL_PATH    = MODEL_DIR / "tulsi_classifier.keras"
LABELS_PATH   = MODEL_DIR / "class_labels.json"
STATIC_DIR    = BASE_DIR / "static"
SNAPSHOT_PATH = BASE_DIR / "latest_snapshot.jpg"
IMG_SIZE      = (224, 224)

CLASS_ADVICE = {
    "healthy":   "Plant looks healthy! Keep up the good care. ✅",
    "bacterial": "⚠️ Bacterial infection detected. Apply bactericide and remove infected leaves.",
    "fungal":    "⚠️ Fungal disease detected. Apply fungicide and improve air circulation.",
    "pests":     "⚠️ Pest damage detected. Inspect the plant and apply appropriate pesticide.",
}
CLASS_EMOJI = {
    "healthy": "🌿", "bacterial": "🦠", "fungal": "🍄", "pests": "🐛",
}

# ── FLASK APP ─────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")
app.config["SECRET_KEY"] = "tulsi-monitor-2024"
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ── IN-MEMORY STATE ───────────────────────────────────────────────────────────
state = {
    "sensors": {
        "temperature": None, "humidity": None, "moisture": None,
        "npk_n": None, "npk_p": None, "npk_k": None,
        "sensor_timestamp": None,
    },
    "ai": {
        "label": None, "confidence": None, "advice": None,
        "emoji": None, "all_probs": {}, "ai_timestamp": None,
    },
    "has_snapshot": SNAPSHOT_PATH.exists(),
}

model = None
label_map = None
model_lock = threading.Lock()

# ── MODEL LOADING ─────────────────────────────────────────────────────────────
def load_model():
    global model, label_map
    if not MODEL_PATH.exists():
        print(f"[WARNING] Model not found at {MODEL_PATH}. AI disabled.")
        print("          Run 'python train_model.py' in 'classifier model/' first.")
        return False
    if not LABELS_PATH.exists():
        print("[WARNING] class_labels.json not found. AI disabled.")
        return False
    print("[*] Loading Tulsi disease classifier ...")
    import tensorflow as tf
    with model_lock:
        model = tf.keras.models.load_model(str(MODEL_PATH))
        with open(LABELS_PATH) as f:
            raw = json.load(f)
        label_map = {int(k): v for k, v in raw.items()}
    print(f"[*] Model loaded. Classes: {list(label_map.values())}")
    return True

# ── INFERENCE ─────────────────────────────────────────────────────────────────
def run_inference(img_bytes: bytes) -> dict:
    if model is None or label_map is None:
        return {"error": "Model not loaded. Run train_model.py first."}
    nparr = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        return {"error": "Could not decode image."}
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = cv2.resize(frame_rgb, IMG_SIZE).astype("float32") / 255.0
    img = np.expand_dims(img, axis=0)
    with model_lock:
        preds = model.predict(img, verbose=0)[0]
    idx  = int(np.argmax(preds))
    lbl  = label_map[idx]
    conf = float(preds[idx]) * 100
    return {
        "label":        lbl,
        "confidence":   round(conf, 1),
        "advice":       CLASS_ADVICE.get(lbl, ""),
        "emoji":        CLASS_EMOJI.get(lbl, "🌱"),
        "all_probs":    {label_map[i]: round(float(preds[i]) * 100, 1) for i in range(len(preds))},
        "ai_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

# ── ROUTES ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(str(STATIC_DIR), "index.html")

@app.route("/api/status")
def api_status():
    return jsonify({
        "sensors": state["sensors"], "ai": state["ai"],
        "has_snapshot": state["has_snapshot"], "model_loaded": model is not None,
    })

@app.route("/api/sensors", methods=["POST"])
def api_sensors():
    """ESP32 sensor node posts readings here."""
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    state["sensors"].update({
        "temperature":      data.get("temperature"),
        "humidity":         data.get("humidity"),
        "moisture":         data.get("moisture"),
        "npk_n":            data.get("npk_n"),
        "npk_p":            data.get("npk_p"),
        "npk_k":            data.get("npk_k"),
        "sensor_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    socketio.emit("sensor_update", state["sensors"])
    print(f"[SENSOR] T={data.get('temperature')}°C H={data.get('humidity')}% M={data.get('moisture')}% NPK={data.get('npk_n')}/{data.get('npk_p')}/{data.get('npk_k')}")
    return jsonify({"ok": True})

def _process_image(img_bytes):
    with open(SNAPSHOT_PATH, "wb") as f:
        f.write(img_bytes)
    state["has_snapshot"] = True
    result = run_inference(img_bytes)
    if "error" not in result:
        state["ai"].update(result)
        socketio.emit("ai_result", {**result, "snapshot_url": "/api/snapshot"})
        print(f"[AI] {result['label']} ({result['confidence']:.1f}%)")
    socketio.emit("snapshot_update", {"snapshot_url": "/api/snapshot"})
    return result

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """ESP32-CAM posts raw JPEG or base64 JSON here."""
    if request.content_type and "json" in request.content_type:
        data = request.get_json(force=True, silent=True) or {}
        img_bytes = base64.b64decode(data.get("image_b64", ""))
    else:
        img_bytes = request.data
    if not img_bytes:
        return jsonify({"error": "No image data"}), 400
    return jsonify(_process_image(img_bytes))

@app.route("/api/analyze_upload", methods=["POST"])
def api_analyze_upload():
    """Browser manual upload for testing (multipart form, field='image')."""
    if "image" not in request.files:
        return jsonify({"error": "No image field"}), 400
    img_bytes = request.files["image"].read()
    return jsonify(_process_image(img_bytes))

@app.route("/api/snapshot")
def api_snapshot():
    if not SNAPSHOT_PATH.exists():
        return jsonify({"error": "No snapshot yet"}), 404
    return send_file(str(SNAPSHOT_PATH), mimetype="image/jpeg")

# ── WEBSOCKET EVENTS ──────────────────────────────────────────────────────────
@socketio.on("connect")
def on_connect():
    print("[WS] Browser connected")
    emit("sensor_update", state["sensors"])
    if state["ai"]["label"]:
        emit("ai_result", {**state["ai"], "snapshot_url": "/api/snapshot"})
    if state["has_snapshot"]:
        emit("snapshot_update", {"snapshot_url": "/api/snapshot"})

@socketio.on("disconnect")
def on_disconnect():
    print("[WS] Browser disconnected")

@socketio.on("request_analyze")
def on_request_analyze():
    if SNAPSHOT_PATH.exists():
        with open(SNAPSHOT_PATH, "rb") as f:
            img_bytes = f.read()
        result = run_inference(img_bytes)
        if "error" not in result:
            state["ai"].update(result)
            emit("ai_result", {**result, "snapshot_url": "/api/snapshot"}, broadcast=True)

# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Tulsi Smart Plant Monitor - Server Starting")
    print("="*60)
    model_ok = load_model()
    if not model_ok:
        print("[!] Sensor dashboard works; AI disabled until model is trained.")

    import socket as _sock
    try:
        s = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    print(f"\n  Dashboard  : http://localhost:5000")
    print(f"  LAN URL    : http://{local_ip}:5000")
    print(f"\n  Set SERVER_IP = \"{local_ip}\" in your .ino files")
    print("="*60 + "\n")

    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
