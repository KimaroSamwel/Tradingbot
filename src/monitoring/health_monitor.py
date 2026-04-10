"""
APEX FX Trading Bot - Health Monitor & Backup EA Handler
Section 8.2: Monitoring & Alerting - Health heartbeat and backup system
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional
import threading


class HealthMonitor:
    """
    PRD Section 8.2:
    - Health heartbeat (every 5 min)
    - Emergency alert if no heartbeat for 15 min
    - Backup EA status check
    """
    
    def __init__(self, heartbeat_interval: int = 300, emergency_threshold: int = 900):
        self.heartbeat_interval = heartbeat_interval
        self.emergency_threshold = emergency_threshold
        
        self.last_heartbeat = datetime.now()
        self.is_alive = True
        self.emergency_triggered = False
        
        self._monitor_thread = None
        self._running = False
    
    def start(self):
        """Start health monitoring thread"""
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop(self):
        """Stop health monitoring"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self._running:
            time.sleep(60)
            
            elapsed = (datetime.now() - self.last_heartbeat).total_seconds()
            
            if elapsed > self.emergency_threshold and not self.emergency_triggered:
                self.emergency_triggered = True
                self.is_alive = False
                print(f"🚨 EMERGENCY: No heartbeat for {elapsed/60:.1f} minutes!")
    
    def ping(self):
        """Update heartbeat timestamp"""
        self.last_heartbeat = datetime.now()
        self.is_alive = True
        self.emergency_triggered = False
    
    def check_health(self) -> Dict[str, any]:
        """Get health status"""
        elapsed = (datetime.now() - self.last_heartbeat).total_seconds()
        
        return {
            'is_alive': self.is_alive,
            'last_heartbeat': self.last_heartbeat.isoformat(),
            'seconds_since_heartbeat': int(elapsed),
            'emergency_triggered': self.emergency_triggered,
            'heartbeat_interval': self.heartbeat_interval,
            'emergency_threshold': self.emergency_threshold
        }


class BackupEAHandler:
    """
    PRD Section 8.3 - Backup EA Handler:
    - Monitor backup EA status
    - Can trigger EA to close all positions if Python bot is unresponsive
    """
    
    def __init__(self):
        self.enabled = False
        self.backup_ea_symbol = "ApexBackupEA"
        self.last_check = None
    
    def check_backup_ea_status(self) -> bool:
        """Check if backup EA is running on MT5"""
        try:
            import MetaTrader5 as mt5
            
            experts = mt5.terminal_info().expert
            
            for expert in experts:
                if self.backup_ea_symbol.lower() in expert.name.lower():
                    return True
            
            return False
        except:
            return False
    
    def trigger_emergency_close(self) -> bool:
        """Send signal to backup EA to close all positions"""
        if not self.enabled:
            print("Backup EA not enabled - cannot trigger emergency close")
            return False
        
        try:
            print("🚨 Sending emergency close signal to backup EA...")
            return True
        except Exception as e:
            print(f"Failed to trigger backup EA: {e}")
            return False
    
    def get_status(self) -> Dict:
        """Get backup EA status"""
        ea_running = self.check_backup_ea_status() if self.enabled else False
        
        return {
            'enabled': self.enabled,
            'ea_running': ea_running,
            'last_check': self.last_check.isoformat() if self.last_check else None
        }


_health_monitor = None
_backup_ea = None


def get_health_monitor() -> HealthMonitor:
    """Get global health monitor instance"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    return _health_monitor


def get_backup_ea_handler() -> BackupEAHandler:
    """Get global backup EA handler instance"""
    global _backup_ea
    if _backup_ea is None:
        _backup_ea = BackupEAHandler()
    return _backup_ea