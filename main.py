"""
Root main.py — proxies to support-agent/main.py.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR = os.path.join(BASE_DIR, "support-agent")
sys.path.insert(0, AGENT_DIR)

from main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
