"""TradeMind AI - FastAPI application (API layer + static frontend)."""
from __future__ import annotations

import asyncio
import os
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from . import auth
from .config import DISCLAIMER, settings
from .paper.broker import AccountManager
from .predictx.features import atr
from .predictx.model import Predictor
from .predictx.sentiment import sentiment_for
from .riskguard.engine import Limits, evaluate
from .streamx.engine import StreamEngine

engine = StreamEngine()
predictor = Predictor()
accounts = AccountManager()


def _secret_key() -> str:
    if os.getenv("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    f = settings.DATA_DIR / ".secret_key"
    if not f.exists():
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip()


async def _equity_snapshots() -> None:
    while True:
        await asyncio.sleep(5)
        marks = _marks()
        for acc in accounts.active():
            acc.snapshot_equity(marks)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await engine.start()
    task = asyncio.create_task(_equity_snapshots())
    yield
    task.cancel()
    for acc in accounts.active():
        acc.save()
    await engine.stop()


app = FastAPI(title="TradeMind AI", version="1.0", lifespan=lifespan)


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    """Browsers must revalidate app files (ETag -> cheap 304), so a new deploy is picked up immediately.
    Third-party vendor bundles never change, so they may be cached for a day."""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/vendor/"):
        response.headers["Cache-Control"] = "public, max-age=86400"
    elif not path.startswith(("/api/", "/ws/")):
        response.headers["Cache-Control"] = "no-cache"
    return response
app.add_middleware(SessionMiddleware, secret_key=_secret_key(), same_site="lax",
                   max_age=60 * 60 * 24 * 14, https_only=os.getenv("HTTPS_ONLY", "false") == "true")


# ---------------- helpers ----------------
def _state(symbol: str):
    st = engine.states.get(symbol.upper())
    if st is None:
        raise HTTPException(404, f"Unknown symbol {symbol}")
    return st


def _marks() -> dict[str, float]:
    return {s: (st.bid + st.ask) / 2 for s, st in engine.states.items()}


def _signal(symbol: str) -> dict:
    st = _state(symbol)
    return predictor.predict(st.symbol, st.candles_df(), st.imbalance, st.ann_vol(), sentiment_for(st.symbol))


class OrderIn(BaseModel):
    symbol: str
    side: str = Field(pattern="^(BUY|SELL|buy|sell)$")
    qty: int | None = None


class RateIn(BaseModel):
    events_per_sec: int = Field(ge=1, le=20000)


class GoogleIn(BaseModel):
    credential: str


def _risk(order: OrderIn, user: dict) -> tuple[dict, dict, object]:
    st = _state(order.symbol)
    signal = _signal(st.symbol)
    acc = accounts.get(user["id"])
    df = st.candles_df()
    verdict = evaluate(st.symbol, order.side, order.qty, bid=st.bid, ask=st.ask,
                       atr=float(atr(df).iloc[-1]), ann_vol=st.ann_vol(), signal=signal,
                       portfolio=acc.portfolio(_marks()))
    return verdict, signal, acc


# ---------------- auth ----------------
@app.get("/api/auth/config")
def auth_config():
    return {"google_client_id": auth.GOOGLE_CLIENT_ID or None, "guest_enabled": True}


@app.post("/api/auth/google")
def auth_google(body: GoogleIn, request: Request):
    user = auth.verify_google_token(body.credential)
    request.session["uid"] = user["id"]
    return user


@app.post("/api/auth/guest")
def auth_guest(request: Request):
    user = auth.guest_user()
    request.session["uid"] = user["id"]
    return user


@app.get("/api/auth/me")
def auth_me(user: dict = Depends(auth.current_user)):
    return user


@app.post("/api/auth/logout")
def auth_logout(request: Request):
    request.session.clear()
    return {"ok": True}


# ---------------- market (StreamX) ----------------
@app.get("/api/health")
def health():
    return {"status": "ok", "feed": "SIMULATED", "bar_seconds": settings.BAR_SECONDS,
            "symbols": settings.SYMBOLS, "data_sources": engine.sources,
            "model_loaded": predictor.model is not None, "time": time.time()}


@app.get("/api/symbols")
def symbols():
    return [st.summary() for st in engine.states.values()]


@app.get("/api/market/{symbol}/snapshot")
def snapshot(symbol: str):
    st = _state(symbol)
    return {**st.snapshot(), "annualised_volatility": round(st.ann_vol(), 4)}


@app.get("/api/market/{symbol}/candles")
def candles(symbol: str, limit: int = 400):
    return _state(symbol).all_candles()[-limit:]


# ---------------- AI (PredictX) ----------------
@app.get("/api/predict/model-info")
def model_info():
    if not predictor.metrics:
        raise HTTPException(404, "Model not trained")
    return predictor.metrics


@app.get("/api/predict/{symbol}")
def predict(symbol: str):
    return _signal(symbol)


@app.get("/api/sentiment/{symbol}")
def sentiment(symbol: str):
    return sentiment_for(_state(symbol).symbol)


# ---------------- RiskGuard ----------------
@app.post("/api/risk/evaluate")
def risk_evaluate(order: OrderIn, user: dict = Depends(auth.current_user)):
    verdict, signal, _ = _risk(order, user)
    return {"verdict": verdict, "signal": signal}


@app.get("/api/risk/portfolio")
def risk_portfolio(user: dict = Depends(auth.current_user)):
    pf = accounts.get(user["id"]).portfolio(_marks())
    L = Limits()
    per_symbol = {s: {"annualised_volatility": round(st.ann_vol(), 4), "imbalance": round(st.imbalance, 3)}
                  for s, st in engine.states.items()}
    return {"portfolio": pf, "per_symbol": per_symbol,
            "limits": {"risk_per_trade": L.risk_per_trade, "max_symbol_exposure": L.max_symbol,
                       "max_total_exposure": L.max_total, "min_risk_reward": L.min_rr,
                       "daily_loss_limit": L.daily_loss, "stop_atr_multiple": L.stop_atr},
            "daily_loss_used": round(-min(0, pf["realised_today"]) / (L.daily_loss * pf["starting_cash"]), 4)}


# ---------------- Paper trading ----------------
@app.post("/api/paper/orders")
def paper_order(order: OrderIn, user: dict = Depends(auth.current_user)):
    verdict, signal, acc = _risk(order, user)
    st = _state(order.symbol)
    price = st.ask if order.side.upper() == "BUY" else st.bid
    rec = acc.record(st.symbol, order.side.upper(), order.qty, verdict, price, signal)
    return {"order": rec, "verdict": verdict, "portfolio": acc.portfolio(_marks())}


@app.get("/api/paper/portfolio")
def paper_portfolio(user: dict = Depends(auth.current_user)):
    return accounts.get(user["id"]).portfolio(_marks())


@app.get("/api/paper/orders")
def paper_orders(user: dict = Depends(auth.current_user)):
    return accounts.get(user["id"]).s["orders"][:100]


@app.get("/api/paper/equity")
def paper_equity(user: dict = Depends(auth.current_user)):
    acc = accounts.get(user["id"])
    curve = acc.s["equity_curve"][-500:]
    return curve or [{"t": int(time.time()), "equity": acc.portfolio(_marks())["equity"]}]


@app.post("/api/paper/reset")
def paper_reset(user: dict = Depends(auth.current_user)):
    acc = accounts.get(user["id"])
    acc.reset()
    return acc.portfolio(_marks())


# ---------------- Monitor ----------------
@app.get("/api/monitor/metrics")
def monitor_metrics():
    return engine.monitor()


@app.post("/api/monitor/rate")
def monitor_rate(body: RateIn):
    engine.sim.set_rate(body.events_per_sec)
    return {"events_per_sec": engine.sim.rate}


# ---------------- WebSockets ----------------
@app.websocket("/ws/market")
async def ws_market(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.send_json({"type": "market", "t": time.time(),
                                "symbols": {s: st.snapshot() for s, st in engine.states.items()}})
            await asyncio.sleep(0.25)
    except (WebSocketDisconnect, RuntimeError):
        pass


@app.websocket("/ws/monitor")
async def ws_monitor(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.send_json({"type": "monitor", **engine.monitor()})
            await asyncio.sleep(1.0)
    except (WebSocketDisconnect, RuntimeError):
        pass


# ---------------- Frontend ----------------
@app.get("/app")
def app_page():
    return FileResponse(settings.STATIC_DIR / "app.html")


app.mount("/", StaticFiles(directory=settings.STATIC_DIR, html=True), name="static")
