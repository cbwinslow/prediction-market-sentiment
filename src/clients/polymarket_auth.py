"""
Polymarket authenticated client wrapper.
Uses py-clob-client for authenticated access (wallet-based).
"""

import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

try:
    from py_clob_client.client import ClobClient

    PY_CLOB_AVAILABLE = True
except ImportError:
    PY_CLOB_AVAILABLE = False


@dataclass
class AuthConfig:
    """Configuration for authenticated Polymarket access"""

    private_key: str = ""
    chain_id: int = 137  # Polygon
    signature_type: int = 0  # 0=EOA/MetaMask, 1=Magic/email, 2=browser wallet
    funder_address: str = ""  # Required for Magic/browser wallets


class PolymarketAuthClient:
    """
    Authenticated Polymarket client using py-clob-client.

    This gives access to:
    - Order book depth (bids/asks with sizes)
    - Your positions and orders
    - Trade execution (placing orders)

    Usage:
        # Option 1: Set env vars
        export POLYMARKET_PRIVATE_KEY=your_key_without_0x
        export POLYMARKET_FUNDER_ADDRESS=your_address

        # Option 2: Pass config directly
        config = AuthConfig(
            private_key="abc123...",
            funder_address="0x..."
        )
        client = PolymarketAuthClient(config)
    """

    HOST = "https://clob.polymarket.com"

    def __init__(self, config: Optional[AuthConfig] = None):
        if not PY_CLOB_AVAILABLE:
            raise ImportError(
                "py-clob-client not installed. Run: pip install py-clob-client"
            )

        # Get config from env if not provided
        if config is None:
            config = AuthConfig(
                private_key=os.getenv("POLYMARKET_PRIVATE_KEY", ""),
                funder_address=os.getenv("POLYMARKET_FUNDER_ADDRESS", ""),
                signature_type=int(os.getenv("POLYMARKET_SIGNATURE_TYPE", "0")),
            )

        if not config.private_key:
            raise ValueError(
                "Private key required. Set POLYMARKET_PRIVATE_KEY env var or pass config."
            )

        # Initialize authenticated client
        self.client = ClobClient(
            host=self.HOST,
            key=config.private_key,
            chain_id=config.chain_id,
            signature_type=config.signature_type,
            funder=config.funder_address if config.funder_address else None,
        )

        # Derive API credentials (L2 auth)
        try:
            api_creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(api_creds)
            self._authenticated = True
        except Exception as e:
            print(f"Warning: Could not derive API credentials: {e}")
            self._authenticated = False

    def get_order_book(self, token_id: str) -> Dict[str, Any]:
        """
        Get order book for a specific token.

        Returns bids and asks with prices and sizes.
        """
        return self.client.get_book(token_id=token_id)

    def get_market_order_book(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """Get order book using condition_id instead of token_id"""
        # Need to get token_id first - this requires mapping
        # For now, use Gamma API to get token_ids
        import requests

        resp = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"conditionId": condition_id, "limit": 1},
        )
        data = resp.json()
        if data and data[0].get("clobTokenIds"):
            token_id = data[0]["clobTokenIds"][0]
            return self.get_order_book(token_id)
        return None

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get your current positions"""
        return self.client.get_positions()

    def get_orders(self) -> List[Dict[str, Any]]:
        """Get your open orders"""
        return self.client.get_orders()

    def place_order(
        self, token_id: str, price: float, size: float, side: str = "BUY"
    ) -> Dict[str, Any]:
        """
        Place a limit order.

        Args:
            token_id: The CLOB token ID
            price: Price (0-1)
            size: Number of contracts
            side: "BUY" or "SELL"
        """
        from py_clob_client.clob_types import OrderArgs

        order_args = OrderArgs(
            token_id=token_id,
            price=str(price),
            size=str(size),
            side=side,
        )

        # Get tick size for this market
        tick_size = self.client.get_tick_size(token_id)

        return self.client.create_and_post_order(order_args, {"tick_size": tick_size})

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order"""
        return self.client.cancel_order(order_id)

    def cancel_all_orders(self) -> Dict[str, Any]:
        """Cancel all open orders"""
        return self.client.cancel_all_orders()


def create_auth_client() -> Optional[PolymarketAuthClient]:
    """
    Factory function to create authenticated client.
    Returns None if credentials not available.
    """
    private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
    if not private_key:
        print("POLYMARKET_PRIVATE_KEY not set. Authenticated client unavailable.")
        print("To enable:")
        print("  1. Get your private key from MetaMask")
        print("  2. Set: export POLYMARKET_PRIVATE_KEY=your_key_without_0x")
        print("  3. Optionally: export POLYMARKET_FUNDER_ADDRESS=your_address")
        return None

    try:
        config = AuthConfig(
            private_key=private_key,
            funder_address=os.getenv("POLYMARKET_FUNDER_ADDRESS", ""),
            signature_type=int(os.getenv("POLYMARKET_SIGNATURE_TYPE", "0")),
        )
        return PolymarketAuthClient(config)
    except Exception as e:
        print(f"Failed to create authenticated client: {e}")
        return None


if __name__ == "__main__":
    # Test connection
    client = create_auth_client()
    if client:
        print("✓ Authenticated client created successfully")

        # Test getting positions
        try:
            positions = client.get_positions()
            print(f"  Positions: {len(positions)}")
        except Exception as e:
            print(f"  Positions: {e}")
    else:
        print("✗ Authenticated client not available")
        print("Set POLYMARKET_PRIVATE_KEY to enable")
