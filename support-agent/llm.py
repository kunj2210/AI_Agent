"""
llm.py — Thin wrapper around the Groq Python SDK.

Reads GROQ_API_KEY, MODEL_NAME, and TEMPERATURE from .env,
then exposes a single call_llm(system_prompt, messages) function
that returns the model's reply as a plain string.
"""

import os
from dotenv import load_dotenv
from groq import Groq

# Load .env variables into os.environ at import time
load_dotenv()


def _get_client() -> Groq:
    """Create and return a Groq client using the API key from .env."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. "
            "Copy .env.example to .env and add your key."
        )
    return Groq(api_key=api_key)


def call_llm(system_prompt: str, messages: list[dict]) -> str:
    """
    Send a chat request to the Groq API and return the reply text.

    Args:
        system_prompt: The fully rendered system prompt string.
        messages:      List of {"role": "user"|"assistant", "content": str}
                       dicts representing the conversation history.

    Returns:
        The model's reply as a plain string.

    Raises:
        EnvironmentError: If GROQ_API_KEY is missing.
        RuntimeError:     If the API call fails for any reason.
    """
    model       = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
    temperature = float(os.getenv("TEMPERATURE", "0.2"))

    # Prepend the system message to the conversation
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    try:
        client   = _get_client()
        response = client.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=temperature,
        )
        return response.choices[0].message.content

    except EnvironmentError:
        raise   # re-raise config errors as-is

    except Exception as exc:
        raise RuntimeError(
            f"Groq API call failed [{type(exc).__name__}]: {exc}"
        ) from exc
