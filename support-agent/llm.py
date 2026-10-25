"""
llm.py — Wrapper around the Google Gemini API.

Reads GEMINI_API_KEY, MODEL_NAME, and TEMPERATURE from .env,
and sends chat requests directly to Google Gemini.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def call_llm(system_prompt: str, messages: list[dict]) -> str:
    """
    Send a chat request to the Google Gemini API and return reply text.

    Args:
        system_prompt: The rendered system prompt string.
        messages: Conversation history as list of {"role": str, "content": str}.

    Returns:
        The model's reply as a plain string.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. Please add it to your .env file."
        )

    model_name  = os.getenv("MODEL_NAME", "gemini-3.8-flash")
    temperature = float(os.getenv("TEMPERATURE", "0.2"))

    # Attempt 1: Modern google.genai SDK
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
        )
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )
        if response.text:
            return response.text
    except Exception:
        pass

    # Attempt 2: Direct REST endpoint (fast, zero dependency overhead)
    import json
    import urllib.request

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    payload = {
        "contents": contents,
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {"temperature": temperature},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            return res_json["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:
        raise RuntimeError(f"Gemini API call failed: {exc}") from exc
