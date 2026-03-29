import os
import json
import numpy as np
import wfdb
import tensorflow as tf

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.utils.class_weight import compute_class_weight
from tensorflow.keras import layers, models

MITBIH_RECORDS = [
    "100","101","102","103","104","105","106","107","108","109",
    "111","112","113","114","115","116","117","118","119",
    "121","122","123","124",
    "200","201","202","203","205","207","208","209",
    "210","212","213","214","215","217","219","220","221","222","223","228",
    "230","231","232","233","234"
]

DATA_DIR = "./mitbih/"
OUTPUT_DIR = "./output/"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

SAMPLE_RATE = 360
SEG_SEC = 5.0
SEG_LEN = int(SAMPLE_RATE * SEG_SEC)

np.random.seed(42)
tf.random.set_seed(42)

ANNOTATION_TO_CLASS = {
    'N': 'N', 'L': 'N', 'R': 'N', 'e': 'N', 'j': 'N',
    'V': 'V', 'E': 'V',
    'A': 'S', 'a': 'S', 'J': 'S', 'S': 'S',
    'F': 'F', 'f': 'F',
    '/': 'Q', 'Q': 'Q'
}

def download_record(rec):
    if not os.path.exists(os.path.join(DATA_DIR, rec + ".dat")):
        wfdb.dl_database("mitdb", DATA_DIR, records=[rec])

def extract_segments_and_labels(record_name):
    try:
        sig, _ = wfdb.rdsamp(os.path.join(DATA_DIR, record_name))
        ann = wfdb.rdann(os.path.join(DATA_DIR, record_name), "atr")
    except Exception as e:
        print("Error loading:", record_name, e)
        return [], []

    sig = sig[:, 0]
    sig = sig - np.mean(sig)

    segments, labels = [], []

    for i, sym in enumerate(ann.symbol):

        if sym not in ANNOTATION_TO_CLASS:
            continue

        center = ann.sample[i]
        start = center - SEG_LEN // 2
        end = start + SEG_LEN

        if start < 0 or end > len(sig):
            continue

        segments.append(sig[start:end].astype(np.float32))
        labels.append(ANNOTATION_TO_CLASS[sym])

    return segments, labels

def prepare_dataset():

    X, y = [], []

    for rec in MITBIH_RECORDS:
        print("Processing:", rec)

        download_record(rec)

        segs, labs = extract_segments_and_labels(rec)

        X.extend(segs)
        y.extend(labs)

    return np.array(X), np.array(y)


def build_model(input_len, n_classes):

    model = models.Sequential([

        layers.Input(shape=(input_len, 1)),

        layers.Conv1D(64, 7, activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling1D(2),

        layers.Conv1D(128, 5, activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling1D(2),

        layers.Conv1D(128, 3, activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling1D(2),

        layers.LSTM(64),

        layers.Dropout(0.4),

        layers.Dense(64, activation="relu"),
        layers.Dropout(0.3),

        layers.Dense(n_classes, activation="softmax")
    ])

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"]
    )

    return model


def compute_tp_tn_fp_fn(cm, idx):

    TP = cm[idx, idx]

    FP = cm[:, idx].sum() - TP

    FN = cm[idx, :].sum() - TP

    TN = cm.sum() - (TP + FP + FN)

    return TP, TN, FP, FN


def main():

    X, y = prepare_dataset()
    le = LabelEncoder()
    y_enc = le.fit_transform(y)
    labels = list(le.classes_)
    n, L = X.shape
    scaler = StandardScaler()
    X = scaler.fit_transform(X.reshape(n, L)).reshape(n, L, 1)
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y_enc,
        test_size=0.15,
        stratify=y_enc,
        random_state=42
    )

    class_weights = compute_class_weight(
        class_weight="balanced",
        classes=np.unique(y_train),
        y=y_train
    )

    class_weights = dict(enumerate(class_weights))

    model = build_model(L, len(labels))
    model.summary()

    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=6,
            restore_best_weights=True
        ),
        tf.keras.callbacks.ModelCheckpoint(
            os.path.join(OUTPUT_DIR, "model.h5"),
            save_best_only=True,
            monitor="val_loss"
        )
    ]

    model.fit(
        X_train,
        y_train,
        validation_split=0.1,
        epochs=8,
        batch_size=128,
        callbacks=callbacks,
        class_weight=class_weights
    )

    y_pred = np.argmax(model.predict(X_test), axis=1)
    print("\nClassification Report")
    print(classification_report(y_test, y_pred, target_names=labels))
    cm = confusion_matrix(y_test, y_pred)
    np.save(os.path.join(OUTPUT_DIR, "confusion_matrix.npy"), cm)
    print("\nTP / TN / FP / FN per class")

    for i, lbl in enumerate(labels):
        TP, TN, FP, FN = compute_tp_tn_fp_fn(cm, i)
        print(f"\nClass {lbl}")
        print(f"TP: {TP}")
        print(f"TN: {TN}")
        print(f"FP: {FP}")
        print(f"FN: {FN}")

    model.save(os.path.join(OUTPUT_DIR, "model_final.h5"))
    np.save(os.path.join(OUTPUT_DIR, "scaler_mean.npy"), scaler.mean_)
    np.save(os.path.join(OUTPUT_DIR, "scaler_scale.npy"), scaler.scale_)

    with open(os.path.join(OUTPUT_DIR, "labels.json"), "w") as f:
        json.dump(labels, f)

    print("\nAll outputs saved to", OUTPUT_DIR)


if __name__ == "__main__":
    main()