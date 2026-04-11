import streamlit as st
import requests
import uuid
import time

API_URL = "http://localhost:8000/chat"

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AutoStream AI",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Custom CSS — Dark Cinematic Theme ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

/* ── Root & Background ── */
:root {
    --bg-primary: #0a0a0f;
    --bg-secondary: #111118;
    --bg-card: #16161f;
    --bg-input: #1c1c28;
    --accent: #e63946;
    --accent-soft: rgba(230, 57, 70, 0.15);
    --accent-glow: rgba(230, 57, 70, 0.4);
    --gold: #f4a261;
    --green: #2ec4b6;
    --green-soft: rgba(46, 196, 182, 0.12);
    --text-primary: #f0f0f5;
    --text-secondary: #8888aa;
    --text-muted: #55556a;
    --border: rgba(255,255,255,0.06);
    --border-accent: rgba(230, 57, 70, 0.3);
    --shadow: 0 8px 32px rgba(0,0,0,0.4);
    --radius: 16px;
}

/* ── Global Reset ── */
html, body, .stApp {
    background-color: var(--bg-primary) !important;
    font-family: 'DM Sans', sans-serif;
    color: var(--text-primary);
}

.stApp {
    background: 
        radial-gradient(ellipse 80% 50% at 20% 0%, rgba(230,57,70,0.06) 0%, transparent 60%),
        radial-gradient(ellipse 60% 40% at 80% 100%, rgba(46,196,182,0.04) 0%, transparent 60%),
        var(--bg-primary);
}

/* ── Hide Streamlit Junk ── */
#MainMenu, footer, header, .stDeployButton { display: none !important; }
.block-container { padding: 0 !important; max-width: 100% !important; }
section[data-testid="stSidebar"] { display: none !important; }

/* ── Layout Columns ── */
[data-testid="column"] { padding: 0 !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--text-muted); border-radius: 2px; }

/* ── Chat Input — comprehensive fix for typed text visibility ── */
/* Target the outer wrapper */
.stChatInput > div {
    background: var(--bg-input) !important;
    border: 1px solid var(--border) !important;
    border-radius: 14px !important;
    transition: border-color 0.2s;
}
.stChatInput > div:focus-within {
    border-color: var(--border-accent) !important;
    box-shadow: 0 0 0 3px var(--accent-soft) !important;
}

/* Target the BaseWeb textarea element — this is the key fix */
[data-baseweb="textarea"] textarea,
[data-baseweb="base-input"] textarea,
.stChatInput textarea,
div[data-testid="stChatInput"] textarea,
div[data-testid="stChatInputTextArea"] textarea {
    color: #f0f0f5 !important;
    -webkit-text-fill-color: #f0f0f5 !important;
    caret-color: #e63946 !important;
    background-color: transparent !important;
    background: transparent !important;
    opacity: 1 !important;
}

/* Also target the shadow host wrappers BaseWeb uses */
[data-baseweb="textarea"],
[data-baseweb="base-input"] {
    background: transparent !important;
    color: #f0f0f5 !important;
}

/* Placeholder */
.stChatInput textarea::placeholder,
[data-baseweb="textarea"] textarea::placeholder {
    color: var(--text-muted) !important;
    -webkit-text-fill-color: var(--text-muted) !important;
    opacity: 1 !important;
}

[data-testid="stChatInput"] {
    background-color: var(--bg-input) !important;
    border-radius: 14px;
}

div[data-testid="stChatInput"] > div {
    background-color: var(--bg-input) !important;
}

/* ── Chat Messages ── */
[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: 4px 0 !important;
    color: #f0f0f5 !important;
}

/* Force all text inside chat messages to be visible */
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] div,
[data-testid="stChatMessage"] span {
    color: #f0f0f5 !important;
}

/* Streamlit injects its own markdown wrapper — override it */
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
    color: #f0f0f5 !important;
}

/* ── Spinner ── */
.stSpinner > div { border-top-color: var(--accent) !important; }

/* ── Buttons ── */
.stButton > button {
    background: var(--accent) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    background: #c1121f !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px var(--accent-glow) !important;
}

