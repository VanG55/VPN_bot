from telebot import TeleBot
from database.db_manager import DatabaseManager
from config.settings import DEFAULT_PLAN_PRICE
import logging
from datetime import datetime, timedelta
import threading
import time
import schedule

logger = logging.getLogger('notifications')  # Добавляем этот логгер в начало файла

class NotificationService:
    def __init__(self, bot: TeleBot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager
        self._scheduler_thread = None
        self._stop_flag = threading.Event()
        self.notification_thresholds = {
            1: "⚠️ ВНИМАНИЕ! Через 24 часа ваши конфигурации будут удалены!"
        }
        self.logger = logger  # Используем созданный логгер

    # notification_service.py
    def check_user_devices_expiration(self, user_id: int) -> None:
        try:
            devices = self.db_manager.get_user_devices(user_id)
            current_time = datetime.now()

            for device in devices:
                if device.expires_at and current_time > device.expires_at:
                    try:
                        self.marzban_service.delete_user(device.marzban_username)
                        self.db_manager.deactivate_device(device.id)
                    except Exception as e:
                        logger.error(f"Error deactivating expired device: {e}")

        except Exception as e:
            logger.error(f"Error checking user devices: {e}")

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

    def check_marzban_configs(self):
        """Проверка состояния конфигураций в Marzban."""
        try:
            devices = self.db_manager.get_all_active_devices()
            for device in devices:
                config = self.marzban.get_user_config(device.marzban_username)
                if not config or config.get('status') == 'disabled':
                    self.db_manager.deactivate_device(device.id)
                    self.bot.send_message(
                        device.telegram_id,
                        f"❌ Ваша конфигурация {device.device_type} была деактивирована.\n"
                        "Пожалуйста, создайте новую."
                    )
        except Exception as e:
            self.logger.error(f"Error checking Marzban configs: {e}")

    def check_device_expiration(self):
        """Проверка истечения срока устройств."""
        try:
            current_time = datetime.now()
            devices = self.db_manager.get_all_active_devices()

            for device in devices:
                if device.expires_at and current_time > device.expires_at:
                    # Деактивируем в Marzban
                    self.marzban.delete_user(device.marzban_username)

                    # Деактивируем в БД
                    self.db_manager.deactivate_device(device.id)

                    # Уведомляем пользователя
                    message = (
                        "⚠️ *Внимание!*\n"
                        f"Ваше устройство {device.device_type} деактивировано "
                        f"в связи с истечением срока действия.\n"
                        "Для продолжения работы необходимо создать новую конфигурацию."
                    )

                    self.bot.send_message(
                        device.telegram_id,
                        message,
                        parse_mode='Markdown'
                    )

                elif device.expires_at:
                    # Проверяем, осталось ли меньше 24 часов
                    time_left = device.expires_at - current_time
                    if timedelta(0) <= time_left <= timedelta(days=1):
                        message = (
                            "⚠️ *Внимание!*\n"
                            f"Ваше устройство {device.device_type} будет деактивировано через "
                            f"{int(time_left.total_seconds() / 3600)} часов.\n"
                            "Рекомендуем продлить подписку заранее."
                        )

                        self.bot.send_message(
                            device.telegram_id,
                            message,
                            parse_mode='Markdown'
                        )

        except Exception as e:
            self.logger.error(f"Error checking device expiration: {e}")

        def check_marzban_configs(self):
            """Проверка актуальности конфигов в Marzban."""
            try:
                devices = self.db_manager.get_all_active_devices()
                for device in devices:
                    # Проверяем существование конфига в Marzban
                    marzban_config = self.marzban.get_user_config(device.marzban_username)

                    # Если конфиг не найден в Marzban
                    if not marzban_config:
                        # Деактивируем устройство в БД
                        self.db_manager.deactivate_device(device.id)

                        # Уведомляем пользователя
                        message = (
                            "❌ *Внимание!*\n"
                            f"Конфигурация `{device.marzban_username}` была удалена.\n"
                            "Для продолжения работы необходимо создать новую конфигурацию."
                        )

                        try:
                            self.bot.send_message(
                                device.telegram_id,
                                message,
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            self.logger.error(f"Error sending notification: {e}")

            except Exception as e:
                self.logger.error(f"Error checking Marzban configs: {e}")