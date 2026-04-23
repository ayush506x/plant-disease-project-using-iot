"""
Tulsi Plant Disease Classifier -- Real-time Detection App
Uses a trained MobileNetV2 model to classify Tulsi leaf conditions via webcam.

Usage:
    python detect_disease.py                    # Live webcam mode
    python detect_disease.py --image <path>     # Single image mode

Controls (webcam mode):
    SPACE   -- Capture & classify current frame
    R       -- Reset / clear result overlay
    Q       -- Quit
"""

import cv2
import json
import sys
import numpy as np
import argparse
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# ── CONFIG ─────────────────────────────────────────────────────────────────────
MODEL_PATH  = Path(__file__).parent / "tulsi_classifier.keras"
LABELS_PATH = Path(__file__).parent / "class_labels.json"
IMG_SIZE    = (224, 224)

# Colors per class: BGR format
CLASS_COLORS = {
    "healthy":   (50,  200, 50),
    "bacterial": (0,   80,  220),
    "fungal":    (0,   140, 255),
    "pests":     (0,   50,  180),
}
CLASS_ADVICE = {
    "healthy":   "Plant looks healthy! Keep up the good care.",
    "bacterial": "Possible bacterial infection. Apply bactericide and remove infected leaves.",
    "fungal":    "Possible fungal disease. Apply fungicide and improve air circulation.",
    "pests":     "Pest damage detected. Inspect and apply appropriate pesticide.",
}

# ── LOAD MODEL ─────────────────────────────────────────────────────────────────
def load_model_and_labels():
    if not MODEL_PATH.exists():
        print(f"\n[ERROR] Model not found at: {MODEL_PATH}")
        print("        Please run `python train_model.py` first to train the model.\n")
        sys.exit(1)
    if not LABELS_PATH.exists():
        print(f"\n[ERROR] class_labels.json not found at: {LABELS_PATH}")
        sys.exit(1)

    print("[*] Loading model ...")
    import tensorflow as tf
    model = tf.keras.models.load_model(str(MODEL_PATH))
    with open(LABELS_PATH) as f:
        label_map = json.load(f)
    label_map = {int(k): v for k, v in label_map.items()}
    print(f"[*] Model loaded. Classes: {list(label_map.values())}\n")
    return model, label_map

# ── INFERENCE ──────────────────────────────────────────────────────────────────
def predict(model, label_map, frame_rgb):
    img = cv2.resize(frame_rgb, IMG_SIZE)
    img = img.astype("float32") / 255.0
    img = np.expand_dims(img, axis=0)
    preds = model.predict(img, verbose=0)[0]
    idx = int(np.argmax(preds))
    label = label_map[idx]
    confidence = float(preds[idx]) * 100
    return label, confidence, preds