/* ── Progress Bar ── */
.stProgress > div > div > div {
    background: linear-gradient(90deg, var(--accent), var(--gold)) !important;
    border-radius: 4px !important;
}
.stProgress > div > div {
    background: var(--bg-input) !important;
    border-radius: 4px !important;
}

/* ── Remove white backgrounds everywhere ── */
div[data-testid="stVerticalBlock"] { background: transparent !important; }
</style>
""", unsafe_allow_html=True)

# ── Session State Bootstrap ───────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "lead_state" not in st.session_state:
    st.session_state.lead_state = {
        "intent": None,
        "lead_name": None,
        "lead_email": None,
        "lead_platform": None,
        "lead_captured": False,
    }
if "show_celebration" not in st.session_state:
    st.session_state.show_celebration = False
if "celebration_done" not in st.session_state:
    st.session_state.celebration_done = False

# ── Layout: Chat | State Panel ────────────────────────────────────────────────
col_chat, col_state = st.columns([3, 1], gap="small")


# ══════════════════════════════════════════════════════════════════════════════
# LEFT — CHAT PANEL
# ══════════════════════════════════════════════════════════════════════════════
with col_chat:

    # Header
    st.markdown("""
    <div style="
        padding: 28px 32px 20px 32px;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        margin-bottom: 8px;
    ">
        <div style="display:flex; align-items:center; gap:14px; margin-bottom:6px;">
            <div style="
                width:44px; height:44px;
                background: linear-gradient(135deg, #e63946, #c1121f);
                border-radius:12px;
                display:flex; align-items:center; justify-content:center;
                font-size:20px;
                box-shadow: 0 4px 16px rgba(230,57,70,0.4);
            ">🎬</div>
            <div>
                <div style="
                    font-family:'Syne',sans-serif;
                    font-size:1.4rem;
                    font-weight:800;
                    color:#f0f0f5;
                    letter-spacing:-0.02em;
                    line-height:1;
                ">AutoStream <span style="color:#e63946;">AI</span></div>
                <div style="
                    font-size:0.75rem;
                    color:#8888aa;
                    margin-top:3px;
                    font-weight:300;
                ">Powered by Gemini 2.0 · LangGraph Agent</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Chat container
    chat_container = st.container(height=520)

    with chat_container:
        if not st.session_state.messages:
            st.markdown("""
            <div style="
                display:flex; flex-direction:column; align-items:center;
                justify-content:center; height:100%; padding:40px;
                text-align:center;
            ">
                <div style="font-size:3rem; margin-bottom:16px;">🎬</div>
                <div style="
                    font-family:'Syne',sans-serif;
                    font-size:1.2rem; font-weight:700;
                    color:#f0f0f5; margin-bottom:8px;
                ">Welcome to AutoStream AI</div>
                <div style="color:#8888aa; font-size:0.9rem; max-width:320px; line-height:1.6;">
                    Ask about pricing, plans, or just say hi.<br>
                    I'm here to help you get started.
                </div>
                <div style="
                    margin-top:24px; display:flex; gap:8px; flex-wrap:wrap; justify-content:center;
                ">
                    <div style="
                        background:rgba(230,57,70,0.1); border:1px solid rgba(230,57,70,0.2);
                        border-radius:20px; padding:6px 14px; font-size:0.8rem; color:#e63946;
                    ">💰 Pricing plans</div>
                    <div style="
                        background:rgba(230,57,70,0.1); border:1px solid rgba(230,57,70,0.2);
                        border-radius:20px; padding:6px 14px; font-size:0.8rem; color:#e63946;
                    ">🚀 Sign up for Pro</div>
                    <div style="
                        background:rgba(230,57,70,0.1); border:1px solid rgba(230,57,70,0.2);
                        border-radius:20px; padding:6px 14px; font-size:0.8rem; color:#e63946;
                    ">❓ FAQs & policies</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        for msg in st.session_state.messages:
            is_user = msg["role"] == "user"
            if is_user:
                with st.chat_message("user", avatar="👤"):
                    st.markdown(f"""
                    <div style="
                        background: rgba(230,57,70,0.1);
                        border: 1px solid rgba(230,57,70,0.15);
                        border-radius: 14px 14px 4px 14px;
                        padding: 12px 16px;
                        color: #f0f0f5 !important;
                        font-size: 0.92rem;
                        line-height: 1.6;
                        display: inline-block;
                        max-width: 85%;
                    ">{msg["content"]}</div>
                    """, unsafe_allow_html=True)
            else:
                with st.chat_message("assistant", avatar="🎬"):
                    st.markdown(f"""
                    <div style="
                        background: rgba(255,255,255,0.04);
                        border: 1px solid rgba(255,255,255,0.08);
                        border-radius: 14px 14px 14px 4px;
                        padding: 12px 16px;
                        color: #ddddf0;
                        font-size: 0.92rem;
                        line-height: 1.7;
                        display: inline-block;
                        max-width: 90%;
                    ">{msg["content"]}</div>
                    """, unsafe_allow_html=True)

    # Input area
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    col_input, col_reset = st.columns([6, 1])
    with col_input:
        user_input = st.chat_input("Ask about pricing, plans, or sign up for Pro...")
    with col_reset:
        if st.button("↺ Reset", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.lead_state = {
                "intent": None, "lead_name": None,
                "lead_email": None, "lead_platform": None, "lead_captured": False
            }
            st.session_state.show_celebration = False
            st.session_state.celebration_done = False
            st.rerun()

    # Handle input
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.spinner(""):
            try:
                response = requests.post(API_URL, json={
                    "message": user_input,
                    "session_id": st.session_state.session_id
                }, timeout=30)
                data = response.json()
                error = None
            except requests.exceptions.ConnectionError:
                data = None
                error = "⚠️ Cannot reach backend. Make sure FastAPI is running on port 8000."
            except Exception as e:
                data = None
                error = f"⚠️ Error: {str(e)}"

        if error:
            st.session_state.messages.append({"role": "assistant", "content": error})
        else:
            reply = data["reply"]
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.session_state.session_id = data["session_id"]
            st.session_state.lead_state = {
                "intent": data["intent"],
                "lead_name": data["lead_name"],
                "lead_email": data["lead_email"],
                "lead_platform": data["lead_platform"],
                "lead_captured": data["lead_captured"],
            }
            if data["lead_captured"] and not st.session_state.get("celebration_done"):
                st.session_state.show_celebration = True
                st.session_state.celebration_done = True

        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# RIGHT — STATE PANEL
# ══════════════════════════════════════════════════════════════════════════════
with col_state:
    st.markdown("""
    <div style="
        padding: 24px 20px 16px 20px;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        margin-bottom: 4px;
    ">
        <div style="
            font-family:'Syne',sans-serif;
            font-size:0.85rem; font-weight:700;
            color:#8888aa; letter-spacing:0.1em;
            text-transform:uppercase;
        ">🧠 Agent State</div>
        <div style="font-size:0.72rem; color:#55556a; margin-top:3px;">
            Live view · updates per turn
        </div>
    </div>
    """, unsafe_allow_html=True)

    ls = st.session_state.lead_state

    # ── Intent Badge ──────────────────────────────────────────────────────────
    intent = ls.get("intent") or "idle"
    intent_config = {
        "greeting":    {"icon": "💬", "label": "Casual Chat",   "color": "#f4a261", "bg": "rgba(244,162,97,0.1)"},
        "inquiry":     {"icon": "🔍", "label": "Inquiring",     "color": "#4cc9f0", "bg": "rgba(76,201,240,0.1)"},
        "high_intent": {"icon": "🔥", "label": "High Intent",   "color": "#2ec4b6", "bg": "rgba(46,196,182,0.1)"},
        "idle":        {"icon": "⏳", "label": "Waiting",       "color": "#8888aa", "bg": "rgba(136,136,170,0.08)"},
    }
    ic = intent_config.get(intent, intent_config["idle"])

    st.markdown(f"""
    <div style="
        margin: 12px 16px;
        background: {ic['bg']};
        border: 1px solid {ic['color']}33;
        border-radius: 12px;
        padding: 12px 14px;
    ">
        <div style="font-size:0.7rem; color:#8888aa; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.08em;">Detected Intent</div>
        <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:1.1rem;">{ic['icon']}</span>
            <span style="
                font-family:'Syne',sans-serif;
                font-size:0.9rem; font-weight:700;
                color:{ic['color']};
            ">{ic['label']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Lead Progress ─────────────────────────────────────────────────────────
    st.markdown("""
    <div style="margin: 16px 16px 8px 16px;">
        <div style="font-size:0.7rem; color:#8888aa; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:10px;">
            Lead Qualification
        </div>
    </div>
    """, unsafe_allow_html=True)

    fields = [
        ("lead_name",     "👤", "Name"),
        ("lead_email",    "📧", "Email"),
        ("lead_platform", "📱", "Platform"),
    ]

    filled_count = 0
    for key, icon, label in fields:
        value = ls.get(key)
        if value:
            filled_count += 1
            st.markdown(f"""
            <div style="
                margin: 4px 16px;
                background: rgba(46,196,182,0.08);
                border: 1px solid rgba(46,196,182,0.2);
                border-radius: 10px;
                padding: 10px 12px;
                display: flex;
                align-items: flex-start;
                gap: 8px;
            ">
                <span style="font-size:0.9rem; margin-top:1px;">{icon}</span>
                <div>
                    <div style="font-size:0.68rem; color:#2ec4b6; text-transform:uppercase; letter-spacing:0.06em;">{label}</div>
                    <div style="font-size:0.82rem; color:#f0f0f5; margin-top:2px; word-break:break-all;">{value}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="
                margin: 4px 16px;
                background: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 10px;
                padding: 10px 12px;
                display: flex;
                align-items: center;
                gap: 8px;
                opacity: 0.5;
            ">
                <span style="font-size:0.9rem;">{icon}</span>
                <div>
                    <div style="font-size:0.68rem; color:#55556a; text-transform:uppercase; letter-spacing:0.06em;">{label}</div>
                    <div style="font-size:0.78rem; color:#55556a; margin-top:2px;">Not collected</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Progress bar
    st.markdown("<div style='margin: 12px 16px 4px 16px;'>", unsafe_allow_html=True)
    st.progress(filled_count / 3)
    st.markdown(f"""
    <div style="
        font-size:0.72rem; color:#8888aa;
        margin: 2px 16px 0 16px;
        text-align:right;
    ">{filled_count}/3 fields</div>
    """, unsafe_allow_html=True)

    # ── Lead Captured Banner ──────────────────────────────────────────────────
    if ls.get("lead_captured"):
        if st.session_state.show_celebration:
            st.balloons()
            st.session_state.show_celebration = False

        st.markdown("""
        <div style="
            margin: 16px 16px 8px 16px;
            background: linear-gradient(135deg, rgba(46,196,182,0.15), rgba(46,196,182,0.05));
            border: 1px solid rgba(46,196,182,0.35);
            border-radius: 12px;
            padding: 14px;
            text-align: center;
        ">
            <div style="font-size:1.5rem; margin-bottom:6px;">🎉</div>
            <div style="
                font-family:'Syne',sans-serif;
                font-size:0.85rem; font-weight:700;
                color:#2ec4b6;
            ">Lead Captured!</div>
            <div style="font-size:0.72rem; color:#8888aa; margin-top:4px;">
                mock_lead_capture() executed
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Session Info ──────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="
        margin: 16px 16px 8px 16px;
        padding-top: 14px;
        border-top: 1px solid rgba(255,255,255,0.05);
    ">
        <div style="font-size:0.68rem; color:#55556a;">
            Session ID<br>
            <span style="color:#8888aa; font-family:monospace; font-size:0.65rem; word-break:break-all;">
                {st.session_state.session_id[:24]}...
            </span>
        </div>
        <div style="font-size:0.68rem; color:#55556a; margin-top:8px;">
            {len(st.session_state.messages)} messages in context
        </div>
    </div>
    """, unsafe_allow_html=True)