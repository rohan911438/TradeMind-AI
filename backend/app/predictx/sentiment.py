"""News sentiment (lightweight).

A finance word lexicon scores SAMPLE headlines. They are illustrative, not real news.
FinBERT (ProsusAI/finbert) is the planned upgrade. It is left out of the base install because
it needs about 500 MB of model weights.
"""
from __future__ import annotations

import re

POSITIVE = {
    "growth", "beats", "beat", "record", "strong", "surge", "gains", "gain", "upgrade", "upgrades",
    "profit", "expansion", "wins", "win", "robust", "bullish", "rises", "rally", "outperform",
    "steady", "approval", "demand", "higher", "boost",
}
NEGATIVE = {
    "falls", "fall", "miss", "misses", "weak", "decline", "loss", "downgrade", "downgrades",
    "probe", "concerns", "slowdown", "pressure", "cuts", "lower", "bearish", "drop", "risk",
    "penalty", "delay", "attrition",
}

# Illustrative sample headlines - NOT real news. Used to demonstrate the sentiment pipeline.
SAMPLE_HEADLINES = {
    "RELIANCE": [
        "Sample: Retail segment reports steady growth in quarterly update",
        "Sample: Analysts upgrade outlook on strong energy demand",
        "Sample: Telecom unit faces pricing pressure in competitive market",
        "Sample: New energy expansion plans draw investor interest",
    ],
    "TCS": [
        "Sample: IT services firm wins large multi-year deal",
        "Sample: Margins under pressure as client spending slowdown continues",
        "Sample: Company reports steady deal pipeline and robust cash flow",
        "Sample: Attrition concerns ease across IT sector",
    ],
    "INFY": [
        "Sample: Revenue guidance cuts weigh on IT stock",
        "Sample: Large deal wins boost order book",
        "Sample: Analysts see demand risk from global slowdown",
        "Sample: Company announces higher buyback",
    ],
    "HDFCBANK": [
        "Sample: Bank posts record profit on loan growth",
        "Sample: Deposit growth remains strong",
        "Sample: Net interest margin under pressure after merger",
        "Sample: Brokerages upgrade bank on asset quality",
    ],
}


def score_text(text: str) -> float:
    words = re.findall(r"[a-z]+", text.lower())
    pos = sum(w in POSITIVE for w in words)
    neg = sum(w in NEGATIVE for w in words)
    return 0.0 if pos + neg == 0 else (pos - neg) / (pos + neg)


def sentiment_for(symbol: str) -> dict:
    heads = SAMPLE_HEADLINES.get(symbol, [])
    scored = [{"headline": h, "score": round(score_text(h), 2)} for h in heads]
    avg = sum(s["score"] for s in scored) / len(scored) if scored else 0.0
    label = "Positive" if avg > 0.15 else "Negative" if avg < -0.15 else "Neutral"
    return {"symbol": symbol, "score": round(avg, 2), "label": label, "headlines": scored,
            "method": "Finance lexicon (FinBERT planned)", "sample_data": True}
