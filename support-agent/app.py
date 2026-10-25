"""
app.py — Streamlit UI for the ShopEasy AI Customer Support Agent.

Tab 1: Customer Chat  — chat interface with structured JSON expander and badges.
Tab 2: Admin Settings — live-edit agent_config.yaml without restarting the server.
"""

import json
import os
import yaml
import streamlit as st
import agent  # local module
from retriever import get_retriever

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ShopEasy Support Agent",
    page_icon="🛒",
    layout="centered",
)

# ── Paths ──────────────────────────────────────────────────────────────────────
AGENT_CFG_PATH = "config/agent_config.yaml"
KB_FOLDER      = "knowledge_base"

# ── Session state defaults ─────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []   # list of {"role": str, "content": str}
if "responses" not in st.session_state:
    st.session_state.responses = []  # parallel list of full response dicts


# ── Badge helpers ──────────────────────────────────────────────────────────────

# Maps priority / urgency values to Streamlit status colors
_PRIORITY_COLOR = {
    "low":    "🟢",
    "medium": "🟡",
    "high":   "🟠",
    "urgent": "🔴",
}

_CATEGORY_ICON = {
    "billing":          "💳",
    "delivery":         "📦",
    "technical_support":"🔧",
    "refunds":          "💰",
    "account_access":   "🔐",
    "other":            "❓",
}

def _badge_row(response: dict) -> None:
    """Render category, priority, and escalation badges in one compact row."""
    category   = response.get("issue_category", "other")
    priority   = response.get("priority", "low")
    escalation = response.get("escalation_required", False)

    cat_icon  = _CATEGORY_ICON.get(category, "❓")
    pri_icon  = _PRIORITY_COLOR.get(priority, "⚪")
    esc_badge = "🚨 Escalation required" if escalation else "✅ No escalation"

    col1, col2, col3 = st.columns(3)
    col1.caption(f"{cat_icon} **{category.replace('_', ' ').title()}**")
    col2.caption(f"{pri_icon} Priority: **{priority}**")
    col3.caption(esc_badge)


# ── Tab 1: Customer Chat ───────────────────────────────────────────────────────

def render_chat_tab() -> None:
    st.header("🛒 ShopEasy Customer Support")
    st.caption("Ask anything about your orders, billing, or account.")

    # Clear chat button
    if st.button("🗑️ Clear chat", key="clear_chat"):
        st.session_state.history   = []
        st.session_state.responses = []
        st.rerun()

    # Replay all previous messages from session state
    for i, msg in enumerate(st.session_state.history):
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

            # Attach badges + JSON expander to every assistant turn
            if msg["role"] == "assistant" and i // 2 < len(st.session_state.responses):
                # Each assistant message pairs with a response dict stored at
                # index = number of complete assistant turns so far
                resp_index = sum(
                    1 for m in st.session_state.history[:i] if m["role"] == "assistant"
                )
                if resp_index < len(st.session_state.responses):
                    resp = st.session_state.responses[resp_index]
                    _badge_row(resp)
                    with st.expander("Structured JSON"):
                        st.json(resp)

    # Accept new user input
    user_message = st.chat_input("Type your message here…")
    if not user_message:
        return

    # Display and store the user message immediately
    with st.chat_message("user"):
        st.write(user_message)
    st.session_state.history.append({"role": "user", "content": user_message})

    # Call the agent pipeline
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                response = agent.handle_message(
                    user_message,
                    st.session_state.history[:-1],  # exclude the message we just appended
                )
            except Exception as exc:
                st.error(
                    f"⚠️ Something went wrong and your message couldn't be processed. "
                    f"Please try again or contact support directly.\n\n"
                    f"*Technical detail: {exc}*"
                )
                # Remove the user message we just added so history stays clean
                st.session_state.history.pop()
                return

        reply = response.get("customer_reply", "I'm sorry, I couldn't process your request.")
        st.write(reply)
        _badge_row(response)
        with st.expander("Structured JSON"):
            st.json(response)

    # Persist the assistant reply and the full response dict
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
    st.header("⚙️ Admin Settings")
    st.caption(
        "Changes are written directly to `config/agent_config.yaml` and take "
        "effect on the **next** customer message — no server restart needed."
    )

    try:
        cfg = _load_agent_config()
    except Exception as exc:
        st.error(f"Could not load config file: {exc}")
        return

    with st.form("admin_form"):
        role = st.text_input(
            "Agent role description",
            value=cfg.get("role", "").strip(),
            help="The opening paragraph of the system prompt describing who the agent is.",
        )

        tone = st.text_input(
            "Communication tone",
            value=cfg.get("tone", "professional_and_friendly"),
            help='e.g. "professional_and_friendly", "formal", "casual"',
        )

        topics_raw = st.text_input(
            "Supported topics (comma-separated)",
            value=", ".join(cfg.get("supported_topics", [])),
            help="billing, delivery, technical_support, refunds, account_access",
        )

        escalation_rules_raw = st.text_area(
            "Escalation rules (one per line)",
            value="\n".join(cfg.get("escalation_rules", [])),
            height=160,
            help="Plain-English rules that trigger escalation to a human agent.",
        )

        boundaries_raw = st.text_area(
            "Response boundaries (one per line)",
            value="\n".join(cfg.get("response_boundaries", [])),
            height=160,
            help="Hard limits on what the agent may say or promise.",
        )

        submitted = st.form_submit_button("💾 Save settings")

    if submitted:
        # Parse the form values back into the expected types
        updated = {
            "role":                role.strip(),
            "tone":                tone.strip(),
            "supported_topics":    [t.strip() for t in topics_raw.split(",") if t.strip()],
            "escalation_rules":    [r.strip() for r in escalation_rules_raw.splitlines() if r.strip()],
            "response_boundaries": [b.strip() for b in boundaries_raw.splitlines() if b.strip()],
        }
        try:
            _save_agent_config(updated)
            st.success("Settings saved! They will apply to the next message.")
        except Exception as exc:
            st.error(f"Failed to save settings: {exc}")

    # ── Knowledge Base section ─────────────────────────────────────────────────
    st.divider()
    _render_kb_section()


