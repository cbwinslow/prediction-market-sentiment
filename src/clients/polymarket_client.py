"""
Polymarket API client for fetching prediction market data.
Uses public endpoints - no authentication required for market data.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import requests


@dataclass
class PolymarketToken:
    """Represents a token/outcome in a Polymarket market"""

    token_id: str
    outcome: str
    price: float
    winner: bool


@dataclass
class PolymarketMarket:
    """Represents a Polymarket market"""

    condition_id: str
    question: str
    description: str
    tokens: List[PolymarketToken]
    active: bool
    accepting_orders: bool
    closed: bool
    archived: bool
    market_slug: str
    minimum_order_size: float
    minimum_tick_size: str
    tags: List[str]
    icon: Optional[str]
    image: Optional[str]
    volume: float = 0.0
    liquidity: float = 0.0

    @property
    def best_buy_price(self) -> Optional[float]:
        """Get the best buy (bid) price across all tokens"""
        buy_prices = [t.price for t in self.tokens if t.outcome != ""]
        return max(buy_prices) if buy_prices else None

    @property
    def implied_probabilities(self) -> Dict[str, float]:
        """Get probability for each outcome based on current token price"""
        return {t.outcome: t.price for t in self.tokens}

    @property
    def spread(self) -> float:
        """Calculate spread if there are two opposing outcomes"""
        if len(self.tokens) == 2:
            prices = sorted([t.price for t in self.tokens])
            return prices[1] - prices[0]
        return 0.0


class PolymarketClient:
    """Client for Polymarket Gamma API (public, no auth required)"""

    BASE_URL = "https://gamma-api.polymarket.com"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "PredictionMarketSentiment/1.0",
            }
        )

    def get_markets(
        self, limit: int = 100, active_only: bool = True
    ) -> List[PolymarketMarket]:
        """
        Fetch markets from Polymarket Gamma API.

        Args:
            limit: Maximum number of markets to return
            active_only: Only return active (non-closed) markets

        Returns:
            List of PolymarketMarket objects
        """
        params = {"limit": limit}
        if active_only:
            params["active"] = "true"

        response = self.session.get(f"{self.BASE_URL}/markets", params=params)
        response.raise_for_status()
        data = response.json()

        markets = []
        for market_data in data:
            # Get outcome prices - they come as JSON strings
            import json

            outcome_prices_raw = market_data.get("outcomePrices")
            outcomes_raw = market_data.get("outcomes")

            # Parse JSON strings if needed
            if isinstance(outcome_prices_raw, str):
                outcome_prices = json.loads(outcome_prices_raw)
            else:
                outcome_prices = outcome_prices_raw or ["0.5", "0.5"]

            if isinstance(outcomes_raw, str):
                outcomes = json.loads(outcomes_raw)
            else:
                outcomes = outcomes_raw or ["Yes", "No"]

            # Create tokens from outcome prices
            tokens = []
            for i, outcome in enumerate(outcomes):
                price = float(outcome_prices[i]) if i < len(outcome_prices) else 0.5
                # Determine winner from final prices if closed
                winner = False
                if market_data.get("closed"):
                    # Check if this outcome has price 1 (won)
                    tokens_data = market_data.get("tokens", [])
                    for t in tokens_data:
                        if t.get("outcome") == outcome:
                            winner = t.get("price", 0) == 1.0
                            break

                token = PolymarketToken(
                    token_id=market_data.get("clobTokenIds", [""])[i]
                    if i < len(market_data.get("clobTokenIds", []))
                    else "",
                    outcome=outcome,
                    price=price,
                    winner=winner,
                )
                tokens.append(token)

            market = PolymarketMarket(
                condition_id=market_data.get("conditionId", ""),
                question=market_data.get("question", ""),
                description=market_data.get("description", ""),
                tokens=tokens,
                active=market_data.get("active", False),
                accepting_orders=market_data.get("acceptingOrders", False),
                closed=market_data.get("closed", False),
                archived=market_data.get("archived", False),
                market_slug=market_data.get("slug", ""),
                minimum_order_size=market_data.get("orderMinSize", 5),
                minimum_tick_size=str(market_data.get("orderPriceMinTickSize", 0.01)),
                tags=[market_data.get("groupItemTitle", "")]
                if market_data.get("groupItemTitle")
                else [],
                icon=market_data.get("icon"),
                image=market_data.get("image"),
                volume=float(market_data.get("volume", 0) or 0),
                liquidity=float(market_data.get("liquidity", 0) or 0),
            )
            markets.append(market)

        return markets

    def get_market(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific market"""
        response = self.session.get(f"{self.BASE_URL}/markets/{condition_id}")
        response.raise_for_status()
        return response.json()

    def get_orderbook(self, token_id: str) -> Dict[str, Any]:
        """Get orderbook for a specific token"""
        response = self.session.get(
            f"{self.BASE_URL}/orderbook", params={"token_id": token_id}
        )
        response.raise_for_status()
        return response.json()

    def get_price(self, token_id: str, side: str = "BUY") -> Optional[float]:
        """Get current best price for a token"""
        response = self.session.get(
            f"{self.BASE_URL}/prices", params={"token_id": token_id, "side": side}
        )
        response.raise_for_status()
        data = response.json()
        return float(data.get("price", 0)) if data.get("price") else None

    def get_trades(
        self, token_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent trades, optionally filtered by token ID"""
        params = {"limit": limit}
        if token_id:
            params["token_id"] = token_id

        response = self.session.get(f"{self.BASE_URL}/trades", params=params)
        response.raise_for_status()
        return response.json().get("trades", [])

    def get_simplified_markets(self) -> List[Dict[str, Any]]:
        """Get simplified market data for faster loading"""
        response = self.session.get(f"{self.BASE_URL}/markets/simplified")
        response.raise_for_status()
        return response.json().get("data", [])
