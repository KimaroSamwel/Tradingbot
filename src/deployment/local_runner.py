"""Local deployment helper with encrypted config support."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Dict, Optional

try:
    from cryptography.fernet import Fernet
except Exception:  # pragma: no cover
    Fernet = None


class LocalDeploymentRunner:
    """Run bot locally with encrypted config + env-based key loading."""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self.load_encrypted_config(str(self.config_path))
        self.api_keys = self.load_from_secure_storage()

    def _get_fernet(self) -> Optional[object]:
        if Fernet is None:
            return None
        key = os.getenv("SNIPER_CONFIG_KEY", "")
        if not key:
            return None
        try:
            return Fernet(key.encode("utf-8"))
        except Exception:
            return None

    def load_encrypted_config(self, path: str) -> Dict:
        raw = Path(path).read_bytes()

        # Try Fernet first if available.
        fernet = self._get_fernet()
        if fernet is not None:
            try:
                decrypted = fernet.decrypt(raw)
                return json.loads(decrypted.decode("utf-8"))
            except Exception:
                pass

        # Fallback to base64-json for portability.
        try:
            decoded = base64.b64decode(raw)
            return json.loads(decoded.decode("utf-8"))
        except Exception:
            pass

        # Final fallback to plain JSON/YAML-like dict via json.
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def load_from_secure_storage(self) -> Dict[str, str]:
        return {
            "mt5_login": os.getenv("MT5_LOGIN", ""),
            "mt5_password": os.getenv("MT5_PASSWORD", ""),
            "mt5_server": os.getenv("MT5_SERVER", ""),
            "telegram_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        }
