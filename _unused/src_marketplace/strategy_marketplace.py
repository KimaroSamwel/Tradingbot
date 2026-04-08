"""Simple strategy marketplace for importing/exporting strategy templates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional


class StrategyMarketplace:
    """Manage sharable strategy templates with basic validation."""

    REQUIRED_FIELDS = {"name", "type", "config"}

    def __init__(self, storage_path: str = "data/strategy_marketplace.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.strategies: List[Dict] = []
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            self.strategies = []
            return
        try:
            self.strategies = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except Exception:
            self.strategies = []

    def _save(self) -> None:
        self.storage_path.write_text(json.dumps(self.strategies, indent=2), encoding="utf-8")

    def _validate_strategy(self, strategy: Dict) -> None:
        missing = self.REQUIRED_FIELDS.difference(strategy.keys())
        if missing:
            raise ValueError(f"Strategy missing required fields: {sorted(missing)}")

    def import_strategy(self, strategy_json: str) -> Dict:
        payload = json.loads(strategy_json)
        self._validate_strategy(payload)

        name = str(payload["name"])
        self.strategies = [s for s in self.strategies if str(s.get("name")) != name]
        self.strategies.append(payload)
        self._save()
        return payload

    def export_strategy(self, strategy_name: str) -> str:
        for strategy in self.strategies:
            if str(strategy.get("name")) == str(strategy_name):
                return json.dumps(strategy, indent=2)
        raise KeyError(f"Strategy not found: {strategy_name}")

    def list_strategies(self) -> List[Dict]:
        return list(self.strategies)

    def get_strategy(self, strategy_name: str) -> Optional[Dict]:
        for strategy in self.strategies:
            if str(strategy.get("name")) == str(strategy_name):
                return strategy
        return None
