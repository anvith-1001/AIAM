# The Health App Backend

FastAPI backend for the health app that handles:

- User authentication and profile management
- Heart-rate and ECG sync from Firebase
- Daily and weekly health summaries
- Arrhythmia classifier and early warning ( CNN + LSTM )
- Weekly LLM-generated health reports and lifestyle recommendations

This application requires a hardware device to get user health data.

Hardware Device Document: https://docs.google.com/document/d/1jCtjUZlMCq8EOS6rEezqeu3t8Kw1eHbKTaZjXdLoMpY/edit?usp=sharing

## Tech Stack

- FastAPI
- MongoDB
- Firebase Realtime Database
- TensorFlow/Keras
- OpenAI API
- Resend

## Project Structure

```text
backend/
├── app/
│   ├── core/
│   ├── models/
│   ├── routes/
│   └── main.py
├── models/
│   ├── model_final.h5
│   ├── scaler_mean.npy
│   ├── scaler_scale.npy
│   └── labels.json
├── finalsmodel.py
├── hardware_test.py
├── requirements.txt
└── README.md
```

## Features

### User

- Register and login with JWT authentication
- Fetch current profile
- Update account details and health profile
- Delete account
- Reset password with OTP email verification

### Medical Data

- Sync heart-rate data from Firebase into MongoDB
- Sync ECG data from Firebase, run model inference, and store predictions
- Generate daily summaries from stored HR and ECG data
- Fetch the latest weekly summary

### LLM Reports

- Generate a weekly AI health report from stored weekly summary data
- Store and fetch the latest LLM report per user

### Background Automation

- Startup task continuously loops through users
- Syncs new HR data
- Periodically processes ECG data
- Periodically generates weekly LLM reports

## Requirements

- Python 3.10+
- MongoDB instance
- Firebase service account credentials
- OpenAI API key
- Resend API key

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file in the project root with values similar to:

```env
MONGO_URL=mongodb://localhost:27017
MONGO_DB_NAME=theapp

JWT_SECRET=your-jwt-secret
JWT_ALGO=HS256
SERVICE_SYNC_TOKEN=your-service-token

FIREBASE_CRED_PATH=/absolute/path/to/firebase-service-account.json
FIREBASE_DB_URL=https://your-project.firebaseio.com

OPENAI_API_KEY=your-openai-api-key
RESEND_API=your-resend-api-key

MODEL_URL=https://example.com/model_final.h5
SCALER_MEAN_URL=https://example.com/scaler_mean.npy
SCALER_SCALE_URL=https://example.com/scaler_scale.npy
LABELS_URL=https://example.com/labels.json

GITHUB_TOKEN=optional-token-for-downloading-model-assets
SAMPLE_RATE=360
```

## Running the Server

```bash
uvicorn app.main:app --reload
```

By default, FastAPI will start locally at:

```text
http://127.0.0.1:8000
```

Docs will be available at:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

## Authentication

Protected user and report endpoints use a bearer JWT token.

Example header:

```http
Authorization: Bearer <jwt-token>
```

Sync endpoints use the service token:

```http
Authorization: Bearer <SERVICE_SYNC_TOKEN>
```

## API Routes

### User Routes

Base path: `/user`

- `POST /user/register`
- `POST /user/login`
- `GET /user/me`
- `PATCH /user/update`
- `POST /user/forgot-password/send-otp`
- `POST /user/forgot-password/verify`
- `DELETE /user/delete`
- `GET /user/stayin-alive`

### Medical Routes

Base path: `/med`

- `POST /med/sync/hr/{user_id}`
- `POST /med/sync/ecg/{user_id}`
- `POST /med/daily-summary`
- `GET /med/weekly-summary`

### LLM Routes

Base path: `/llm`

- `POST /llm/weekly-llm-report`
- `GET /llm/weekly-report`

## Notes

- ECG classifier model assets are downloaded during initial startup if the target files do not already exist in `models/`.
- Firebase and model-loading happen during import, so missing configuration will prevent startup.
- The background sync worker starts automatically when the FastAPI app starts.

## Development Tip

If you only want to inspect the API contract quickly, start the server and use the Swagger UI at `/docs`.