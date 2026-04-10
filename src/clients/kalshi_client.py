"""
Kalshi API client for fetching prediction market data.
Uses public endpoints - no authentication required for market data.
"""

import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class KalshiMarket:
    """Represents a Kalshi market"""

    ticker: str
    title: str
    event_ticker: str
    yes_bid_dollars: float
    no_bid_dollars: float
    yes_ask_dollars: float
    no_ask_dollars: float
    volume: float  # Fixed-point representation
    open_interest: float  # Fixed-point representation
    last_price: float
    close_time: Optional[str]
    category: str
    subcategory: Optional[str]

    @property
    def implied_probability(self) -> float:
        """Get the market-implied probability from yes_bid price"""
        return self.yes_bid_dollars

    @property
    def spread(self) -> float:
        """Calculate the bid-ask spread"""
        return self.yes_ask_dollars - self.yes_bid_dollars


class KalshiClient:
    """Client for Kalshi public API endpoints"""

    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "PredictionMarketSentiment/1.0",
            }
        )

    def get_markets(
        self, status: str = "open", limit: int = 1000
    ) -> List[KalshiMarket]:
        """
        Fetch markets from Kalshi API.

        Args:
            status: Market status filter (open, closed, settled, all)
            limit: Maximum number of markets to return

        Returns:
            List of KalshiMarket objects
        """
        params = {"status": status, "limit": limit}
        response = self.session.get(f"{self.BASE_URL}/markets", params=params)
        response.raise_for_status()
        data = response.json()

        markets = []
        for market_data in data.get("markets", []):
            market = KalshiMarket(
                ticker=market_data["ticker"],
                title=market_data["title"],
                event_ticker=market_data["event_ticker"],
                yes_bid_dollars=float(market_data.get("yes_bid_dollars", 0)),
                no_bid_dollars=float(market_data.get("no_bid_dollars", 0)),
                yes_ask_dollars=float(market_data.get("yes_ask_dollars", 0)),
                no_ask_dollars=float(market_data.get("no_ask_dollars", 0)),
                volume=float(market_data.get("volume_fp", 0) or 0),
                open_interest=float(market_data.get("open_interest_fp", 0) or 0),
                last_price=float(market_data.get("last_price_dollars", 0)),
                close_time=market_data.get("close_time"),
                category=market_data.get("category", ""),
                subcategory=market_data.get("subcategory"),
            )
            markets.append(market)

        return markets

    def get_market(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific market"""
        response = self.session.get(f"{self.BASE_URL}/markets/{ticker}")
        response.raise_for_status()
        return response.json()

    def get_orderbook(self, ticker: str) -> Dict[str, Any]:
        """Get orderbook for a specific market"""
        response = self.session.get(f"{self.BASE_URL}/markets/{ticker}/orderbook")
        response.raise_for_status()
        return response.json()

    def get_events(
        self, category: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch events from Kalshi"""
        params = {"limit": limit}
        if category:
            params["category"] = category

        response = self.session.get(f"{self.BASE_URL}/events", params=params)
        response.raise_for_status()
        return response.json().get("events", [])

    def get_series(self, series_ticker: str) -> Dict[str, Any]:
        """Get series information"""
        response = self.session.get(f"{self.BASE_URL}/series/{series_ticker}")
        response.raise_for_status()
        return response.json()

    def get_trades(
        self, ticker: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent trades, optionally filtered by market ticker"""
        params = {"limit": limit}
        if ticker:
            params["market_ticker"] = ticker

        response = self.session.get(f"{self.BASE_URL}/trades", params=params)
        response.raise_for_status()
        return response.json().get("trades", [])
