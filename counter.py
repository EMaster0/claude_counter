"""
This Py file is making for Claude API Webhook + Usage Counter / FaskAPI Middleware

Connect to Make's HTTP module first instead of Claude directly.


Remember to setup ANTHROPIC_API_KEY == your Claude API key in Railway dashboard
"""

import os
import httpx
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# pricing per million tokens (USD)
# updating after June 15th
PRICING = {
    "claude-opus-4-5":   {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-5": {"input": 3.0,  "output": 15.0},
    "claude-haiku-4-5":  {"input": 0.8,  "output": 4.0},
}

# using in-memory log — clears on restart, enough to track current session
records: list[dict] = []


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICING.get(model, {"input": 0, "output": 0})
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


class WebhookRequest(BaseModel):
    prompt: str
    feature_tag: str = ""                  
    model: str = "claude-sonnet-4-5"       
    max_tokens: int = 1024
    system: str = ""                       # system prompt


class WebhookResponse(BaseModel):
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    feature_tag: str


# sends requests here
# set the variable in Railway (cloud server)
@app.post("/webhook", response_model=WebhookResponse)
async def webhook(req: WebhookRequest):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY is not set")

    messages = [{"role": "user", "content": req.prompt}]
    body = {
        "model": req.model,
        "max_tokens": req.max_tokens,
        "messages": messages,
    }
    if req.system:
        body["system"] = req.system

    # Forward request to Claude API
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body,
        )

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    data = response.json()

    # extract usage from response
    usage         = data.get("usage", {})
    input_tokens  = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    model_used    = data.get("model", req.model)
    cost          = estimate_cost(model_used, input_tokens, output_tokens)
    content       = data["content"][0]["text"] if data.get("content") else ""

    # save record
    records.append({
        "timestamp":          datetime.now().isoformat(),
        "feature_tag":        req.feature_tag,
        "model":              model_used,
        "input_tokens":       input_tokens,
        "output_tokens":      output_tokens,
        "estimated_cost_usd": cost,
    })

    return WebhookResponse(
        content=content,
        model=model_used,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=cost,
        feature_tag=req.feature_tag,
    )


# open in browser anytime
@app.get("/summary")
def summary():
    if not records:
        return {"message": "No calls recorded yet"}

    total_calls  = len(records)
    total_tokens = sum(r["input_tokens"] + r["output_tokens"] for r in records)
    total_cost   = sum(r["estimated_cost_usd"] for r in records)

    # group by feature_tag
    by_feature: dict[str, dict] = {}
    for r in records:
        tag = r["feature_tag"] or "untagged"
        if tag not in by_feature:
            by_feature[tag] = {"calls": 0, "tokens": 0, "cost": 0.0}
        by_feature[tag]["calls"]  += 1
        by_feature[tag]["tokens"] += r["input_tokens"] + r["output_tokens"]
        by_feature[tag]["cost"]   += r["estimated_cost_usd"]

    return {
        "total_calls":    total_calls,
        "total_tokens":   total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "by_feature":     by_feature,
        "recent_10":      records[-10:],
    }


# Health check for Railway
# this just to make sure it will run
@app.get("/")
def health():
    return {"status": "ok"}
