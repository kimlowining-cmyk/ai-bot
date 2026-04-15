import os
import traceback

from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from openai import OpenAI

from database import SessionLocal, engine
from models import Base, ChatMessage, AISettings

Base.metadata.create_all(bind=engine)

app = FastAPI()
print("OPENROUTER_API_KEY exists:", bool(os.getenv("OPENROUTER_API_KEY")))

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY", "").replace("\r", "").replace("\n", "").strip(),
    timeout=60.0,
)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ChatRequest(BaseModel):
    user_id: str
    message: str
    system_prompt: str | None = None

class SettingsUpdate(BaseModel):
    system_prompt: str

def get_or_create_settings(db: Session):
    settings = db.query(AISettings).first()
    if not settings:
        settings = AISettings(
            system_prompt="You are a professional English sales assistant."
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

from fastapi import FastAPI, Request

app = FastAPI()

VERIFY_TOKEN = "abc123"

# ✅ 这里加（位置1：推荐放在最上面）
@app.get("/webhook")
async def verify(request: Request):
    params = request.query_params

    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return int(params.get("hub.challenge"))

    return {"error": "verify failed"}


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    print(data)
    return {"status": "ok"}

@app.post("/chat")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    try:
        settings = get_or_create_settings(db)
        system_prompt = req.system_prompt if req.system_prompt else settings.system_prompt

        user_msg = ChatMessage(
            user_id=req.user_id,
            role="user",
            message=req.message
        )
        db.add(user_msg)
        db.commit()

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""
You are a professional stock trading assistant.

Your purpose:
- Help users understand their trading problems
- Build trust through useful insights
- Guide them to join a trading group where they can learn more

Rules:
- Stay on topic (stock trading only)
- Never give generic life advice
- Never go off-topic
- Be practical, not theoretical
- Speak like an experienced trader

{system_prompt}
"""
                },
                {
                    "role": "user",
                    "content": req.message
                }
            ]
        )

        reply = response.choices[0].message.content

        bot_msg = ChatMessage(
            user_id=req.user_id,
            role="assistant",
            message=reply
        )
        db.add(bot_msg)
        db.commit()

        return {"reply": reply}

    except Exception as e:
        return {
            "error": str(e),
            "trace": traceback.format_exc()
        }

@app.get("/admin/settings")
def get_settings(db: Session = Depends(get_db)):
    settings = get_or_create_settings(db)
    return {"system_prompt": settings.system_prompt}

@app.post("/admin/settings")
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db)):
    settings = get_or_create_settings(db)
    settings.system_prompt = data.system_prompt
    db.commit()
    return {
        "message": "Settings updated successfully",
        "system_prompt": settings.system_prompt
    }

@app.get("/admin/messages")
def get_messages(db: Session = Depends(get_db)):
    messages = db.query(ChatMessage).order_by(ChatMessage.id.desc()).all()
    return [
        {
            "id": m.id,
            "user_id": m.user_id,
            "role": m.role,
            "message": m.message,
            "created_at": m.created_at
        }
        for m in messages
    ]
