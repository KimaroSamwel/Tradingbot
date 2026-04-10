"""
APEX FX Trading Bot - Configuration Manager
Handles all configuration loading and validation
"""

import os
import json
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigManager:
    """Central configuration management"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.config_dir = self.base_dir / "config"
        self._config = {}
        self._load_all()
    
    def _load_all(self):
        """Load all configuration files"""
        # Main config.yaml
        self._config['main'] = self._load_yaml('config.yaml')
        
        # Broker configs
        self._config['mt5'] = self._load_yaml('mt5_config.yaml')
        self._config['binance'] = self._load_yaml('binance_config.yaml')
        
        # Risk config
        self._config['risk'] = self._load_json('risk_config.json')
        
        # Strategy configs
        self._config['strategies'] = self._load_yaml('strategies_config.yaml')
        
        # Pairs config
        self._config['pairs'] = self._load_yaml('pairs_config.yaml')
        
        # Watchlist
        self._config['watchlist'] = self._load_yaml('watchlist.yaml')
        
        # Paper trading config
        self._config['paper'] = self._load_yaml('paper_config.yaml')
        
    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """Load YAML configuration"""
        path = self.config_dir / filename
        if not path.exists():
            return {}
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return {}
    
    def _load_json(self, filename: str) -> Dict[str, Any]:
        """Load JSON configuration"""
        path = self.config_dir / filename
        if not path.exists():
            return {}
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by key"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Set config value by key"""
        keys = key.split('.')
        target = self._config
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value
        
        # Update the YAML file if it's a top-level key
        if keys[0] == 'trading':
            self._save_yaml('config.yaml')
    
    def _save_yaml(self, filename: str) -> None:
        """Save YAML configuration"""
        path = self.config_dir / filename
        try:
            with open(path, 'w') as f:
                yaml.safe_dump(self._config.get('main', {}), f, default_flow_style=False)
        except Exception as e:
            print(f"Error saving {filename}: {e}")
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration"""
        return self._config
    
    def reload(self):
        """Reload all configurations"""
        self._config = {}
        self._load_all()


# Global config instance
config = ConfigManager()


def get_config() -> ConfigManager:
    """Get global config instance"""
    return config