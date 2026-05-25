"""Shared prompt construction for all AI providers.

Identical inputs produce identical prompts across OpenAI, Gemini, and Claude
so that consensus mode comparisons are meaningful.
"""

SYSTEM_PROMPT = (
    "You are a disciplined crypto day-trader focused on capital preservation. "
    "You look for SHORT-TERM opportunities (hours to 1 day). Always respond with valid JSON only. "
    "No markdown formatting. Only recommend BUY when technicals, volume, AND trend clearly support it. "
    "In fear/bear markets, be MORE selective - most setups will fail. Default to HOLD unless conviction is high. "
    "A HOLD that misses a trade is better than a BUY that loses money."
)

RESPONSE_SCHEMA = """{
  "action": "BUY" or "SELL" or "HOLD",
  "confidence": <number 0-100>,
  "reasoning": "<2-3 sentences explaining why, mentioning specific indicators>",
  "risk_level": "LOW" or "MEDIUM" or "HIGH",
  "suggested_stop_loss_pct": <number like 2 or 3>,
  "suggested_take_profit_pct": <number like 4 or 6>,
  "key_factors": ["<factor1>", "<factor2>", "<factor3>"]
}"""


def build_user_prompt(
    symbol: str,
    price: float,
    change_24h: float,
    indicators: dict,
    balance: float | None = None,
    open_trades: int = 0,
    daily_pnl: float = 0.0,
) -> str:
    """Build the analysis prompt from market data.

    Args:
        symbol: Trading pair (e.g. "BTC/USDT").
        price: Current price.
        change_24h: 24-hour price change percentage.
        indicators: Dict of technical indicator values.
        balance: Available account balance.
        open_trades: Number of currently open trades.
        daily_pnl: Today's realized P&L.
    """
    rsi = indicators.get("rsi", "N/A")
    macd = indicators.get("macd", "N/A")
    macd_signal = indicators.get("macd_signal", "N/A")
    ema_fast = indicators.get("ema_fast", "N/A")
    ema_slow = indicators.get("ema_slow", "N/A")
    volume_ratio = indicators.get("volume_ratio", "N/A")
    bb_upper = indicators.get("bb_upper", "N/A")
    bb_lower = indicators.get("bb_lower", "N/A")
    atr = indicators.get("atr", "N/A")
    trend = indicators.get("trend", "N/A")

    account_ctx = ""
    if balance is not None:
        account_ctx = f"\nACCOUNT: Balance=${balance:.2f} | Open trades: {open_trades} | Daily PnL: ${daily_pnl:.2f}"

    return f"""Analyze the following real-time data for {symbol} and give your trading opinion.

CURRENT STATE:
- Price: ${price} | 24h Change: {change_24h:.2f}%{account_ctx}

PRIMARY INDICATORS:
- RSI (14): {rsi}
- MACD: {macd}, Signal: {macd_signal}
- EMA Fast/Slow: {ema_fast} / {ema_slow}
- Bollinger Bands: Upper={bb_upper}, Lower={bb_lower}
- ATR: {atr}
- Volume Ratio: {volume_ratio}x average
- Trend: {trend}

IMPORTANT: This is for SHORT-TERM day trading. Only recommend BUY when you see CLEAR evidence.
Protecting capital is priority #1.

RESPOND IN EXACTLY THIS JSON FORMAT (no markdown, no explanation outside the JSON):
{RESPONSE_SCHEMA}"""
