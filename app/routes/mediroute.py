from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from app.core.medicore import (
    get_latest_hr_from_firebase,
    store_hr_in_mongo,
    get_latest_ecg_from_firebase,
    process_ecg_signal,
    store_ecg_in_mongo,
    calculate_average_hr,
    calculate_resting_hr,
    get_ecg_results_for_day,
    store_daily_summary,
    week_collection
)
from app.core.usercore import get_current_user
from app.core.servicecore import verify_service_token

router = APIRouter(prefix="/med", tags=["Medicare"])


@router.post("/sync/hr/{user_id}")
def sync_heart_rate(
    user_id: str,
    service=Depends(verify_service_token)
):
    data = get_latest_hr_from_firebase(user_id)

    if not data:
        raise HTTPException(status_code=404, detail="No HR data found in Firebase")

    ok = store_hr_in_mongo(
        user_id,
        data["hr"],
        data["timestamp"]
    )

    return {
        "synced": ok,
        "user_id": user_id,
        "hr": data["hr"],
        "timestamp": data["timestamp"]
    }


@router.post("/sync/ecg/{user_id}")
def sync_ecg(
    user_id: str,
    service=Depends(verify_service_token)
):
    data = get_latest_ecg_from_firebase(user_id)

    if not data:
        raise HTTPException(status_code=404, detail="No ECG data found in Firebase")

    prediction = process_ecg_signal(data["signal"])

    ok = store_ecg_in_mongo(
        user_id,
        data,
        prediction
    )

    return {
        "synced": ok,
        "user_id": user_id,
        "prediction": prediction
    }



@router.post("/daily-summary")
def daily_summary(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    today = datetime.now(timezone.utc)

    avg_hr = calculate_average_hr(user_id, today)
    rest_hr = calculate_resting_hr(user_id)
    ecg_results = get_ecg_results_for_day(user_id, today)

    summary_parts = []

    if avg_hr:
        summary_parts.append(f"Your average heart rate today was {avg_hr:.2f} bpm.")
    else:
        summary_parts.append("Heart rate data was insufficient today.")

    if rest_hr:
        summary_parts.append(f"Your resting heart rate was {rest_hr:.2f} bpm.")

    if ecg_results:
        abnormal = any(r["class"] != "N" for r in ecg_results)
        if abnormal:
            summary_parts.append(
                "Some ECG readings showed irregular patterns. Please monitor closely."
            )
        else:
            summary_parts.append("No abnormal ECG patterns were detected today.")
    else:
        summary_parts.append("No ECG readings were recorded today.")

    summary = " ".join(summary_parts)

    store_daily_summary(user_id, today, avg_hr, rest_hr, ecg_results)

    return {
        "avg_hr": avg_hr,
        "rest_hr": rest_hr,
        "ecg_reports": ecg_results,
        "summary": summary,  
    }


@router.get("/weekly-summary")
def weekly_summary(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]

    doc = week_collection.find_one(
        {"user_id": user_id},
        sort=[("_id", -1)]  
    )

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="No weekly report found"
        )

    doc["_id"] = str(doc["_id"])
    return doc