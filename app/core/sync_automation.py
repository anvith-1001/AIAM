import asyncio
import logging
import time

from app.core.usercore import users_collection
from app.core.medicore import (
    get_latest_hr_from_firebase,
    get_latest_ecg_from_firebase,
    store_hr_in_mongo,
    store_ecg_in_mongo,
    process_ecg_signal,
)
from app.core.llmcore import generate_weekly_llm_report, store_llm_report
logger = logging.getLogger(__name__)

SYNC_INTERVAL = 10
ECG_INTERVAL = 10
WEEKLY_LLM_INTERVAL = 6 * 24 * 60 * 60 

last_hr_ts = {}
last_ecg_ts = {}
last_llm_ts = {}

def should_store_hr(user_id: str, timestamp: int) -> bool:
    last = last_hr_ts.get(user_id)
    if last is None or timestamp > last:
        last_hr_ts[user_id] = timestamp
        return True
    return False

def should_run_ecg(user_id: str) -> bool:
    last = last_ecg_ts.get(user_id)
    now = int(time.time())

    if last is None or (now - last) >= ECG_INTERVAL:
        last_ecg_ts[user_id] = now
        return True
    return False

def should_run_weekly_llm(user_id: str) -> bool:
    last = last_llm_ts.get(user_id)
    now = int(time.time())

    if last is None or (now - last) >= WEEKLY_LLM_INTERVAL:
        last_llm_ts[user_id] = now
        return True
    return False


async def sync_all_users():
    logger.warning(" Firebase sync worker STARTED")

    while True:
        cycle_start = time.time()

        try:
            users = list(users_collection.find({}, {"_id": 1}))
            logger.info(f"Sync cycle users={len(users)}")

            for user in users:
                user_id = str(user["_id"])

                hr_data = get_latest_hr_from_firebase(user_id)
                if hr_data and should_store_hr(user_id, hr_data["timestamp"]):
                    store_hr_in_mongo(
                        user_id,
                        hr_data["hr"],
                        hr_data["timestamp"]
                    )
                    logger.info(f"HR stored user={user_id}")

                if should_run_ecg(user_id):
                    ecg_data = get_latest_ecg_from_firebase(user_id)
                    if ecg_data:
                        prediction = await asyncio.to_thread(
                            process_ecg_signal,
                            ecg_data["signal"]
                        )
                        store_ecg_in_mongo(
                            user_id,
                            ecg_data,
                            prediction
                        )
                        logger.info(f"ECG stored user={user_id}")
                
                if should_run_weekly_llm(user_id):
                    llm_data = generate_weekly_llm_report(user_id)
                    if llm_data:
                        store_llm_report(
                            user_id=user_id,
                            week_id=llm_data["week_id"],
                            report=llm_data["report"]
                        )
                        logger.info(f"Weekly LLM report stored user={user_id}")


        except Exception:
            logger.exception(" SYNC LOOP ERROR")

        elapsed = round(time.time() - cycle_start, 2)
        logger.info(f"Cycle completed in {elapsed}s")

        await asyncio.sleep(SYNC_INTERVAL)
