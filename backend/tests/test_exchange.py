from decimal import Decimal

import pytest

from app.exchange.mock import MockAdapter


@pytest.fixture
def mock_exchange():
    return MockAdapter()


async def test_get_ticker(mock_exchange: MockAdapter):
    ticker = await mock_exchange.get_ticker("BTC/USDT")
    assert "bid" in ticker
    assert "ask" in ticker
    assert "last" in ticker
    assert ticker["ask"] > ticker["bid"]


async def test_place_buy_order(mock_exchange: MockAdapter):
    balance_before = await mock_exchange.get_balance()
    usdt_before = balance_before["USDT"]

    order = await mock_exchange.place_order("BTC/USDT", "buy", Decimal("0.1"))
    assert order["status"] == "filled"
    assert order["side"] == "buy"
    assert order["id"] is not None

    balance_after = await mock_exchange.get_balance()
    assert balance_after["USDT"] < usdt_before
    assert balance_after.get("BTC", Decimal("0")) > 0


async def test_place_sell_order(mock_exchange: MockAdapter):
    await mock_exchange.place_order("BTC/USDT", "buy", Decimal("1.0"))

    order = await mock_exchange.place_order("BTC/USDT", "sell", Decimal("0.5"))
    assert order["status"] == "filled"
    assert order["side"] == "sell"


async def test_insufficient_balance_rejected(mock_exchange: MockAdapter):
    order = await mock_exchange.place_order("BTC/USDT", "buy", Decimal("10000"))
    assert order["status"] == "rejected"
    assert order["reason"] == "insufficient_balance"


async def test_sell_without_holdings_rejected(mock_exchange: MockAdapter):
    order = await mock_exchange.place_order("BTC/USDT", "sell", Decimal("1.0"))
    assert order["status"] == "rejected"


async def test_get_order_book(mock_exchange: MockAdapter):
    book = await mock_exchange.get_order_book("ETH/USDT", depth=5)
    assert len(book["bids"]) == 5
    assert len(book["asks"]) == 5


async def test_get_ohlcv(mock_exchange: MockAdapter):
    candles = await mock_exchange.get_ohlcv("BTC/USDT", limit=10)
    assert len(candles) == 10
    assert len(candles[0]) == 6


async def test_unknown_symbol_raises(mock_exchange: MockAdapter):
    with pytest.raises(ValueError, match="Unknown mock symbol"):
        await mock_exchange.get_ticker("FAKE/USDT")


async def test_invalid_side_raises(mock_exchange: MockAdapter):
    with pytest.raises(ValueError, match="Invalid side"):
        await mock_exchange.place_order("BTC/USDT", "hodl", Decimal("1"))
