import requests
from fastapi import FastAPI
from app.routes import user, mediroute, llmroute
from app.core.sync_automation import sync_all_users
import asyncio

app = FastAPI(
    title="The App Backend",
    version="1.0"
)

# user route
app.include_router(user.router, prefix="/user", tags=["User"])

# medical related route
app.include_router(mediroute.router, prefix="/med", tags=["Medicare"])
app.include_router(llmroute.router, prefix="/llm", tags=["LLM"])

# sync automation
@app.on_event("startup")
async def start_background_sync():
    asyncio.create_task(sync_all_users())