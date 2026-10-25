"""
llm.py — Wrapper around Google Gemini API using google-genai SDK with automatic retry & fallback.

Reads GEMINI_API_KEY, GEMINI_MODEL / MODEL_NAME, and TEMPERATURE from .env.
Uses response_mime_type="application/json" for structured output mode.
Handles transient 429 / 503 errors and rotates to active models seamlessly.
"""

import os
import json
import time
import urllib.request
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

    primary_model = os.getenv("GEMINI_MODEL") or os.getenv("MODEL_NAME") or "gemini-3.5-flash-lite"
    candidate_models = [primary_model, "gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.8-flash"]
    temperature = float(os.getenv("TEMPERATURE", "0.2"))

    last_error = None

    for model_name in candidate_models:
        # Try google.genai SDK
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key, http_options={"timeout": 15})
            contents = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                response_mime_type="application/json",
            )
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
            if response.text:
                return response.text
        except Exception as exc:
            last_error = exc

        # Direct REST endpoint with response_mime_type=application/json
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            contents = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

            payload = {
                "contents": contents,
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "generationConfig": {
                    "temperature": temperature,
                    "response_mime_type": "application/json"
                },
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

            with urllib.request.urlopen(req, timeout=15) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                return res_json["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:
            last_error = exc
            if "429" in str(exc):
                continue

    raise RuntimeError(f"Gemini API call failed: {last_error}")
