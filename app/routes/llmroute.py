from fastapi import APIRouter, Depends, HTTPException
from app.core.llmcore import generate_weekly_llm_report, store_llm_report
from app.core.usercore import get_current_user
from app.core.db import llm_reports_collection

router = APIRouter(prefix="/llm", tags=["LLM"])

@router.post("/weekly-llm-report")
def generate_and_store_weekly_llm_report(
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    llm_data = generate_weekly_llm_report(user_id)
    if not llm_data:
        raise HTTPException(
            status_code=404,
            detail="Weekly data not available for LLM generation"
        )

    store_llm_report(
        user_id=user_id,
        week_id=llm_data["week_id"],
        report=llm_data["report"]
    )

    return {
        "status": "stored",
        "user_id": user_id,
        "week_id": llm_data["week_id"],
        "generated_at": llm_data["generated_at"]
    }

@router.get("/weekly-report")
def get_weekly_llm_report(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]

    doc = llm_reports_collection.find_one(
        {"user_id": user_id},
        sort=[("generated_at", -1)]
    )

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="No weekly LLM report found"
        )

    doc["_id"] = str(doc["_id"])
    return doc
