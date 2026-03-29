from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional
from enum import Enum
from datetime import time


class SexEnum(str, Enum):
    male = "male"
    female = "female"


class HealthDetails(BaseModel):
    prior_cardiac_history: bool
    cardiac_history_note: Optional[str] = None
    medications: str
    age: int = Field(gt=0, lt=120)
    sex: SexEnum
    weight: float = Field(gt=0, lt=300)
    height: float = Field(gt=0, lt=250)

    @model_validator(mode="after")
    def validate_cardiac_note(self):
        if self.prior_cardiac_history and not self.cardiac_history_note:
            raise ValueError(
                "cardiac_history_note is required when prior_cardiac_history is true"
            )
        return self


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    health: HealthDetails
    sleep_start: Optional[datetime] = None
    sleep_end: Optional[datetime] = None


class UserResponse(BaseModel):
    user_id: str
    token: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    health: Optional[HealthDetails] = None
    sleep_start: Optional[datetime] = None
    sleep_end: Optional[datetime] = None

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

from pydantic import BaseModel, EmailStr

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

