"""
Core data models and utilities shared across the project.
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ArbitrageOpportunity:
    """Represents an arbitrage opportunity between markets"""

    platform_a: str
    platform_b: str
    market_a: str
    market_b: str
    event_a: str
    event_b: str
    price_a: float
    price_b: float
    spread: float
    spread_pct: float
    volume_a: float
    volume_b: float
    implied_probability_difference: float
    confidence: float  # 0-1 based on volume and spread

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "platform_a": self.platform_a,
            "platform_b": self.platform_b,
            "market_a": self.market_a,
            "market_b": self.market_b,
            "event_a": self.event_a,
            "event_b": self.event_b,
            "price_a": self.price_a,
            "price_b": self.price_b,
            "spread": self.spread,
            "spread_pct": self.spread_pct,
            "volume_a": self.volume_a,
            "volume_b": self.volume_b,
            "implied_probability_difference": self.implied_probability_difference,
            "confidence": self.confidence,
        }


@dataclass
class CrossAssetOpportunity:
    """Represents arbitrage between prediction markets and asset prices"""

    platform: str
    market_id: str
    question: str
    asset: str
    asset_price: float
    strike: float
    direction: str
    prediction_probability: float
    calculated_probability: float
    discrepancy: float
    time_to_expiry: float
    confidence: float

    def to_dict(self) -> Dict:
        return {
            "platform": self.platform,
            "market_id": self.market_id,
            "question": self.question,
            "asset": self.asset,
            "asset_price": self.asset_price,
            "strike": self.strike,
            "direction": self.direction,
            "prediction_probability": self.prediction_probability,
            "calculated_probability": self.calculated_probability,
            "discrepancy": self.discrepancy,
            "time_to_expiry": self.time_to_expiry,
            "confidence": self.confidence,
        }


@dataclass
class MarketSentiment:
    """Aggregated sentiment data for a category or event"""

    category: str
    total_markets: int
    avg_probability: float
    weighted_probability: float  # Volume-weighted
    total_volume: float
    bullish_count: int  # Markets with prob > 0.5
    bearish_count: int  # Markets with prob < 0.5
    neutral_count: int  # Markets with prob = 0.5
    volatility: float  # Standard deviation of probabilities
    timestamp: datetime

    @property
    def sentiment_score(self) -> float:
        """Overall sentiment score from -1 (bearish) to +1 (bullish)"""
        total = self.bullish_count + self.bearish_count
        if total == 0:
            return 0.0
        return (self.bullish_count - self.bearish_count) / total

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "category": self.category,
            "total_markets": self.total_markets,
            "avg_probability": self.avg_probability,
            "weighted_probability": self.weighted_probability,
            "total_volume": self.total_volume,
            "bullish_count": self.bullish_count,
            "bearish_count": self.bearish_count,
            "neutral_count": self.neutral_count,
            "volatility": self.volatility,
            "sentiment_score": self.sentiment_score,
            "timestamp": self.timestamp.isoformat(),
        }
