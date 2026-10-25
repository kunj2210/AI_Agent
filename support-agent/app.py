"""
app.py — Streamlit UI for the ShopEasy AI Customer Support Agent.

Theme: Clean modern White & Blue design system.
Tab 1: Customer Chat  — real-time resolution with structured badges and JSON inspector.
Tab 2: Admin Settings — live-edit agent parameters & knowledge base file upload with dynamic re-indexing.
"""

import html
import io
import json
import os
import yaml
import streamlit as st
import agent
from retriever import get_retriever

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ShopEasy Support Hub",
    page_icon="◈",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Paths ──────────────────────────────────────────────────────────────────────
AGENT_CFG_PATH = "config/agent_config.yaml"
KB_FOLDER      = "knowledge_base"

# ── Global Custom CSS (White & Blue Modern Theme) ──────────────────────────────
CUSTOM_CSS = """
<style>
/* ── Reset & Base Font ── */
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"], [data-testid="stAppViewContainer"], .main {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background-color: #ffffff !important;
    color: #0f172a !important;
}

/* ── Hide Streamlit Default Chrome ── */
header[data-testid="stHeader"] {
    background-color: #ffffff !important;
    border-bottom: 1px solid #f1f5f9 !important;
}

[data-testid="stToolbar"] {
    right: 1.5rem !important;
}

/* ── App Header ── */
.app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.5rem;
    background: #ffffff;
    border: 1.5px solid #e2e8f0;
    border-radius: 16px;
    box-shadow: 0 4px 20px rgba(37, 99, 235, 0.06);
}

.header-left {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.header-logo {
    width: 44px;
    height: 44px;
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 12px;
    font-size: 1.4rem;
    font-weight: 700;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
}

.header-title {
    font-size: 1.35rem !important;
    font-weight: 700 !important;
    color: #0f172a !important;
    margin: 0 !important;
    line-height: 1.2 !important;
}

.header-subtitle {
    font-size: 0.85rem !important;
    color: #64748b !important;
    margin: 0.15rem 0 0 0 !important;
}

.status-indicator {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.35rem 0.85rem;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 9999px;
    font-size: 0.78rem;
    font-weight: 600;
    color: #1d4ed8;
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2);
}

/* ── Tabs Styling ── */
div[data-testid="stTabs"] {
    margin-bottom: 1.5rem;
}

div[data-baseweb="tab-list"] {
    background-color: #f8fafc !important;
    border-radius: 12px !important;
    padding: 4px !important;
    border: 1px solid #e2e8f0 !important;
    gap: 4px !important;
}

div[data-baseweb="tab"] {
    border-radius: 8px !important;
    padding: 8px 18px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    color: #64748b !important;
    border: none !important;
    background: transparent !important;
    transition: all 0.2s ease !important;
}

div[data-baseweb="tab"][aria-selected="true"] {
    background-color: #2563eb !important;
    color: #ffffff !important;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25) !important;
}

div[data-baseweb="tab-border"] {
    display: none !important;
}

/* ── Chat Message Container (ALL MESSAGES BLUE, ZERO INNER BORDERS) ── */
[data-testid="stChatMessage"] {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    gap: 0.95rem !important;
    border-radius: 18px !important;
    margin-bottom: 1.25rem !important;
    padding: 0.85rem 1.25rem !important;
    box-shadow: 0 4px 16px rgba(15, 23, 42, 0.08) !important;
    transition: all 0.2s ease !important;
    background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%) !important;
    border: 1.5px solid #3b82f6 !important;
}

/* User Messages: Royal Blue Bubble, center-aligned (single-line) */
div[data-testid="stChatMessage"]:has([aria-label*="user"]),
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    border: 1.5px solid #60a5fa !important;
    box-shadow: 0 4px 16px rgba(37, 99, 235, 0.2) !important;
    border-radius: 18px 18px 4px 18px !important;
    max-width: 82% !important;
    margin-left: auto !important;
    margin-right: 0 !important;
    align-items: center !important;
}

/* Assistant Messages: Deep Sapphire Blue Card, icon pins to first text line */
div[data-testid="stChatMessage"]:has([aria-label*="assistant"]),
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background: linear-gradient(145deg, #0f2b5c 0%, #1e3a8a 100%) !important;
    border: 1.5px solid #3b82f6 !important;
    box-shadow: 0 6px 20px rgba(15, 43, 92, 0.24) !important;
    border-radius: 18px 18px 18px 4px !important;
    max-width: 95% !important;
    margin-left: 0 !important;
    margin-right: auto !important;
    align-items: flex-start !important;
}

/* ── Content block: fills remaining width ── */
[data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {
    flex: 1 1 0% !important;
    min-width: 0 !important;
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    outline: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* For assistant messages, align the first text line center (6px + 12px = 18px) with the 36px avatar center (18px) */
div[data-testid="stChatMessage"]:has([aria-label*="assistant"]) [data-testid="stChatMessageContent"] {
    padding-top: 6px !important;
}

/* ── Zero out ALL internal Streamlit padding and margins that cause shifts ── */
[data-testid="stChatMessage"] [data-testid="stVerticalBlock"] {
    padding: 0 !important;
    margin: 0 !important;
    gap: 0 !important;
}

[data-testid="stChatMessage"] [data-testid="stElementContainer"] {
    padding: 0 !important;
    margin: 0 !important;
}

/* STRICTLY eliminate ALL internal borders and backgrounds */
[data-testid="stChatMessage"] div[aria-label*="Chat message"],
[data-testid="stChatMessage"] [class*="exttvjz1"],
[data-testid="stChatMessage"] [class*="st-emotion-cache"],
[data-testid="stChatMessage"] [data-testid="stMarkdown"] {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    border-width: 0 !important;
    outline: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* CRITICAL: Overwrite Streamlit's default -16px / -1rem negative margin on stMarkdownContainer */
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    outline: none !important;
    box-shadow: none !important;
    margin: 0 !important;
    margin-bottom: 0 !important;
    padding: 0 !important;
}

/* Typography inside messages */
[data-testid="stChatMessage"] p {
    color: #ffffff !important;
    font-size: 0.96rem !important;
    line-height: 1.5 !important;
    margin: 0 !important;
    padding: 0 !important;
    letter-spacing: 0.01em !important;
}

/* ── Avatar styling ── */
[data-testid="stChatMessage"] > div[aria-hidden="true"] {
    width: 36px !important;
    height: 36px !important;
    min-width: 36px !important;
    max-width: 36px !important;
    border-radius: 50% !important;
    background: #ffffff !important;
    border: 2px solid #bfdbfe !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12) !important;
    flex-shrink: 0 !important;
    align-self: center !important;
    margin: 0 !important;
    padding: 0 !important;
    font-size: 1.1rem !important;
    line-height: 1 !important;
    overflow: hidden !important;
}

/* User avatar: vertically centered with the message bubble */
div[data-testid="stChatMessage"]:has([aria-label*="user"]) > div[aria-hidden="true"],
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) > div[aria-hidden="true"] {
    align-self: center !important;
    margin: 0 !important;
}

/* Assistant avatar: pins cleanly to top and aligns with first line of text */
div[data-testid="stChatMessage"]:has([aria-label*="assistant"]) > div[aria-hidden="true"],
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) > div[aria-hidden="true"] {
    align-self: flex-start !important;
    margin: 0 !important;
    margin-top: 0 !important;
}

[data-testid="stChatMessage"] > div[aria-hidden="true"] * {
    background: transparent !important;
    font-size: 1.1rem !important;
    line-height: 1 !important;
}

/* Hide Streamlit dev banner */
[data-testid="stNotification"] {
    display: none !important;
}

/* ── Modern Badges (Translucent light blue on deep blue messages) ── */
.badge-container {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    margin-top: 1rem;
    padding-top: 0.85rem;
    border-top: 1px solid rgba(255, 255, 255, 0.18);
}


.badge-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.38rem 0.95rem;
    border-radius: 9999px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    backdrop-filter: blur(6px);
}

.badge-cat {
    background: rgba(255, 255, 255, 0.16) !important;
    color: #ffffff !important;
    border: 1.2px solid rgba(255, 255, 255, 0.35);
}

.badge-pri-low {
    background: rgba(56, 189, 248, 0.22) !important;
    color: #e0f2fe !important;
    border: 1.2px solid rgba(125, 211, 252, 0.5);
}

.badge-pri-medium {
    background: rgba(245, 158, 11, 0.24) !important;
    color: #fef3c7 !important;
    border: 1.2px solid rgba(251, 191, 36, 0.5);
}

.badge-pri-high, .badge-pri-urgent {
    background: rgba(239, 68, 68, 0.28) !important;
    color: #fee2e2 !important;
    border: 1.2px solid rgba(248, 113, 113, 0.55);
}

.badge-esc-false {
    background: rgba(16, 185, 129, 0.25) !important;
    color: #d1fae5 !important;
    border: 1.2px solid rgba(52, 211, 153, 0.5);
}

.badge-esc-true {
    background: rgba(239, 68, 68, 0.38) !important;
    color: #ffffff !important;
    border: 1.2px solid #f87171;
}

/* ── Structured JSON Expander (High Contrast Card) ── */
[data-testid="stChatMessage"] details,
[data-testid="stChatMessage"] [data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1.5px solid #bfdbfe !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.14) !important;
    margin-top: 1.15rem !important;
    margin-bottom: 0.25rem !important;
    overflow: hidden !important;
}

[data-testid="stChatMessage"] [data-testid="stExpander"] summary {
    background: #eff6ff !important;
    color: #1e40af !important;
    font-weight: 700 !important;
    font-size: 0.85rem !important;
    padding: 0.65rem 1rem !important;
    border-bottom: 1px solid #dbeafe !important;
}

[data-testid="stChatMessage"] [data-testid="stExpander"] summary:hover {
    background: #dbeafe !important;
    color: #1d4ed8 !important;
}

[data-testid="stChatMessage"] [data-testid="stExpander"] summary span,
[data-testid="stChatMessage"] [data-testid="stExpander"] summary p {
    color: #1e40af !important;
}

[data-testid="stChatMessage"] [data-testid="stExpander"] summary svg {
    fill: #1e40af !important;
}

[data-testid="stChatMessage"] [data-testid="stExpander"] div[data-testid="stJson"] {
    background: #f8fafc !important;
    padding: 0.9rem !important;
    border-radius: 8px !important;
    border: 1px solid #e2e8f0 !important;
    margin: 0.65rem !important;
}

[data-testid="stChatMessage"] [data-testid="stExpander"] div[data-testid="stJson"] * {
    color: #0f172a !important;
}



/* ── Chat Input Bar ── */
[data-testid="stBottomBlockContainer"] {
    background-color: #ffffff !important;
    border-top: 1px solid #e2e8f0 !important;
    padding: 1rem 0 !important;
}

[data-testid="stChatInput"] {
    border-radius: 14px !important;
    border: 1.5px solid #cbd5e1 !important;
    background-color: #ffffff !important;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.05) !important;
    transition: all 0.2s ease !important;
}

[data-testid="stChatInput"]:focus-within {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15) !important;
}

[data-testid="stChatInput"] textarea {
    color: #0f172a !important;
    font-family: inherit !important;
}

[data-testid="stChatInput"] button {
    background-color: #2563eb !important;
    color: #ffffff !important;
    border-radius: 8px !important;
}

[data-testid="stChatInput"] button:hover {
    background-color: #1d4ed8 !important;
}

/* ── Buttons ── */
div.stButton > button {
    background-color: #ffffff !important;
    color: #2563eb !important;
    border: 1.5px solid #bfdbfe !important;
    border-radius: 10px !important;
    padding: 0.45rem 1.1rem !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    transition: all 0.2s ease !important;
}

div.stButton > button:hover {
    background-color: #eff6ff !important;
    border-color: #2563eb !important;
    color: #1d4ed8 !important;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.15) !important;
}

/* Form Submit Button: Solid Blue */
div.stFormSubmitButton > button {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 0.55rem 1.4rem !important;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25) !important;
}

div.stFormSubmitButton > button:hover {
    background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%) !important;
    box-shadow: 0 6px 16px rgba(37, 99, 235, 0.35) !important;
}

/* ── Form Inputs (Admin Tab) ── */
div[data-testid="stForm"] {
    background: #ffffff !important;
    border: 1.5px solid #e2e8f0 !important;
    border-radius: 16px !important;
    padding: 1.5rem !important;
    box-shadow: 0 4px 20px rgba(37, 99, 235, 0.04) !important;
}

div[data-baseweb="input"], div[data-baseweb="textarea"] {
    border-radius: 10px !important;
    border-color: #cbd5e1 !important;
    background-color: #ffffff !important;
}

div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
}

/* ── Knowledge Base Upload Zone ── */
[data-testid="stFileUploader"] {
    background: #f8fafc !important;
    border: 1.5px dashed #bfdbfe !important;
    border-radius: 14px !important;
    padding: 1rem !important;
    transition: all 0.2s ease !important;
}

[data-testid="stFileUploader"]:hover {
    border-color: #2563eb !important;
    background: #eff6ff !important;
}

/* ── Custom Cards & Badges ── */
.kb-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}

.kb-file-tag {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.25rem 0.65rem;
    margin: 0.2rem;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 500;
    color: #1e40af;
}
/* ── Custom HTML Chat Bubbles (replaces st.chat_message for full layout control) ── */
.msg-bubble {
    display: flex;
    flex-direction: row;
    gap: 0.95rem;
    margin-bottom: 1.25rem;
    padding: 0.85rem 1.25rem;
    transition: all 0.2s ease;
}

.user-bubble {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    border: 1.5px solid #60a5fa;
    border-radius: 18px 18px 4px 18px;
    max-width: 82%;
    margin-left: auto;
    margin-right: 0;
    align-items: center;
    box-shadow: 0 4px 16px rgba(37, 99, 235, 0.2);
}

.asst-bubble {
    background: linear-gradient(145deg, #0f2b5c 0%, #1e3a8a 100%);
    border: 1.5px solid #3b82f6;
    border-radius: 18px 18px 18px 4px;
    max-width: 95%;
    margin-left: 0;
    margin-right: auto;
    align-items: flex-start;
    box-shadow: 0 6px 20px rgba(15, 43, 92, 0.24);
}

.msg-avatar {
    width: 36px;
    height: 36px;
    min-width: 36px;
    border-radius: 50%;
    background: #ffffff;
    border: 2px solid #bfdbfe;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.1rem;
    line-height: 1;
    flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

.user-bubble .msg-avatar {
    align-self: center;
}

.asst-bubble .msg-avatar {
    align-self: flex-start;
    margin-top: 4px;
}

.msg-content {
    flex: 1;
    min-width: 0;
}

.msg-text {
    color: #ffffff;
    font-size: 0.96rem;
    line-height: 1.65;
    margin: 0;
    padding: 0;
    letter-spacing: 0.01em;
    word-break: break-word;
}

.json-inspector {
    background: #ffffff;
    border: 1.5px solid #bfdbfe;
    border-radius: 12px;
    margin-top: 1.15rem;
    overflow: hidden;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.14);
}

.json-inspector summary {
    background: #eff6ff;
    color: #1e40af;
    font-weight: 700;
    font-size: 0.85rem;
    padding: 0.65rem 1rem;
    cursor: pointer;
    border-bottom: 1px solid #dbeafe;
    list-style: none;
    user-select: none;
}

.json-inspector summary::-webkit-details-marker { display: none; }

.json-inspector summary:hover { background: #dbeafe; }

.json-body {
    background: #f8fafc;
    padding: 0.9rem;
    margin: 0;
    font-size: 0.78rem;
    color: #0f172a;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: 'JetBrains Mono', monospace;
    border-top: 1px solid #e2e8f0;
}
</style>
"""

