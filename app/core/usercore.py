from fastapi import HTTPException,Depends
from fastapi.security import HTTPBearer
from datetime import datetime, timedelta
from bson import ObjectId
import bcrypt
import jwt
from pymongo import MongoClient
import os
from dotenv import load_dotenv

auth_scheme = HTTPBearer()
load_dotenv()  

MONGO_URL = os.getenv("MONGO_URL")
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")
JWT_ALGO = os.getenv("JWT_ALGO")

client = MongoClient(MONGO_URL)
db = client["theapp"]
users_collection = db["users"]



def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def verify_password(password: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed)

def create_jwt_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def decode_jwt(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(auth=Depends(auth_scheme)):
    token = auth.credentials
    payload = decode_jwt(token)

    user_id = payload.get("user_id")
    user = users_collection.find_one({"_id": ObjectId(user_id)})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": str(user["_id"]),
        "email": user["email"],
        "health": user["health"],
        "created_at": user["created_at"]
    }