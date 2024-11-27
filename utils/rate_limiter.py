from collections import defaultdict
import time
from functools import wraps
from typing import Callable, Dict, List, Tuple
import logging
from telebot.types import CallbackQuery

logger = logging.getLogger('rate_limiter')


class RateLimiter:
    def __init__(self):
        self.user_clicks: Dict[int, List[float]] = defaultdict(list)
        # Увеличиваем пороги
        self.warn_threshold = 15  # Было 5, делаем 15 кликов для предупреждения
        self.block_threshold = 30  # Было 10, делаем 30 кликов для блокировки
        self.time_window = 60  # Оставляем 60 секунд
        self.blocked_users: Dict[int, float] = {}
        self.block_duration = 300  # Оставляем 5 минут блокировки

    def _cleanup_old_clicks(self, user_id: int) -> None:
        """Очистка старых кликов."""
        current_time = time.time()
        self.user_clicks[user_id] = [
            click_time for click_time in self.user_clicks[user_id]
            if current_time - click_time < self.time_window
        ]

    def is_blocked(self, user_id: int) -> bool:
        """Проверка, заблокирован ли пользователь."""
        if user_id not in self.blocked_users:
            return False

        if time.time() - self.blocked_users[user_id] > self.block_duration:
            del self.blocked_users[user_id]
            return False

        return True

    def add_click(self, user_id: int) -> Tuple[bool, str]:
        """
        Добавление клика и проверка ограничений.
        Возвращает (можно_ли_продолжить, сообщение).
        """
        if self.is_blocked(user_id):
            remaining_time = int(self.block_duration -
                                 (time.time() - self.blocked_users[user_id]))
            return False, f"⛔️ Вы заблокированы на {remaining_time} секунд за спам"

        self._cleanup_old_clicks(user_id)
        current_time = time.time()
        self.user_clicks[user_id].append(current_time)
        clicks_count = len(self.user_clicks[user_id])

        if clicks_count >= self.block_threshold:
            self.blocked_users[user_id] = current_time
            self.user_clicks[user_id].clear()
            logger.warning(f"User {user_id} blocked for spam")
            return False, "⛔️ Вы заблокированы на 5 минут за спам"

        if clicks_count >= self.warn_threshold:
            remaining_clicks = self.block_threshold - clicks_count
            return True, f"⚠️ Предупреждение: замедлите! Осталось {remaining_clicks} нажатий"

        return True, ""

    @staticmethod
    def limit_rate(func: Callable):
        """Декоратор для ограничения частоты нажатий на кнопки."""

        @wraps(func)
        def wrapper(self, call: CallbackQuery, *args, **kwargs):
            can_continue, message = self.rate_limiter.add_click(call.from_user.id)

            if not can_continue:
                self.bot.answer_callback_query(call.id, message)
                return

            if message:  # Предупреждение
                self.bot.answer_callback_query(call.id, message)

            return func(self, call, *args, **kwargs)

        return wrapper