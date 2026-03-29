import os
import time
import random
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv

load_dotenv()

FIREBASE_CRED_PATH = os.getenv("FIREBASE_CRED_PATH")
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")
USER_ID = os.getenv("USER_ID")

cred = credentials.Certificate(FIREBASE_CRED_PATH)

firebase_admin.initialize_app(cred, {
    "databaseURL": FIREBASE_DB_URL
})


def send_heart_rate():
    hr_value = random.randint(60, 100)

    ref = db.reference(f"users/{USER_ID}/heart_rate")
    ref.push({
        "hr": hr_value,
        "timestamp": datetime.utcnow().isoformat()
    })

    print(f"[HR] Sent: {hr_value}")


def send_ecg():
    ecg_signal = [round(random.uniform(-1, 1), 4) for _ in range(187)]

    ref = db.reference(f"users/{USER_ID}/ecg")
    ref.push({
        "signal": ecg_signal,
        "timestamp": datetime.utcnow().isoformat()
    })

    print("[ECG] Sent 187-sample dummy signal")


if __name__ == "__main__":
    last_ecg_time = 0

    while True:
        send_heart_rate()

        current_time = time.time()
        if current_time - last_ecg_time >= 14400:
            send_ecg()
            last_ecg_time = current_time

        time.sleep(10)
