from typing import Dict, Any
from datetime import datetime
from database.models import User
from database.db_manager import DatabaseManager
from config.settings import DEFAULT_PLAN_PRICE


class UserService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def get_or_create_user(self, telegram_user: Any) -> User:
        """Create or update user from telegram user object."""
        user = User(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name
        )
        self.db_manager.update_user(user)
        return self.db_manager.get_user(telegram_user.id)

    def get_user_info(self, telegram_id: int) -> Dict[str, Any]:
        """Get formatted user information for display."""
        user = self.db_manager.get_user(telegram_id)
        if not user:
            return {}

        devices_count = self.db_manager.get_active_devices_count(telegram_id)
        total_cost = DEFAULT_PLAN_PRICE * devices_count if devices_count > 0 else 0
        days_left = int(user.balance / total_cost) if total_cost > 0 else 0

        return {
            'display_name': user.display_name,
            'user_id': user.telegram_id,
            'balance': user.balance,
            'plan_price': DEFAULT_PLAN_PRICE,
            'devices_count': devices_count,
            'devices_word': self._get_devices_word(devices_count),
            'total_cost': total_cost,
            'days_left': days_left,
            'days_word': self._get_days_word(days_left),
            'current_time': datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        }

    @staticmethod
    def _get_devices_word(count: int) -> str:
        """Get correct form of word 'конфиг' based on count."""
        if count == 1:
            return 'конфиг'
        return 'конфигов'

    @staticmethod
    def _get_days_word(count: int) -> str:
        """Get correct form of word 'день' based on count."""
        if count == 1:
            return 'день'
        if 2 <= count <= 4:
            return 'дня'
        return 'дней'

    def update_balance(self, telegram_id: int, amount: float) -> None:
        """Update user balance."""
        self.db_manager.update_balance(telegram_id, amount)