# Inject custom styling
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── Session state defaults ─────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "responses" not in st.session_state:
    st.session_state.responses = []


# ── Badge helpers ──────────────────────────────────────────────────────────────
_CATEGORY_LABEL = {
    "billing":           "Billing & Payments",
    "delivery":          "Delivery & Shipping",
    "technical_support": "Technical Support",
    "refunds":           "Refunds & Returns",
    "account_access":    "Account Access",
    "other":             "General Inquiry",
}

def _badge_html(response: dict) -> str:
    """Return category, priority, and escalation badges as an HTML string."""
    category   = response.get("issue_category", "other")
    priority   = response.get("priority", "low").lower()
    escalation = response.get("escalation_required", False)
    cat_label  = _CATEGORY_LABEL.get(category, category.replace('_', ' ').title())
    esc_badge  = (
        "<span class='badge-pill badge-esc-true'>&#9650; Human Review Required</span>"
        if escalation else
        "<span class='badge-pill badge-esc-false'>&#10003; In-Policy Resolution</span>"
    )
    return f"""
    <div class="badge-container">
        <span class="badge-pill badge-cat">&#9672; {html.escape(cat_label)}</span>
        <span class="badge-pill badge-pri-{html.escape(priority)}">&#9679; Priority: {html.escape(priority.title())}</span>
        {esc_badge}
    </div>
    """


