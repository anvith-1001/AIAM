from fastapi import APIRouter, HTTPException,Depends
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from app.core.usercore import hash_password, verify_password, create_jwt_token, get_current_user
from app.models.usermodel import UserRegister,UserLogin,UserResponse,UserUpdate, EmailStr, ResetPasswordRequest, ForgotPasswordRequest
from app.core.smtpcore import send_otp, verify_otp

router = APIRouter()

load_dotenv()  


MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")
JWT_ALGO = os.getenv("JWT_ALGO", "HS256")


client = MongoClient(MONGO_URL)
db = client["theapp"]
users_collection = db["users"]


# register endpoint
@router.post("/register", response_model=UserResponse)
def register_user(data: UserRegister):

    if users_collection.find_one({"email": data.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = hash_password(data.password)

    user_doc = {
        "email": data.email,
        "password": hashed_pw,
        "name": data.name,
        "health": data.health.dict(),
        "sleep_start": data.sleep_start if data.sleep_start else None,
        "sleep_end": data.sleep_end if data.sleep_end else None,
        "created_at": datetime.utcnow(),
    }

    result = users_collection.insert_one(user_doc)

    token = create_jwt_token(str(result.inserted_id))

    return {"user_id": str(result.inserted_id), "token": token}


# login endpoint
@router.post("/login", response_model=UserResponse)
def login_user(data: UserLogin):

    user = users_collection.find_one({"email": data.email})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    stored_hashed_pw = user["password"]
    if not verify_password(data.password, stored_hashed_pw):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    user_id = str(user["_id"])
    token = create_jwt_token(user_id)

    return UserResponse(user_id=user_id, token=token)

# get current user details endpoint
@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    user = users_collection.find_one(
        {"_id": ObjectId(current_user["user_id"])},
        {"password": 0}  
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user["user_id"] = str(user["_id"])
    user.pop("_id")

    return user


# update user endpoint
@router.patch("/update")
def update_user(data: UserUpdate, current_user: dict = Depends(get_current_user)):

    updates = {}

    if data.email:
        existing = users_collection.find_one({"email": data.email})
        if existing and str(existing["_id"]) != current_user["user_id"]:
            raise HTTPException(status_code=400, detail="Email already in use")
        updates["email"] = data.email

    if data.password:
        updates["password"] = hash_password(data.password)

    if data.name:
        updates["name"] = data.name

    if data.sleep_start and data.sleep_end:
        start_t = data.sleep_start.time()
        end_t = data.sleep_end.time()

        if start_t == end_t:
            raise HTTPException(
                status_code=400,
                detail="Sleep start and end cannot be the same"
            )

        updates["sleep_start"] = data.sleep_start
        updates["sleep_end"] = data.sleep_end

    if data.health:
        updates["health"] = {
            "prior_cardiac_history": data.health.prior_cardiac_history,
            "cardiac_history_note": data.health.cardiac_history_note,
            "medications": data.health.medications,
            "age": data.health.age,
            "sex": data.health.sex,
            "weight": data.health.weight,
            "height": data.health.height,
        }

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    users_collection.update_one(
        {"_id": ObjectId(current_user["user_id"])},
        {"$set": updates}
    )

    return {"message": "User updated successfully"}


# forgot password endpoints
@router.post("/forgot-password/send-otp")
def forgot_password_send_otp(data: ForgotPasswordRequest):
    email = data.email

    user = users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="Email not registered")

    sent = send_otp(email)
    if not sent:
        raise HTTPException(status_code=500, detail="Failed to send OTP")

    return {"message": "OTP sent to your email"}

@router.post("/forgot-password/verify")
def forgot_password_verify(data: ResetPasswordRequest):
    user = users_collection.find_one({"email": data.email})
    if not user:
        raise HTTPException(status_code=404, detail="Email not registered")

    if not verify_otp(data.email, data.otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    hashed_pw = hash_password(data.new_password)

    users_collection.update_one(
        {"email": data.email},
        {"$set": {"password": hashed_pw}}
    )

    return {"message": "Password reset successfully"}

# delete user account endpoint
@router.delete("/delete")
def delete_user(current_user: dict = Depends(get_current_user)):

    result = users_collection.delete_one(
        {"_id": ObjectId(current_user["user_id"])}
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User account deleted successfully"}

# wake up endpoint
@router.get("/stayin-alive")
def stayin_alive():
    return {"message": "I'm alive!"}