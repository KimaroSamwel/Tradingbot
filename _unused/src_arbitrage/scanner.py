"""Cross-exchange and triangular arbitrage scanner."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple


class ArbitrageScanner:
    """Continuously compare prices across exchanges for spread opportunities."""

    def __init__(self, exchanges: Dict[str, object], config: Dict | None = None):
        cfg = config or {}
        self.exchanges = exchanges or {}
        self.watchlist = list(cfg.get("watchlist", []))
        self.min_spread = float(cfg.get("min_spread", 0.005) or 0.005)
        self.scan_interval = int(cfg.get("scan_interval", 1) or 1)

    def get_prices_across_exchanges(self, pair: str) -> Dict[str, Dict[str, float]]:
        prices = {}
        for name, connector in self.exchanges.items():
            if connector is None:
                continue
            try:
                quote = connector.get_ticker(pair)
                prices[name] = {
                    "bid": float(quote.get("bid", 0.0) or 0.0),
                    "ask": float(quote.get("ask", 0.0) or 0.0),
                }
            except Exception:
                continue
        return prices

    def _normalize_pair_symbol(self, pair: str) -> str:
        return str(pair or "").upper().replace(" ", "")

    def _parse_pair(self, pair: str) -> Optional[Tuple[str, str]]:
        pair_u = self._normalize_pair_symbol(pair)
        for sep in ("/", "_", "-"):
            if sep in pair_u:
                left, right = pair_u.split(sep, 1)
                if left and right:
                    return left, right

        # Basic fallback for 6-char FX-style symbols (e.g., EURUSD).
        if len(pair_u) == 6 and pair_u.isalpha():
            return pair_u[:3], pair_u[3:]

        return None

    def _fetch_exchange_quotes(self, exchange_name: str) -> Dict[str, Dict[str, float]]:
        connector = self.exchanges.get(exchange_name)
        if connector is None:
            return {}

        quotes: Dict[str, Dict[str, float]] = {}
        for pair in self.watchlist:
            try:
                raw = connector.get_ticker(pair)
                bid = float(raw.get("bid", 0.0) or 0.0)
                ask = float(raw.get("ask", 0.0) or 0.0)
                if bid <= 0 or ask <= 0:
                    continue
                quotes[self._normalize_pair_symbol(pair)] = {
                    "bid": bid,
                    "ask": ask,
                }
            except Exception:
                continue

        return quotes

    def _build_conversion_edges(self, quotes: Dict[str, Dict[str, float]]) -> Dict[Tuple[str, str], Dict]:
        """
        Build directional conversion edges from bid/ask.

        If pair is BASE/QUOTE:
          - BASE -> QUOTE uses bid (selling base for quote)
          - QUOTE -> BASE uses 1/ask (buying base with quote)
        """
        edges: Dict[Tuple[str, str], Dict] = {}

        for pair, px in quotes.items():
            parsed = self._parse_pair(pair)
            if parsed is None:
                continue

            base, quote = parsed
            bid = float(px.get("bid", 0.0) or 0.0)
            ask = float(px.get("ask", 0.0) or 0.0)
            if bid <= 0.0 or ask <= 0.0:
                continue

            edges[(base, quote)] = {
                "rate": bid,
                "pair": pair,
                "side": "SELL_BASE",
            }
            edges[(quote, base)] = {
                "rate": 1.0 / ask,
                "pair": pair,
                "side": "BUY_BASE",
            }

        return edges

    def calculate_spreads(self, prices: Dict[str, Dict[str, float]]) -> List[Dict]:
        opportunities = []
        exchanges = list(prices.keys())
        for buy_ex in exchanges:
            for sell_ex in exchanges:
                if buy_ex == sell_ex:
                    continue
                buy_ask = float(prices[buy_ex].get("ask", 0.0) or 0.0)
                sell_bid = float(prices[sell_ex].get("bid", 0.0) or 0.0)
                if buy_ask <= 0 or sell_bid <= 0:
                    continue
                spread = (sell_bid - buy_ask) / buy_ask
                opportunities.append(
                    {
                        "buy_exchange": buy_ex,
                        "sell_exchange": sell_ex,
                        "buy_price": buy_ask,
                        "sell_price": sell_bid,
                        "spread": float(spread),
                    }
                )
        return opportunities

    def filter_profitable(self, spreads: List[Dict]) -> List[Dict]:
        return [s for s in spreads if float(s.get("spread", 0.0)) >= self.min_spread]

    def scan_all_pairs(self) -> List[Dict]:
        opportunities = []
        for pair in self.watchlist:
            prices = self.get_prices_across_exchanges(pair)
            spreads = self.calculate_spreads(prices)
            profitable = self.filter_profitable(spreads)
            for item in profitable:
                item["pair"] = pair
            opportunities.extend(profitable)
        opportunities.sort(key=lambda x: float(x.get("spread", 0.0) or 0.0), reverse=True)
        return opportunities

    def calculate_triangular_arbitrage(self, base_currency: str, exchanges: List[str]) -> List[Dict]:
        """Detect triangular opportunities base -> c1 -> c2 -> base per exchange."""
        base = str(base_currency or "").upper().strip()
        if not base:
            return []

        selected_exchanges = list(exchanges or [])
        if not selected_exchanges:
            selected_exchanges = list(self.exchanges.keys())

        opportunities: List[Dict] = []

        for exchange_name in selected_exchanges:
            if exchange_name not in self.exchanges:
                continue

            quotes = self._fetch_exchange_quotes(exchange_name)
            if not quotes:
                continue

            edges = self._build_conversion_edges(quotes)
            if not edges:
                continue

            currencies = set()
            for src, dst in edges.keys():
                currencies.add(src)
                currencies.add(dst)

            if base not in currencies:
                continue

            for c1 in currencies:
                if c1 == base:
                    continue
                e1 = edges.get((base, c1))
                if e1 is None:
                    continue

                for c2 in currencies:
                    if c2 == base or c2 == c1:
                        continue

                    e2 = edges.get((c1, c2))
                    e3 = edges.get((c2, base))
                    if e2 is None or e3 is None:
                        continue

                    gross_return = float(e1["rate"]) * float(e2["rate"]) * float(e3["rate"])
                    spread = gross_return - 1.0
                    if spread < self.min_spread:
                        continue

                    opportunities.append(
                        {
                            "type": "triangular",
                            "exchange": exchange_name,
                            "base_currency": base,
                            "path": [base, c1, c2, base],
                            "pairs": [e1["pair"], e2["pair"], e3["pair"]],
                            "actions": [e1["side"], e2["side"], e3["side"]],
                            "gross_return": float(gross_return),
                            "spread": float(spread),
                        }
                    )

        opportunities.sort(key=lambda x: float(x.get("spread", 0.0) or 0.0), reverse=True)
        return opportunities
