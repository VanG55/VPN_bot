import sys
from pathlib import Path
import threading
from flask import Flask, request, jsonify
import hmac
import hashlib
from yookassa import Configuration

# Добавляем путь проекта в PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

import telebot
from database.db_manager import DatabaseManager
from handlers.command_handler import CommandHandler
from handlers.callback_handler import CallbackHandler
from services.backup_service import BackupService
from services.notification_service import NotificationService
from services.payment_service import PaymentService
from services.qr_service import QRService
from utils.network import check_network_connectivity, test_telegram_api
from utils.rate_limiter import RateLimiter
from utils.helpers import setup_logger, print_fancy_header
from config.settings import TOKEN, DB_NAME

# Инициализация логгера
logger = setup_logger(__name__)

# Инициализация Flask для вебхуков
app = Flask(__name__)
payment_service = None


@app.route('/payment-notification', methods=['POST'])
def payment_notification():
    try:
        # Получаем данные уведомления
        notification_data = request.get_json()

        # Проверяем подпись уведомления
        signature = request.headers.get('X-YooKassa-Signature')
        if not verify_webhook_signature(signature, request.get_data().decode('utf-8')):
            return jsonify({'error': 'Invalid signature'}), 400

        # Обрабатываем уведомление
        result = payment_service.handle_notification(notification_data)

        if result:
            return jsonify({'success': True}), 200
        else:
            return jsonify({'success': False}), 400

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({'error': str(e)}), 500


def verify_webhook_signature(signature: str, body: str) -> bool:
    """Verify YooKassa webhook signature."""
    try:
        if not signature:
            return False

        secret_key = Configuration.secret_key
        hmac_obj = hmac.new(
            secret_key.encode(),
            body.encode(),
            hashlib.sha1
        )
        calculated_signature = hmac_obj.hexdigest()

        return signature == calculated_signature

    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        return False


def run_webhook_server():
    """Запуск вебхук-сервера."""
    app.run(host='0.0.0.0', port=8080, debug=False)


class VPNBot:
    def __init__(self):
        self.bot = telebot.TeleBot(TOKEN)
        self.db_manager = DatabaseManager(DB_NAME)
        self.backup_service = BackupService(DB_NAME)
        self.notification_service = NotificationService(self.bot, self.db_manager)
        self.qr_service = QRService()
        self.rate_limiter = RateLimiter()
        self.payment_service = PaymentService(self.db_manager)
        self.backup_service.setup_auto_cleanup(max_backups=5)

        # Устанавливаем payment_service для вебхук-сервера
        global payment_service
        payment_service = self.payment_service

        # Инициализация обработчиков
        self.command_handler = CommandHandler(self.bot, self.db_manager)
        self.callback_handler = CallbackHandler(
            bot=self.bot,
            db_manager=self.db_manager,
            qr_service=self.qr_service,
            rate_limiter=self.rate_limiter
        )

    def setup(self):
        """Настройка бота перед запуском."""
        try:
            # Проверка подключения к интернету и Telegram API
            logger.info("Checking network connectivity...")
            if not check_network_connectivity():
                logger.error("No internet connection!")
                return False

            logger.info("Testing Telegram API connection...")
            if not test_telegram_api():
                logger.error("Cannot connect to Telegram API!")
                return False

            # Создание начального бэкапа
            logger.info("Creating initial backup...")
            backup_path = self.backup_service.create_backup()
            if backup_path:
                logger.info(f"Backup created successfully: {backup_path}")
            else:
                logger.warning("Failed to create initial backup")

            # Запуск планировщиков
            logger.info("Starting schedulers...")
            self.backup_service.schedule_backups()
            self.notification_service.schedule_balance_checks()

            # Регистрация обработчиков
            logger.info("Registering handlers...")
            self.command_handler.register_handlers()
            self.callback_handler.register_handlers()

            logger.info("Bot setup completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error during bot setup: {e}")
            return False

    def run(self):
        """Запуск бота."""
        print_fancy_header(TOKEN, DB_NAME)

        if not self.setup():
            logger.error("Bot setup failed, exiting...")
            sys.exit(1)

        # Запускаем вебхук-сервер в отдельном потоке
        webhook_thread = threading.Thread(target=run_webhook_server, daemon=True)
        webhook_thread.start()

        logger.info("🤖 Bot is running...")

        try:
            self.bot.polling(none_stop=True)
        except Exception as e:
            logger.error(f"❌ Critical error: {e}", exc_info=True)
        finally:
            # Создаем финальный бэкап перед выключением
            logger.info("Creating final backup...")
            self.backup_service.create_backup()
            logger.info("👋 Bot stopped")

    @staticmethod
    def handle_exception(exc_type, exc_value, exc_traceback):
        """Обработка необработанных исключений."""
        logger.error(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback)
        )


def main():
    """Основная функция запуска бота."""
    # Установка обработчика необработанных исключений
    sys.excepthook = VPNBot.handle_exception

    # Создание и запуск бота
    vpn_bot = VPNBot()
    vpn_bot.run()


if __name__ == '__main__':
    main()