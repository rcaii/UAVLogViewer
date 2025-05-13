from typing import Dict, Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prompt import build_prompt
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Initialize OpenAI client (e.g., for Groq)
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE")  # e.g., https://api.groq.com/openai/v1
)

# Initialize FastAPI app
app = FastAPI()

# Enable CORS for frontend requests (adjust allowed origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or use ["http://localhost:8080"] for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define request schema for LLM endpoint
class ChatRequest(BaseModel):
    question: str
    telemetry: Dict[str, Any]

@app.post("/chat")
async def chat(req: ChatRequest):
    # ✂️ Truncate telemetry data to avoid exceeding token limits
    def truncate(data, limit=100):
        if isinstance(data, dict):
            keys = list(data.keys())
            return {k: data[k] for k in keys[:limit]}
        elif isinstance(data, list):
            return data[:limit]
        return data

    telemetry = req.telemetry
    truncated = {
        "attitude": truncate(telemetry.get("attitude", {})),
        "trajectory": truncate(telemetry.get("trajectory", [])),
        "flightModes": truncate(telemetry.get("flightModes", []))
    }

    # Build prompt from question and truncated telemetry
    prompt = build_prompt(req.question, truncated)

    # Call LLM via OpenAI-compatible API (e.g., Groq)
    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {"role": "system", "content": prompt}
        ]
    )

    return {"answer": response.choices[0].message.content}
