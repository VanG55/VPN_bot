import os
from typing import List, Optional
from datetime import datetime, timedelta
from database.models import Device
from database.db_manager import DatabaseManager
from config.settings import DEFAULT_PLAN_PRICE


class DeviceService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def get_user_devices(self, telegram_id: int) -> List[Device]:
        """Get all active devices for user."""
        return self.db_manager.get_user_devices(telegram_id)

    def can_add_device(self, telegram_id: int) -> bool:
        """Check if user can add new device."""
        user = self.db_manager.get_user(telegram_id)
        return user and user.balance >= DEFAULT_PLAN_PRICE

    # device_service.py
    def add_device(self, telegram_id: int, device_type: str) -> Optional[Device]:
        """Add new device."""
        if not self.can_add_device(telegram_id):
            return None

        current_time = datetime.now()
        expires_at = current_time + timedelta(minutes=2)  # для тестового тарифа

        config_data = self._generate_config(device_type)

        device = Device(
            telegram_id=telegram_id,
            device_type=device_type,
            config_data=config_data,
            created_at=current_time,
            expires_at=expires_at
        )

        device_id = self.db_manager.add_device(device)
        if device_id:
            self.db_manager.update_balance(telegram_id, -DEFAULT_PLAN_PRICE)
            device.id = device_id
            return device
        return None

    def can_add_device(self, telegram_id: int) -> bool:
        """Check if user can add new device."""
        user = self.db_manager.get_user(telegram_id)
        return user and user.balance >= DEFAULT_PLAN_PRICE

    def get_user_devices(self, telegram_id: int) -> List[Device]:
        """Get all active devices for user."""
        return self.db_manager.get_user_devices(telegram_id)

    def save_config_file(self, config_data: str, device_type: str) -> str:
        """Save config to temporary file."""
        filename = f"{device_type}_config_{datetime.now().timestamp()}.txt"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(config_data)
            return filename
        except Exception as e:
            print(f"Error saving config file: {e}")
            return ""

    def cleanup_config_file(self, filename: str) -> None:
        """Remove temporary config file."""
        try:
            if filename and os.path.exists(filename):
                os.remove(filename)
        except Exception as e:
            print(f"Error removing config file: {e}")

    @staticmethod
    def _generate_config(device_type: str) -> str:
        """Generate VPN configuration for device."""
        return f"""
# VPN Configuration for {device_type}
server = vpn.example.com
port = 1194
protocol = udp
cipher = AES-256-GCM
auth = SHA512
# Additional configuration parameters would go here
"""


__all__ = ['DeviceService']