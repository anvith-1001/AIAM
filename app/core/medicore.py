import os
import json
import requests
import numpy as np
from datetime import datetime, timezone, timedelta, time
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from bson import ObjectId
import firebase_admin
from firebase_admin import credentials, db
from tensorflow.keras.models import load_model

load_dotenv()


# add URL here

MODEL_URL = os.getenv("MODEL_URL")
SCALER_MEAN_URL = os.getenv("SCALER_MEAN_URL")
SCALER_SCALE_URL = os.getenv("SCALER_SCALE_URL")
LABELS_URL = os.getenv("LABELS_URL")


ASSETS_DIR = "models"

MODEL_PATH = os.path.join(ASSETS_DIR, "model_final.h5")
SCALER_MEAN_PATH = os.path.join(ASSETS_DIR, "scaler_mean.npy")
SCALER_SCALE_PATH = os.path.join(ASSETS_DIR, "scaler_scale.npy")
LABELS_PATH = os.path.join(ASSETS_DIR, "labels.json")

def download_file(url: str, path: str):
    if os.path.exists(path):
        print(f"Already exists: {path}")
        return

    os.makedirs(os.path.dirname(path), exist_ok=True)

    headers = {}
    github_token = os.getenv("GITHUB_TOKEN")

    if github_token:
        headers["Authorization"] = f"token {github_token}"

    print(f" Downloading {os.path.basename(path)}")

    r = requests.get(url, headers=headers, stream=True, timeout=30)
    r.raise_for_status()

    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    print(f"Saved to {path}")

download_file(MODEL_URL, MODEL_PATH)
download_file(SCALER_MEAN_URL, SCALER_MEAN_PATH)
download_file(SCALER_SCALE_URL, SCALER_SCALE_PATH)
download_file(LABELS_URL, LABELS_PATH)
FIREBASE_CRED_PATH = os.getenv("FIREBASE_CRED_PATH")
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")

if not FIREBASE_CRED_PATH or not FIREBASE_DB_URL:
    raise RuntimeError("Firebase env vars not set")

SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", 360))
MONGO_URL = os.getenv("MONGO_URL")

cred = credentials.Certificate(FIREBASE_CRED_PATH)
firebase_admin.initialize_app(cred, {
    "databaseURL": FIREBASE_DB_URL
})

firebase_root = db.reference("/") 

client = MongoClient(MONGO_URL)
db = client["theapp"]

users_collection = db["users"]
hr_collection = db["user_hr_logs"]
ecg_collection = db["user_ecg_logs"]
week_collection = db["user_week_reports"]


model = load_model(MODEL_PATH)
scaler_mean = np.load(SCALER_MEAN_PATH)
scaler_scale = np.load(SCALER_SCALE_PATH)

with open(LABELS_PATH, "r") as f:
    LABELS = json.load(f)




def scale_ecg(signal: np.ndarray) -> np.ndarray:
    return (signal - scaler_mean) / scaler_scale


def get_latest_hr_from_firebase(user_id: str):
    ref = firebase_root.child(f"device/{user_id}/heart_rate")
    data = ref.get()

    if not data:
        return None

    hr = data.get("hr")
    timestamp = data.get("timestamp")

    if hr is None or timestamp is None:
        return None

    if not isinstance(hr, (int, float)) or hr < 30 or hr > 220:
        return None

    return {
        "hr": int(hr),
        "timestamp": int(timestamp)
    }

def store_hr_in_mongo(user_id: str, hr: int, timestamp: int) -> bool:
    if hr is None or timestamp is None:
        return False

    record = {
        "hr": hr,
        "timestamp": timestamp,
        "dt": datetime.fromtimestamp(timestamp, timezone.utc)
    }

    result = hr_collection.update_one(
        {
            "user_id": user_id,
            "records.timestamp": {"$ne": timestamp}
        },
        {
            "$push": {"records": record},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        },
        upsert=True
    )

    return result.modified_count == 1 or result.upserted_id is not None


