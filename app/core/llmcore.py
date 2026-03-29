import os
import json
from datetime import datetime, timezone
from bson import ObjectId
from dotenv import load_dotenv
from openai import OpenAI
from app.core.medicore import users_collection, week_collection
from app.models.usermodel import HealthDetails

load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

from app.core.db import db  
llm_reports_collection = db["llm_reports"]


def get_user_health_data(user_id: str) -> HealthDetails:
    user = users_collection.find_one({"_id": ObjectId(user_id)})

    health = user.get("health", {})

    return HealthDetails(
        prior_cardiac_history=health["prior_cardiac_history"],
        cardiac_history_note=health.get("cardiac_history_note"),
        medications=health["medications"],
        age=health["age"],
        sex=health["sex"],
        weight=health["weight"],
        height=health["height"],
    )



def get_weekly_summary_data(user_id: str):
    doc = week_collection.find_one({"user_id": user_id})
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc


def build_llm_prompt(health: HealthDetails, weekly_data: dict):
    cardiac_history_section = (
        f"- Prior cardiac history: Yes\n"
        f"- Cardiac history details: {health.cardiac_history_note}\n"
        if health.prior_cardiac_history
        else "- Prior cardiac history: No\n"
    )

    return f"""
You are a highly skilled medical expert.

IMPORTANT:
- This is for education and awareness only.
- Do NOT provide a medical diagnosis.
- Avoid alarming language.
- Recommend professional consultation when appropriate.

You MUST return ONLY valid JSON.
Do NOT include markdown, explanations, or extra text.
Do NOT include trailing commas.

=== REQUIRED JSON SCHEMA ===
{{
  "weekly_health_summary": string,
  "ecg_pattern_insights": string,
  "heart_rate_pattern_insights": string,
  "possible_risk_indicators": array of strings,
  "lifestyle_recommendations": array of strings,
  "diet_recommendations": array of strings,
  "medical_attention_advice": string
}}

=== PATIENT MEDICAL DETAILS ===
- Age: {health.age}
- Sex: {health.sex.value if hasattr(health.sex, "value") else health.sex}
- Weight: {health.weight} kg
- Height: {health.height} cm
{cardiac_history_section}
- Medications: {health.medications}

=== WEEKLY HEART DATA (HR + ECG) ===
{weekly_data}

RULES:
- Fill all fields.
- If data is insufficient, state that clearly in the relevant field.
- Be conservative in risk assessment.
"""


def generate_weekly_llm_report(user_id: str):
    health = get_user_health_data(user_id)
    weekly = get_weekly_summary_data(user_id)

    if not weekly:
        return None

    prompt = build_llm_prompt(health, weekly)

    response = openai_client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "system",
                "content": "You are a medical expert who outputs strict JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=900,
        temperature=0.3
    )

    raw_output = response.choices[0].message.content.strip()

    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON returned by LLM:\n{raw_output}")

    return {
        "user_id": user_id,
        "week_id": weekly["week_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report": parsed
    }


def store_llm_report(user_id: str, week_id: str, report: dict):
    return llm_reports_collection.update_one(
        {
            "user_id": user_id,
            "week_id": week_id
        },
        {
            "$set": {
                "report": report,
                "generated_at": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )