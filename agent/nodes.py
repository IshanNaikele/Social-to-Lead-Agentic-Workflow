import os
import re
import json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_huggingface import HuggingFaceEmbeddings

from agent.state import AgentState
from agent.tools import mock_lead_capture

load_dotenv()

# ── LLM Setup ──────────────────────────────────────────────────────────────────
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",                
    google_api_key=os.getenv("GOOGLE_API_KEY"),
)

# ── RAG Setup ──────────────────────────────────────────────────────────────────
def build_retriever():
    loader = TextLoader("knowledge_base/autostream_kb.md", encoding="utf-8")
    docs = loader.load()
    # FIX: chunk_size raised from 200 → 500 to prevent mid-plan splits.
    # e.g. "Pro Plan — $79/month" and its features now stay in the same chunk.
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = FAISS.from_documents(chunks, embeddings)
    return vectorstore.as_retriever(search_kwargs={"k": 3})

retriever = build_retriever()


# ── Helpers ────────────────────────────────────────────────────────────────────
def clean_value(value) -> str | None:
    if not value or value == "null":
        return None
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r'[*~`]', '', value).strip()
    return cleaned if cleaned else None


def is_valid_email(value: str) -> bool:
    """Basic email format check — must contain @ and a dot after it."""
    return bool(re.search(r'[^@]+@[^@]+\.[^@]+', value))


def safe_json_parse(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"```(?:json)?", "", raw).strip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[JSON Parse Error] Raw string was: {repr(raw[:200])} | Error: {e}")
        raise


# ── NODE 1: Intent Classification ──────────────────────────────────────────────
def intent_node(state: AgentState) -> AgentState:
    # Short-circuit: no LLM call needed after lead is captured
    if state.get("lead_captured"):
        return {**state, "intent": "post_capture"}

    last_msg = state["messages"][-1].content

    # FIX: Added few-shot examples to prevent "Write essay" → high_intent misclassification.
    # The old prompt had no examples so the LLM used active-verb heuristics ("write", "do")
    # and sometimes classified clearly off-topic requests as high_intent.
    prompt = f"""You are an intent classifier for AutoStream, a video editing SaaS.

Classify the user message into EXACTLY one of: greeting, inquiry, high_intent

Definitions:
- high_intent: user explicitly wants to buy, sign up, try, start, or subscribe to AutoStream
- inquiry: user is asking about AutoStream features, pricing, plans, refunds, or support
- greeting: anything else — casual chat, jokes, off-topic requests, personal questions, unrelated tasks

Few-shot examples (follow these strictly):
"Hi there" → greeting
"Write me an essay on patience" → greeting
"Write essay. Topic: AI" → greeting
"Tell me a joke" → greeting
"What is the Pro plan?" → inquiry
"How much does Basic cost?" → inquiry
"Do you offer refunds?" → inquiry
"I want to sign up for Pro" → high_intent
"Sign me up for my YouTube channel" → high_intent
"I want to try AutoStream" → high_intent
"Let's get started" → high_intent

Message to classify: "{last_msg}"

Respond ONLY with valid JSON, no markdown:
{{"intent": "inquiry", "reason": "user asked about pricing"}}"""

    try:
        result = llm.invoke(prompt)
        parsed = safe_json_parse(result.content)
        intent = parsed.get("intent", "greeting")
        if intent not in ("greeting", "inquiry", "high_intent"):
            intent = "greeting"
    except Exception as e:
        print(f"[Intent Error] {e}")
        intent = "greeting"

    return {**state, "intent": intent}


# ── NODE 2: RAG Retrieval ──────────────────────────────────────────────────────
def rag_node(state: AgentState) -> AgentState:
    query = state["messages"][-1].content
    docs = retriever.invoke(query)
    context = "\n".join([d.page_content for d in docs])
    return {**state, "rag_context": context}


# ── NODE 3: General Chat ───────────────────────────────────────────────────────
def chat_node(state: AgentState) -> AgentState:
    context = state.get("rag_context", "")

    if context:
        lead_captured = state.get("lead_captured", False)
        no_signup_note = (
            " The user has already signed up — do NOT prompt them to sign up again."
            if lead_captured else ""
        )
        system = f"""You are a friendly sales assistant for AutoStream, a video editing SaaS.

RULES:
1. Answer using ONLY the provided knowledge base — do not invent any details.
2. When asked about pricing or plans, you MUST list EVERY plan with ALL its features.
   Format each plan clearly like:
   Basic Plan — $29/month: 10 videos/month, 720p resolution
   Pro Plan — $79/month: Unlimited videos, 4K resolution, AI captions, 24/7 support
3. Never give a partial answer — always include both the price AND the features together.
4. Keep the tone friendly and concise.{no_signup_note}"""
        user_prompt = f"Knowledge base:\n{context}\n\nUser: {state['messages'][-1].content}"

    elif state.get("lead_captured"):
        system = """You are a helpful support assistant for AutoStream, a video editing SaaS.
The user has already signed up. Do NOT mention sign-up or repeat any confirmation message.
Answer whatever they ask naturally and concisely."""
        user_prompt = state["messages"][-1].content

    else:
        system = """You are a friendly, witty sales assistant for AutoStream — an AI-powered
video editing SaaS for content creators. Keep replies concise.
If the user asks you to write essays, poems, or anything unrelated to AutoStream,
politely decline and redirect the conversation to AutoStream."""
        user_prompt = state["messages"][-1].content

    result = llm.invoke([
        {"role": "system", "content": system},
        {"role": "user",   "content": user_prompt}
    ])

    return {
        **state,
        "rag_context": None,
        "messages": state["messages"] + [AIMessage(content=result.content)]
    }


# ── NODE 4: Slot Filling ───────────────────────────────────────────────────────
def slot_fill_node(state: AgentState) -> AgentState:
    already_have = {
        "name":     state.get("lead_name"),
        "email":    state.get("lead_email"),
        "platform": state.get("lead_platform"),
    }

    # Skip LLM call if all fields are already collected
    if all(already_have.values()):
        return state

    recent_messages = state["messages"][-6:]
    history_lines = []
    for m in recent_messages:
        role = "User" if isinstance(m, HumanMessage) else "Agent"
        history_lines.append(f"{role}: {m.content}")
    history = "\n".join(history_lines)

    missing_fields = [k for k, v in already_have.items() if not v]
    fields_instruction = ", ".join(missing_fields)

    # FIX: Added correction detection. If user says "actually", "wait", "change",
    # "use this instead" etc., the LLM should return the NEW value, not the old one.
    # The `or state.get(...)` fallback below then won't overwrite it with stale data
    # because clean_value will return the new value first.
    prompt = f"""Extract lead information from this conversation.
We are still missing: {fields_instruction}

IMPORTANT RULES:
1. Scan ALL messages including the very first signup message — users often mention
   their platform there (e.g. "sign up for my YouTube channel" → platform = YouTube).
2. If the user corrects a previously given value (e.g. "actually use ishan@work.com",
   "wait, change my email", "use this instead"), return the CORRECTED/NEWER value.
3. For email: copy it EXACTLY — do not change any character. Reject anything without @.
4. For platform: content platforms only (YouTube, Instagram, TikTok, Twitter, Facebook).
   Ignore messaging apps like WhatsApp or Telegram.
   If multiple mentioned, prefer: YouTube > Instagram > TikTok > Twitter > Facebook.
5. For name: accept full or partial ("I am John", "my name is Sarah", "I'm Mike").

Conversation (recent turns):
{history}

Return ONLY valid JSON, no markdown:
{{"name": "Full Name", "email": "email@example.com", "platform": "YouTube"}}

Use JSON null (not the string "null") for anything genuinely not found."""

    try:
        result = llm.invoke(prompt)
        data = safe_json_parse(result.content)
    except Exception as e:
        print(f"[Slot Fill Error] {e}")
        data = {"name": None, "email": None, "platform": None}

    # FIX: Email gets an extra validation step — clean_value alone doesn't
    # catch "not an email" strings that happen to parse without errors.
    raw_email = clean_value(data.get("email"))
    validated_email = raw_email if (raw_email and is_valid_email(raw_email)) else None

    return {
        **state,
        "lead_name":     clean_value(data.get("name"))     or state.get("lead_name"),
        "lead_email":    validated_email                    or state.get("lead_email"),
        "lead_platform": clean_value(data.get("platform")) or state.get("lead_platform"),
    }


# ── NODE 5: Ask for Lead Info ──────────────────────────────────────────────────
def ask_lead_info_node(state: AgentState) -> AgentState:
    missing_parts = []

    if not state.get("lead_name"):
        missing_parts.append("your **full name**")
    if not state.get("lead_email"):
        missing_parts.append("your **email address**")
    if not state.get("lead_platform"):
        missing_parts.append("your **main creator platform** (YouTube, Instagram, TikTok, etc.)")

    # Safety: if nothing is missing, don't append a message
    if not missing_parts:
        return state

    has_any = any([state.get("lead_name"), state.get("lead_email"), state.get("lead_platform")])

    if not has_any:
        question = (
            "Awesome, let's get you onboarded to AutoStream Pro! 🎬\n\n"
            "I just need a few quick details:\n"
            + "\n".join(["• " + p for p in missing_parts])
            + "\n\nFeel free to share them all in one message!"
        )
    else:
        if len(missing_parts) == 1:
            question = f"Almost there! Just one more thing — could you share {missing_parts[0]}?"
        else:
            fields_str = " and ".join(missing_parts)
            question = f"Thanks! Still need {fields_str} to complete your signup."

    return {
        **state,
        "messages": state["messages"] + [AIMessage(content=question)]
    }


# ── NODE 6: Lead Capture ───────────────────────────────────────────────────────
def lead_capture_node(state: AgentState) -> AgentState:
    # Guard: if somehow we arrive here with missing fields, fall back to ask
    if not all([state.get("lead_name"), state.get("lead_email"), state.get("lead_platform")]):
        print("[Lead Capture] Guard triggered — missing fields, routing to ask_lead")
        return ask_lead_info_node(state)

    try:
        result = mock_lead_capture(
            name=state["lead_name"],
            email=state["lead_email"],
            platform=state["lead_platform"]
        )
        print(f"[Tool Result] {result}")
    except Exception as e:
        print(f"[Lead Capture Tool Error] {e}")

    confirmation = (
        f"🎉 **You're officially in, {state['lead_name']}!**\n\n"
        f"📧 We'll reach out to **{state['lead_email']}** within 24 hours.\n"
        f"🎬 Can't wait to see your **{state['lead_platform']}** content shine with AutoStream Pro!\n\n"
        f"Feel free to ask me anything else about AutoStream 🚀"
    )

    return {
        **state,
        "lead_captured": True,
        "messages": state["messages"] + [AIMessage(content=confirmation)]
    }