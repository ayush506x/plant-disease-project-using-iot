"""
Tulsi Plant Disease Classifier -- Training Script
Trains a MobileNetV2 transfer learning model on the dataset.

Usage:
    python train_model.py

Output:
    tulsi_classifier.keras  -- the trained model
    class_labels.json       -- class index to label mapping
"""

import os
import sys
import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau

# ── CONFIG ─────────────────────────────────────────────────────────────────────
DATASET_DIR   = Path(__file__).parent / "dataset" / "train_aug"
IMG_SIZE      = (224, 224)
BATCH_SIZE    = 32
EPOCHS        = 20
OUTPUT_MODEL  = Path(__file__).parent / "tulsi_classifier.keras"
OUTPUT_LABELS = Path(__file__).parent / "class_labels.json"
SEED          = 42
VAL_SPLIT     = 0.2

# ── DATA GENERATORS ────────────────────────────────────────────────────────────
print("\n[*] Loading dataset from:", DATASET_DIR)

train_datagen = ImageDataGenerator(
    rescale=1.0 / 255.0,
    validation_split=VAL_SPLIT,
    rotation_range=25,
    width_shift_range=0.15,
    height_shift_range=0.15,
    shear_range=0.15,
    zoom_range=0.2,
    horizontal_flip=True,
    brightness_range=[0.8, 1.2],
    fill_mode="nearest",
)

val_datagen = ImageDataGenerator(
    rescale=1.0 / 255.0,
    validation_split=VAL_SPLIT,
)

train_gen = train_datagen.flow_from_directory(
    DATASET_DIR,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode="categorical",
    subset="training",
    seed=SEED,
    shuffle=True,
)

val_gen = val_datagen.flow_from_directory(
    DATASET_DIR,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode="categorical",
    subset="validation",
    seed=SEED,
    shuffle=False,
)

# Save class labels
class_indices = train_gen.class_indices               # {"bacterial": 0, ...}
label_map = {str(v): k for k, v in class_indices.items()}  # {"0": "bacterial", ...}
with open(OUTPUT_LABELS, "w") as f:
    json.dump(label_map, f, indent=2)

print("[*] Classes found:", list(class_indices.keys()))
print("[*] Saved class labels ->", OUTPUT_LABELS)

# ── CLASS WEIGHTS ──────────────────────────────────────────────────────────────
class_counts = [len(list((DATASET_DIR / cls).glob("*.jpeg")))
                for cls in class_indices.keys()]
total = sum(class_counts)
class_weight_values = {i: total / (len(class_counts) * c) for i, c in enumerate(class_counts)}
print("[*] Class weights:", class_weight_values)

# ── MODEL ──────────────────────────────────────────────────────────────────────
print("\n[*] Building MobileNetV2 model ...")

NUM_CLASSES = len(class_indices)

base_model = MobileNetV2(
    input_shape=(*IMG_SIZE, 3),
    include_top=False,
    weights="imagenet",
)
base_model.trainable = False

inputs = tf.keras.Input(shape=(*IMG_SIZE, 3))
x = base_model(inputs, training=False)
x = layers.GlobalAveragePooling2D()(x)
x = layers.BatchNormalization()(x)
x = layers.Dense(256, activation="relu")(x)
x = layers.Dropout(0.4)(x)
x = layers.Dense(128, activation="relu")(x)
x = layers.Dropout(0.3)(x)
outputs = layers.Dense(NUM_CLASSES, activation="softmax")(x)

model = models.Model(inputs, outputs)

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
    loss="categorical_crossentropy",
    metrics=["accuracy"],
)
model.summary()

# ── PHASE 1: Train head ────────────────────────────────────────────────────────
print("\n[*] Phase 1 -- Training classification head ...")

callbacks = [
    EarlyStopping(patience=5, restore_best_weights=True, monitor="val_accuracy"),
    ModelCheckpoint(str(OUTPUT_MODEL), save_best_only=True, monitor="val_accuracy"),
    ReduceLROnPlateau(factor=0.5, patience=3, min_lr=1e-6, monitor="val_loss"),
]

history1 = model.fit(
    train_gen,
    validation_data=val_gen,
    epochs=10,
    class_weight=class_weight_values,
    callbacks=callbacks,
)

# ── PHASE 2: Fine-tune top layers ──────────────────────────────────────────────
print("\n[*] Phase 2 -- Fine-tuning top MobileNetV2 layers ...")

base_model.trainable = True
for layer in base_model.layers[:-30]:
    layer.trainable = False

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=1e-4),
    loss="categorical_crossentropy",
    metrics=["accuracy"],
)

history2 = model.fit(
    train_gen,
    validation_data=val_gen,
    epochs=EPOCHS,
    class_weight=class_weight_values,
    callbacks=callbacks,
)

# ── RESULTS ────────────────────────────────────────────────────────────────────
loss, acc = model.evaluate(val_gen)

print("\n" + "=" * 60)
print("  [OK] Training complete!")
print(f"  Validation Accuracy : {acc * 100:.2f}%")
print(f"  Model saved to      : {OUTPUT_MODEL}")
print(f"  Labels saved to     : {OUTPUT_LABELS}")
print("=" * 60 + "\n")

# ── PLOT ───────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
all_acc  = history1.history["accuracy"]  + history2.history["accuracy"]
all_val  = history1.history["val_accuracy"] + history2.history["val_accuracy"]
all_loss = history1.history["loss"] + history2.history["loss"]
all_vloss = history1.history["val_loss"] + history2.history["val_loss"]

axes[0].plot(all_acc,  label="Train Accuracy")
axes[0].plot(all_val,  label="Val Accuracy")
axes[0].set_title("Accuracy")
axes[0].legend()

axes[1].plot(all_loss,  label="Train Loss")
axes[1].plot(all_vloss, label="Val Loss")
axes[1].set_title("Loss")
axes[1].legend()

plt.tight_layout()
plot_path = Path(__file__).parent / "training_history.png"
plt.savefig(plot_path)
print("[*] Training plot saved ->", plot_path)
plt.show()