# ── DRAW OVERLAY ───────────────────────────────────────────────────────────────
def draw_overlay(frame, label, confidence, label_map, preds):
    h, w = frame.shape[:2]
    color = CLASS_COLORS.get(label, (255, 255, 255))

    # Border
    cv2.rectangle(frame, (0, 0), (w - 1, h - 1), color, 8)

    # Top banner
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 90), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    # Main label
    cv2.putText(frame, label.upper(), (20, 50),
                cv2.FONT_HERSHEY_DUPLEX, 1.4, color, 2, cv2.LINE_AA)

    # Confidence bar
    bar_x, bar_y, bar_w, bar_h = 20, 62, 300, 18
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (60, 60, 60), -1)
    filled = int(bar_w * confidence / 100)
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + filled, bar_y + bar_h), color, -1)
    cv2.putText(frame, f"{confidence:.1f}%", (bar_x + bar_w + 10, bar_y + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)

    # Advice at bottom
    advice = CLASS_ADVICE.get(label, "")
    overlay2 = frame.copy()
    cv2.rectangle(overlay2, (0, h - 50), (w, h), (20, 20, 20), -1)
    cv2.addWeighted(overlay2, 0.75, frame, 0.25, 0, frame)
    cv2.putText(frame, advice, (15, h - 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

    # Mini probability bar chart
    n = len(preds)
    chart_x, chart_y0 = w - 165, 20
    for i in range(n):
        cls_label = label_map[i]
        prob = float(preds[i])
        bar_len = int(130 * prob)
        bcolor = CLASS_COLORS.get(cls_label, (180, 180, 180))
        y = chart_y0 + i * 22
        cv2.rectangle(frame, (chart_x, y), (chart_x + bar_len, y + 16), bcolor, -1)
        cv2.putText(frame, f"{cls_label[:3].upper()} {prob*100:.0f}%",
                    (chart_x - 70, y + 13),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (230, 230, 230), 1, cv2.LINE_AA)

    return frame

# ── SINGLE IMAGE MODE ──────────────────────────────────────────────────────────
def run_image_mode(model, label_map, image_path):
    frame = cv2.imread(str(image_path))
    if frame is None:
        print(f"[ERROR] Cannot read image: {image_path}")
        sys.exit(1)

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    label, confidence, preds = predict(model, label_map, frame_rgb)

    print(f"\n[*] Result for: {image_path}")
    print(f"    Label      : {label.upper()}")
    print(f"    Confidence : {confidence:.2f}%")
    print(f"    Advice     : {CLASS_ADVICE.get(label, '')}\n")

    result = draw_overlay(frame, label, confidence, label_map, preds)
    win_title = f"Tulsi Classifier -- {label.upper()} ({confidence:.1f}%)"
    cv2.namedWindow(win_title, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_title, 800, 600)
    cv2.imshow(win_title, result)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

# ── WEBCAM MODE ────────────────────────────────────────────────────────────────
def run_webcam_mode(model, label_map):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Cannot open webcam. Check camera connection.")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    WIN = "Tulsi Disease Detector  |  SPACE=Capture  R=Reset  Q=Quit"
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN, 960, 600)

    last_label      = None
    last_confidence = None
    last_preds      = None
    frozen          = False

    print("\n[*] Webcam started!")
    print("    Hold a Tulsi leaf in front of the camera.")
    print("    Press SPACE to capture & classify.")
    print("    Press R to reset, Q to quit.\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARNING] Lost camera feed.")
            break

        display = frame.copy()

        if frozen and last_label is not None:
            display = draw_overlay(display, last_label, last_confidence, label_map, last_preds)
        else:
            h, w = frame.shape[:2]
            cx, cy = w // 2, h // 2
            box_s = min(h, w) // 3
            cv2.rectangle(display,
                          (cx - box_s, cy - box_s),
                          (cx + box_s, cy + box_s),
                          (100, 255, 100), 2)
            cv2.putText(display, "Position leaf in box, then press SPACE",
                        (cx - box_s, cy - box_s - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 255, 100), 1, cv2.LINE_AA)
            cv2.putText(display, "SPACE=Capture  R=Reset  Q=Quit",
                        (15, h - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

        cv2.imshow(WIN, display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q") or key == 27:
            break
        elif key == ord(" "):
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            last_label, last_confidence, last_preds = predict(model, label_map, frame_rgb)
            frozen = True
            print(f"[*] Predicted: {last_label.upper()}  ({last_confidence:.1f}%)")
        elif key == ord("r"):
            frozen = False
            last_label = last_confidence = last_preds = None

    cap.release()
    cv2.destroyAllWindows()
    print("[*] Done.")

# ── ENTRY POINT ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tulsi Disease Detector")
    parser.add_argument("--image", type=str, default=None,
                        help="Path to an image file (omit for webcam mode)")
    args = parser.parse_args()

    model, label_map = load_model_and_labels()

    if args.image:
        run_image_mode(model, label_map, Path(args.image))
    else:
        run_webcam_mode(model, label_map)