def get_latest_ecg_from_firebase(user_id: str):
    ref = firebase_root.child(f"device/{user_id}/ecg")
    data = ref.get()
    if not data:
        return None
    return {
        "signal": data.get("signal"),
        "timestamp": data.get("timestamp")
    }


def store_ecg_in_mongo(user_id: str, ecg_data: dict, prediction: dict):
    exists = ecg_collection.find_one({
        "user_id": user_id,
        "timestamp": ecg_data["timestamp"]
    })
    if exists:
        return False
    ecg_collection.insert_one({
        "user_id": user_id,
        "timestamp": ecg_data["timestamp"],
        "dt": datetime.fromtimestamp(ecg_data["timestamp"], timezone.utc),
        "signal_len": len(ecg_data["signal"]),
        "prediction": prediction
    })
    return True


def process_ecg_signal(ecg_signal: list):
    arr = np.array(ecg_signal, dtype=np.float32)
    if len(arr) > 1800:
        arr = arr[:1800]
    elif len(arr) < 1800:
        pad_len = 1800 - len(arr)
        arr = np.pad(arr, (0, pad_len))
    arr = scale_ecg(arr)
    arr = arr.reshape(1, -1, 1)
    pred = model.predict(arr)
    idx = int(np.argmax(pred[0]))
    return {
        "class": LABELS[idx],
        "probabilities": pred[0].tolist()
    }



def calculate_average_hr(user_id: str, day: datetime):
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end = start.replace(hour=23, minute=59, second=59)

    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$unwind": "$records"},
        {
            "$match": {
                "records.dt": {"$gte": start, "$lte": end},
                "records.hr": {"$ne": None}  
            }
        },
        {
            "$group": {
                "_id": None,
                "avg_hr": {"$avg": "$records.hr"}
            }
        }
    ]

    result = list(hr_collection.aggregate(pipeline))

    if not result or result[0]["avg_hr"] is None:
        return None

    return round(result[0]["avg_hr"], 2)


def calculate_resting_hr(user_id: str):
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        return None

    sleep_start = user.get("sleep_start")
    sleep_end = user.get("sleep_end")

    if not sleep_start or not sleep_end:
        return None

    start_t: time = sleep_start.time()
    end_t: time = sleep_end.time()

    today = datetime.utcnow().date()

    start_dt = datetime.combine(today, start_t)
    end_dt = datetime.combine(today, end_t)

    if end_dt <= start_dt:
        end_dt += timedelta(days=1)

    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$unwind": "$records"},
        {
            "$match": {
                "records.dt": {
                    "$gte": start_dt,
                    "$lte": end_dt
                }
            }
        },
        {
            "$group": {
                "_id": None,
                "resting_hr": {"$min": "$records.hr"}
            }
        }
    ]

    result = list(hr_collection.aggregate(pipeline))
    if not result:
        return None

    return result[0]["resting_hr"]


def get_week_id(date: datetime):
    return f"{date.year}-W{date.isocalendar().week}"


def store_daily_summary(user_id: str, date: datetime, avg_hr: float, rest_hr: float, ecg_results: list):
    week_id = get_week_id(date)
    doc = week_collection.find_one({
        "user_id": user_id,
        "week_id": week_id
    })
    day_key = date.strftime("%Y-%m-%d")
    if not doc:
        week_collection.insert_one({
            "user_id": user_id,
            "week_id": week_id,
            "days": {
                day_key: {
                    "avg_hr": avg_hr,
                    "rest_hr": rest_hr,
                    "ecg_reports": ecg_results
                }
            }
        })
        return True
    week_collection.update_one(
        {"user_id": user_id, "week_id": week_id},
        {"$set": {
            f"days.{day_key}": {
                "avg_hr": avg_hr,
                "rest_hr": rest_hr,
                "ecg_reports": ecg_results
            }
        }}
    )
    return True


def get_ecg_results_for_day(user_id: str, date: datetime):
    start = datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
    end = start.replace(hour=23, minute=59, second=59)
    logs = list(ecg_collection.find({
        "user_id": user_id,
        "dt": {"$gte": start, "$lte": end}
    }))
    results = []
    for log in logs:
        results.append(log["prediction"])
    return results
