# main.py
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import ccxt

app = FastAPI()

API_KEY = os.getenv("BITGET_KEY")
API_SECRET = os.getenv("BITGET_SECRET")
API_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

# Bitget 선물(USDT 무기한) 사용
exchange = ccxt.bitget({
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "password": API_PASSPHRASE,        # bitget은 passphrase -> password
    "options": {"defaultType": "swap"},
    "enableRateLimit": True,
})

class TVPayload(BaseModel):
    secret: str
    direction: str          # "long" or "short"
    short_ticker: str       # 예: BTCUSDT
    price: float
    sl: float | None = None
    tp: float | None = None
    base_percent: float = 100.0
    leverage: int = 3
    mode: str = "triple"

def map_symbol(short_ticker: str) -> str:
    s = short_ticker.upper()
    base = s.replace("PERP", "").replace("USDT", "").replace("USD", "")
    base = base.strip()
    return f"{base}/USDT:USDT"          # 예: BTC/USDT:USDT

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/webhook")
def webhook(p: TVPayload):
    if not WEBHOOK_SECRET:
        raise HTTPException(500, "Server misconfigured: WEBHOOK_SECRET missing")
    if p.secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")

    symbol = map_symbol(p.short_ticker)

    # 1) 레버리지(거래소 설정 따라 1회만 필요할 수 있음)
    try:
        exchange.set_leverage(p.leverage, symbol)
    except Exception as e:
        print("set_leverage warning:", e)

    # 2) 포지션 크기(아주 단순 예시: 가용 USDT * base_percent)
    balance = exchange.fetch_balance()
    usdt_free = balance.get("USDT", {}).get("free", 0)
    notional = max(usdt_free * (p.base_percent / 100.0), 5)  # 최소 $5 가드
    price = max(p.price, 1e-8)
    amount = max(notional / price, 0.0001)

    side = "buy" if p.direction.lower() == "long" else "sell"

    # 3) 시장가 진입 (TP/SL은 다음 단계에서 추가 예정)
    order = exchange.create_order(symbol, "market", side, amount, params={"reduceOnly": False})
    print("entry", order)

    return {"ok": True, "symbol": symbol, "side": side, "amount": amount}
