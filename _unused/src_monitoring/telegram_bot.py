"""Telegram monitoring/command helper."""

from __future__ import annotations

from typing import Dict, Iterable, List

try:
    import telebot
except Exception:  # pragma: no cover
    telebot = None


class TelegramCommandBot:
    """Send status/performance updates to authorized Telegram chats."""

    def __init__(self, token: str, chat_ids: Iterable[int]):
        self.token = str(token or "")
        self.authorized_chats = [int(c) for c in (chat_ids or [])]
        self.bot = telebot.TeleBot(self.token) if telebot and self.token else None

    @property
    def enabled(self) -> bool:
        return self.bot is not None and len(self.authorized_chats) > 0

    def send_message(self, text: str) -> Dict:
        if not self.enabled:
            return {"ok": False, "reason": "telegram_disabled"}

        delivered: List[int] = []
        errors: List[str] = []
        for chat_id in self.authorized_chats:
            try:
                self.bot.send_message(chat_id, text)
                delivered.append(chat_id)
            except Exception as exc:
                errors.append(f"{chat_id}:{exc}")

        return {"ok": len(errors) == 0, "delivered": delivered, "errors": errors}

    def send_performance_update(self, summary: Dict) -> Dict:
        text = (
            "SNIPER PRO Performance Update\n"
            f"PnL: {summary.get('pnl', 0.0)}\n"
            f"Win rate: {summary.get('win_rate', 0.0)}\n"
            f"Trades: {summary.get('trades', 0)}"
        )
        return self.send_message(text)
