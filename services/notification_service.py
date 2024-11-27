from telebot import TeleBot
from database.db_manager import DatabaseManager
from config.settings import DEFAULT_PLAN_PRICE
import logging
from datetime import datetime, timedelta
import threading
import time
import schedule

logger = logging.getLogger('notifications')


class NotificationService:
    def __init__(self, bot: TeleBot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager
        self._scheduler_thread = None
        self._stop_flag = threading.Event()
        self.notification_thresholds = {
            1: "⚠️ ВНИМАНИЕ! Через 24 часа ваши конфигурации будут удалены!"
        }

    # notification_service.py
    def check_user_devices_and_balance(self, user_id: int) -> None:
        """Проверка и списание ежедневной платы."""
        try:
            user = self.db_manager.get_user(user_id)
            if not user:
                return

            devices = self.db_manager.get_user_devices(user_id)
            if not devices:
                return

            # Стоимость за все устройства в день
            daily_cost = len(devices) * DEFAULT_PLAN_PRICE

            # Проверяем достаточно ли баланса
            if user.balance < daily_cost:
                self.db_manager.deactivate_user_devices(user_id)
                notification = (
                    "❌ *Внимание! Конфигурации деактивированы*\n\n"
                    f"💰 Баланс: {user.balance:.2f} руб.\n"
                    f"💸 Требуется: {daily_cost} руб/день\n\n"
                    "Пополните баланс и создайте новые конфигурации."
                )
                self.bot.send_message(user_id, notification, parse_mode='Markdown')
                return

            # Списываем ежедневную плату
            self.db_manager.update_balance(user_id, -daily_cost)

            # Считаем оставшиеся дни
            days_left = user.balance / daily_cost

            # Уведомление если осталось меньше 2 дней
            if days_left < 2:
                notification = (
                    "⚠️ *Внимание! Баланс подходит к концу*\n\n"
                    f"💰 Текущий баланс: {user.balance:.2f} руб.\n"
                    f"📱 Количество устройств: {len(devices)}\n"
                    f"💸 Стоимость в день: {daily_cost} руб.\n"
                    f"⏳ Хватит на {days_left:.1f} дней\n\n"
                    "Пополните баланс для продления работы конфигураций!"
                )
                self.bot.send_message(user_id, notification, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error checking devices for user {user_id}: {e}", exc_info=True)

    def check_all_users_devices_and_balance(self) -> None:
        """Проверка всех пользователей."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT telegram_id FROM users")
                users = cursor.fetchall()

                for user in users:
                    try:
                        self.check_user_devices_and_balance(user['telegram_id'])
                    except Exception as e:
                        logger.error(f"Error checking user {user['telegram_id']}: {e}")

        except Exception as e:
            logger.error(f"Error checking all users: {e}")

    def _scheduler_loop(self):
        """Основной цикл планировщика."""
        schedule.every().day.at("00:01").do(self.check_all_users_devices_and_balance)

        while not self._stop_flag.is_set():
            schedule.run_pending()
            time.sleep(60)

    def schedule_balance_checks(self) -> None:
        """Запуск планировщика проверок баланса."""
        if self._scheduler_thread is None or not self._scheduler_thread.is_alive():
            self._stop_flag.clear()
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                name="BalanceChecker",
                daemon=True
            )
            self._scheduler_thread.start()
            logger.info("Balance check scheduler started")

    def stop_scheduler(self) -> None:
        """Остановка планировщика."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._stop_flag.set()
            self._scheduler_thread.join(timeout=5)
            logger.info("Balance check scheduler stopped")