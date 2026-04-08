"""Generate YAML config snippets for V2 strategy controllers.

Usage:
  python scripts/generate_v2_config.py --strategy bollinger_v1
  python scripts/generate_v2_config.py --strategy macd_bb_v1
"""

from __future__ import annotations

import argparse
import yaml


TEMPLATES = {
    "bollinger_v1": {
        "bb_length": 100,
        "bb_std": 2.0,
        "bb_long_threshold": 0.3,
        "bb_short_threshold": 0.7,
        "max_executors": 5,
        "cooldown_time": 15,
        "position_executor": {
            "stop_loss": 0.01,
            "take_profit": 0.03,
            "time_limit": 21600,
        },
    },
    "macd_bb_v1": {
        "macd_fast": 21,
        "macd_slow": 42,
        "macd_signal": 9,
        "bb_length": 100,
        "bb_std": 2.0,
        "bb_long_threshold": 0.3,
        "bb_short_threshold": 0.7,
        "max_executors": 5,
        "cooldown_time": 15,
        "position_executor": {
            "stop_loss": 0.01,
            "take_profit": 0.03,
            "time_limit": 21600,
        },
    },
    "trend_follower_v1": {
        "fast_period": 20,
        "slow_period": 50,
        "max_executors": 5,
        "cooldown_time": 15,
        "position_executor": {
            "stop_loss": 0.01,
            "take_profit": 0.03,
            "time_limit": 21600,
        },
    },
    "dman_v1": {
        "lookback": 40,
        "max_executors": 5,
        "cooldown_time": 15,
        "position_executor": {
            "stop_loss": 0.01,
            "take_profit": 0.03,
            "time_limit": 21600,
        },
    },
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", required=True, choices=sorted(TEMPLATES.keys()))
    args = parser.parse_args()

    payload = {"v2_strategies": {args.strategy: TEMPLATES[args.strategy]}}
    print(yaml.safe_dump(payload, sort_keys=False))


if __name__ == "__main__":
    main()
