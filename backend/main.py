from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent.graph import graph
from langchain_core.messages import HumanMessage, AIMessage
import uuid

app = FastAPI(title="AutoStream Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    session_id: str = None

class ChatResponse(BaseModel):
    reply: str
    intent: str
    lead_name: str | None
    lead_email: str | None
    lead_platform: str | None
    lead_captured: bool
    session_id: str


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    result = graph.invoke(
        {"messages": [HumanMessage(content=req.message)]},
        config=config
    )

    # ── FIX: Robust reply extraction ─────────────────────────────────────────
    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]

    if ai_messages:
        reply = ai_messages[-1].content
    elif result.get("lead_captured"):
        # Fallback if AIMessage wasn't appended but tool fired successfully
        name = result.get("lead_name", "there")
        email = result.get("lead_email", "")
        platform = result.get("lead_platform", "")
        reply = (
            f"🎉 You're officially in, {name}!\n\n"
            f"📧 We'll reach out to **{email}** within 24 hours.\n"
            f"🎬 Can't wait to see your **{platform}** content shine with AutoStream Pro! 🚀"
        )
    else:
        reply = "I'm here to help! Ask me about AutoStream's pricing, features, or getting started."

    return ChatResponse(
        reply=reply,
        intent=result.get("intent", "greeting"),
        lead_name=result.get("lead_name"),
        lead_email=result.get("lead_email"),
        lead_platform=result.get("lead_platform"),
        lead_captured=result.get("lead_captured", False),
        session_id=session_id
    )


# ── WhatsApp Webhook ──────────────────────────────────────────────────────────

@app.get("/webhook")
async def whatsapp_verify(request: Request):
    params = dict(request.query_params)
    verify_token = "YOUR_VERIFY_TOKEN"
    if params.get("hub.verify_token") == verify_token:
        return int(params["hub.challenge"])
    return {"error": "Invalid token"}


@app.post("/webhook")
async def whatsapp_incoming(request: Request):
    body = await request.json()
    try:
        entry = body["entry"][0]["changes"][0]["value"]
        msg_obj = entry["messages"][0]
        phone = msg_obj["from"]
        text = msg_obj["text"]["body"]

        config = {"configurable": {"thread_id": phone}}
        result = graph.invoke(
            {"messages": [HumanMessage(content=text)]},
            config=config
        )

        ai_msgs = [m for m in result["messages"] if isinstance(m, AIMessage)]
        reply = ai_msgs[-1].content if ai_msgs else "How can I help you today?"
        print(f"Reply to {phone}: {reply}")
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook error: {e}")
        return {"status": "error"}