def _badge_row(response: dict) -> None:
    """Render category, priority, and escalation badges using styled HTML pills."""
    st.markdown(_badge_html(response), unsafe_allow_html=True)


def _render_user_bubble(content: str) -> None:
    """Render a user chat message as a fully-controlled custom HTML bubble."""
    safe = html.escape(content).replace("\n", "<br>")
    st.markdown(f"""
    <div class="msg-bubble user-bubble">
        <div class="msg-avatar">&#128100;</div>
        <div class="msg-text">{safe}</div>
    </div>
    """, unsafe_allow_html=True)


def _render_asst_bubble(reply: str, resp: dict | None = None) -> None:
    """Render an assistant chat message as a fully-controlled custom HTML bubble."""
    safe_reply = html.escape(reply).replace("\n", "<br>")
    badge_section = _badge_html(resp) if resp else ""
    json_section  = ""
    if resp:
        json_str     = html.escape(json.dumps(resp, indent=2))
        json_section = f"""
        <details class="json-inspector">
            <summary>&#9654; Structured JSON Inspector</summary>
            <pre class="json-body">{json_str}</pre>
        </details>
        """
    st.markdown(f"""
    <div class="msg-bubble asst-bubble">
        <div class="msg-avatar">&#129302;</div>
        <div class="msg-content">
            <div class="msg-text">{safe_reply}</div>
            {badge_section}
            {json_section}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── Tab 1: Customer Chat ───────────────────────────────────────────────────────

def render_chat_tab() -> None:
    # Header bar
    st.markdown(
        """
        <div class="app-header">
            <div class="header-left">
                <div class="header-logo">◈</div>
                <div>
                    <h1 class="header-title">ShopEasy Support Hub</h1>
                    <p class="header-subtitle">Real-time AI customer resolution & policy compliance</p>
                </div>
            </div>
            <div class="status-indicator">
                <span class="status-dot"></span> System Active
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Controls row
    top_col1, top_col2 = st.columns([6, 2])
    with top_col2:
        if st.button("↻ Clear Chat", key="clear_chat", use_container_width=True):
            st.session_state.history   = []
            st.session_state.responses = []
            st.rerun()

    # Replay conversation history
    for i, msg in enumerate(st.session_state.history):
        avatar = "👤" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar):
            st.write(msg["content"])

            if msg["role"] == "assistant":
                resp_index = sum(
                    1 for m in st.session_state.history[:i] if m["role"] == "assistant"
                )
                if resp_index < len(st.session_state.responses):
                    resp = st.session_state.responses[resp_index]
                    _badge_row(resp)
                    with st.expander("Structured JSON Inspector"):
                        st.json(resp)

    # Chat input
    user_message = st.chat_input("How can we assist you with your ShopEasy order today?")
    if not user_message:
        return

    # Render and store user turn
    with st.chat_message("user", avatar="👤"):
        st.write(user_message)
    st.session_state.history.append({"role": "user", "content": user_message})

    # Agent processing
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Analyzing policy documents…"):
            try:
                response = agent.handle_message(
                    user_message,
                    st.session_state.history[:-1],
                )
            except Exception as exc:
                st.error(
                    f"⚠️ We encountered a processing error. Our support team has been alerted.\n\n"
                    f"*Technical reference: {exc}*"
                )
                st.session_state.history.pop()
                return

        reply = response.get("customer_reply", "Thank you for contacting ShopEasy. We are reviewing your request.")
        st.write(reply)
        _badge_row(response)
        with st.expander("Structured JSON Inspector"):
            st.json(response)

    st.session_state.history.append({"role": "assistant", "content": reply})
    st.session_state.responses.append(response)