def _render_kb_section() -> None:
    """File uploader + file list for the knowledge base folder."""
    st.subheader("Knowledge Base")

    # Show existing files
    kb_files = sorted(
        f for f in os.listdir(KB_FOLDER)
        if f.endswith((".md", ".txt")) and f != ".gitkeep"
    )
    if kb_files:
        st.caption(f"{len(kb_files)} file(s) currently indexed:")
        for fname in kb_files:
            st.text(f"  • {fname}")
    else:
        st.caption("No documents in the knowledge base yet.")

    # Uploader
    uploads = st.file_uploader(
        "Upload documents (.md, .txt, .pdf)",
        type=["md", "txt", "pdf"],
        accept_multiple_files=True,
        key="kb_uploader",
    )

    if uploads:
        saved = []
        for uf in uploads:
            if uf.name.lower().endswith(".pdf"):
                # Extract text from PDF with pypdf
                try:
                    from pypdf import PdfReader
                    import io
                    reader = PdfReader(io.BytesIO(uf.read()))
                    text = "\n\n".join(
                        page.extract_text() or "" for page in reader.pages
                    )
                    out_name = os.path.splitext(uf.name)[0] + ".txt"
                    out_path = os.path.join(KB_FOLDER, out_name)
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(text)
                    saved.append(out_name)
                except Exception as exc:
                    st.error(f"Could not extract text from {uf.name}: {exc}")
            else:
                # Save .md / .txt directly
                out_path = os.path.join(KB_FOLDER, uf.name)
                with open(out_path, "wb") as f:
                    f.write(uf.getbuffer())
                saved.append(uf.name)

        if saved:
            # Rebuild the retriever index immediately
            try:
                get_retriever(KB_FOLDER)   # mtime change triggers rebuild
                st.success(
                    f"Saved and indexed: {', '.join(saved)}. "
                    "New documents are searchable immediately."
                )
            except Exception as exc:
                st.warning(f"Files saved but index rebuild failed: {exc}")



# ── Layout ─────────────────────────────────────────────────────────────────────

tab_chat, tab_admin = st.tabs(["💬 Customer Chat", "⚙️ Admin Settings"])

with tab_chat:
    render_chat_tab()

with tab_admin:
    render_admin_tab()
