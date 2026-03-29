import os
import random
import time
import resend
from dotenv import load_dotenv

load_dotenv()

# env variables
RESEND_API = os.getenv("RESEND_API")

resend.api_key = RESEND_API

otp_store = {}


def generate_otp(length=4) -> str:
    return ''.join(random.choices('0123456789', k=length))


# send email and otp functions
def send_email(to_email: str, subject: str, message: str) -> bool:
    try:
        response = resend.Emails.send({
            "from": "onboarding@resend.dev",  
            "to": [to_email],
            "subject": subject,
            "text": message,
        })

        print(f"[INFO] OTP email sent to {to_email}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False


def send_otp(email: str) -> bool:
    otp = generate_otp()
    subject = "Your Verification Code"
    message = f"Your OTP for verification is: {otp}\n\nThis code will expire in 5 minutes."

    sent = send_email(email, subject, message)
    if sent:
        otp_store[email] = {"otp": otp, "timestamp": time.time()}
        print(f"[INFO] OTP '{otp}' stored for {email}")
        return True
    else:
        print(f"[ERROR] Could not send OTP to {email}")
        return False


def verify_otp(email: str, user_input_otp: str) -> bool:
    record = otp_store.get(email)
    if not record:
        print(f"[WARN] No OTP found for {email}")
        return False

    if time.time() - record['timestamp'] > 300:
        print(f"[WARN] OTP expired for {email}")
        del otp_store[email]
        return False

    if record['otp'] == user_input_otp:
        print(f"[INFO] OTP verified for {email}")
        del otp_store[email]
        return True
    else:
        print(f"[WARN] Invalid OTP for {email}")
        return False