# ── Tab 2: Admin Settings ──────────────────────────────────────────────────────

def _load_agent_config() -> dict:
    with open(AGENT_CFG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _save_agent_config(data: dict) -> None:
    with open(AGENT_CFG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


def render_admin_tab() -> None:
    st.markdown(
        """
        <div class="app-header">
            <div class="header-left">
                <div class="header-logo">⚙</div>
                <div>
                    <h1 class="header-title">Admin & Policy Engine</h1>
                    <p class="header-subtitle">Live configuration, boundaries & knowledge base management</p>
                </div>
            </div>
            <div class="status-indicator">
                <span class="status-dot"></span> Live Sync Enabled
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        cfg = _load_agent_config()
    except Exception as exc:
        st.error(f"Could not load agent configuration: {exc}")
        return

    with st.form("admin_form"):
        st.subheader("◈ Agent Parameters")
        role = st.text_input(
            "Agent Role & Identity",
            value=cfg.get("role", "").strip(),
            help="High-level identity injected into Section 1 of the prompt.",
        )

        tone = st.text_input(
            "Communication Tone",
            value=cfg.get("tone", "professional_and_friendly"),
            help='Desired voice, e.g. "professional_and_friendly", "concise_and_courteous"',
        )

        topics_raw = st.text_input(
            "Supported Topics (comma-separated)",
            value=", ".join(cfg.get("supported_topics", [])),
            help="billing, delivery, technical_support, refunds, account_access",
        )

        escalation_rules_raw = st.text_area(
            "Escalation Rules (one rule per line)",
            value="\n".join(cfg.get("escalation_rules", [])),
            height=140,
            help="Plain-English criteria triggering human escalation.",
        )

        boundaries_raw = st.text_area(
            "Hard Response Boundaries (one limit per line)",
            value="\n".join(cfg.get("response_boundaries", [])),
            height=140,
            help="Negative constraints and strict promises boundaries.",
        )

        submitted = st.form_submit_button("💾 Save System Configuration")

    if submitted:
        updated = {
            "role":                role.strip(),
            "tone":                tone.strip(),
            "supported_topics":    [t.strip() for t in topics_raw.split(",") if t.strip()],
            "escalation_rules":    [r.strip() for r in escalation_rules_raw.splitlines() if r.strip()],
            "response_boundaries": [b.strip() for b in boundaries_raw.splitlines() if b.strip()],
        }
        try:
            _save_agent_config(updated)
            st.success("Configuration successfully saved! Changes apply immediately to the next query.")
        except Exception as exc:
            st.error(f"Failed to write configuration: {exc}")

    # ── Knowledge Base Management ──────────────────────────────────────────────
    st.write("")
    st.subheader("◈ Knowledge Base & Document Indexing")

    # Display active files in clean pill tags
    kb_files = sorted(
        f for f in os.listdir(KB_FOLDER)
        if f.endswith((".md", ".txt")) and f != ".gitkeep"
    )

    if kb_files:
        tags_html = "".join(f"<span class='kb-file-tag'>📄 {fname}</span>" for fname in kb_files)
        st.markdown(
            f"""
            <div class="kb-card">
                <div style="font-size:0.85rem; font-weight:600; color:#475569; margin-bottom:0.5rem;">
                    Currently Indexed Documents ({len(kb_files)} files):
                </div>
                {tags_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.caption("No documents in the knowledge base directory.")

    # Upload zone
    uploads = st.file_uploader(
        "Upload policy or FAQ documents (.md, .txt, .pdf)",
        type=["md", "txt", "pdf"],
        accept_multiple_files=True,
        key="kb_uploader",
    )

    if uploads:
        saved = []
        for uf in uploads:
            if uf.name.lower().endswith(".pdf"):
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(io.BytesIO(uf.read()))
                    text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
                    out_name = os.path.splitext(uf.name)[0] + ".txt"
                    out_path = os.path.join(KB_FOLDER, out_name)
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(text)
                    saved.append(out_name)
                except Exception as exc:
                    st.error(f"Error parsing PDF '{uf.name}': {exc}")
            else:
                out_path = os.path.join(KB_FOLDER, uf.name)
                with open(out_path, "wb") as f:
                    f.write(uf.getbuffer())
                saved.append(uf.name)

        if saved:
            try:
                get_retriever(KB_FOLDER)  # Triggers automatic re-indexing via mtime detection
                st.success(f"Successfully indexed: {', '.join(saved)}. New documents are searchable immediately.")
            except Exception as exc:
                st.warning(f"Documents saved, but index reload reported: {exc}")


# ── Tab Navigation ─────────────────────────────────────────────────────────────

tab_chat, tab_admin = st.tabs(["💬 Customer Support", "⚙ Policy Configuration & Knowledge Base"])

with tab_chat:
    render_chat_tab()

with tab_admin:
    render_admin_tab()
