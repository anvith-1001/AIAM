import os
from fastapi import Depends, Header, HTTPException, status
from dotenv import load_dotenv

load_dotenv()

SERVICE_TOKEN = os.getenv("SERVICE_SYNC_TOKEN")

def verify_service_token(
    authorization: str = Header(...)
):

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format"
        )

    token = authorization.split(" ")[1]

    if token != SERVICE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid service token"
        )

    return {"service": "firebase-sync"}
