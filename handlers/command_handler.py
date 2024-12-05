from telebot import TeleBot
from telebot.types import Message
from database.db_manager import DatabaseManager
from services.user_service import UserService
from services.payment_service import PaymentService
from services.support_service import SupportService
from .menu_handler import MenuHandler
from config.settings import MESSAGE_TEMPLATES, SUPPORT_GROUP_ID
import logging
from time import time
from collections import defaultdict
from services.device_service import DeviceService
from services.marzban_service import MarzbanService
from config.settings import (
    MARZBAN_HOST,
    MARZBAN_USERNAME,
    MARZBAN_PASSWORD
)

logger = logging.getLogger('command_handler')


class CommandRateLimit:
    def __init__(self):
        self.user_commands = defaultdict(list)
        self.time_window = 60  # Время в секундах для отслеживания команд
        self.max_commands = 3  # Максимальное количество команд в time_window
        self.blocked_users = {}  # Заблокированные пользователи и время блокировки
        self.block_duration = 300  # Длительность блокировки в секундах (5 минут)


    def _cleanup_old_commands(self, user_id: int):
        """Очистка старых команд."""
        current_time = time()
        self.user_commands[user_id] = [
            cmd_time for cmd_time in self.user_commands[user_id]
            if current_time - cmd_time < self.time_window
        ]

    def is_blocked(self, user_id: int) -> bool:
        """Проверка, заблокирован ли пользователь."""
        if user_id not in self.blocked_users:
            return False

        if time() - self.blocked_users[user_id] > self.block_duration:
            del self.blocked_users[user_id]
            return False

        return True

    def can_execute(self, user_id: int) -> tuple[bool, str]:
        """Проверка возможности выполнения команды."""
        # Проверка блокировки
        if self.is_blocked(user_id):
            remaining_time = int(self.block_duration - (time() - self.blocked_users[user_id]))
            return False, f"⛔️ Подождите {remaining_time} секунд перед следующей попыткой."

        # Очистка старых команд
        self._cleanup_old_commands(user_id)

        # Добавление новой команды
        current_time = time()
        self.user_commands[user_id].append(current_time)

        # Проверка количества команд
        if len(self.user_commands[user_id]) > self.max_commands:
            self.blocked_users[user_id] = current_time
            self.user_commands[user_id].clear()
            return False, "⛔️ Слишком много запросов. Вы заблокированы на 5 минут."

        return True, ""


class CommandHandler:
    def __init__(self, bot: TeleBot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager
        self.user_service = UserService(db_manager)
        self.payment_service = PaymentService(db_manager)
        self.support_service = SupportService(bot, db_manager)
        self.menu_handler = MenuHandler()
        self.rate_limiter = CommandRateLimit()
        self.marzban_service = MarzbanService(
            MARZBAN_HOST,
            MARZBAN_USERNAME,
            MARZBAN_PASSWORD
        )
        self.device_service = DeviceService(
            db_manager=self.db_manager,
            marzban_service=self.marzban_service,
            bot=self.bot  # Добавляем параметр bot
        )

    def register_handlers(self):
        """Register command handlers."""
        self.bot.message_handler(commands=['start'])(self.handle_start)
        self.bot.message_handler(commands=['help'])(self.handle_help)

        # Обработчик для ответов из канала поддержки
        self.bot.message_handler(
            func=lambda message: message.chat.id == SUPPORT_GROUP_ID and message.reply_to_message
        )(self.handle_support_reply)

        # Обработчик сообщений от пользователей в режиме поддержки
        self.bot.message_handler(
            func=lambda message: self.support_service.is_waiting_for_message(message.from_user.id)
        )(self.handle_user_support_message)

    def handle_start(self, message: Message):
        try:
            user_id = message.from_user.id
            args = message.text.split()

            # Проверка ограничения
            can_execute, error_message = self.rate_limiter.can_execute(user_id)
            if not can_execute:
                self.bot.reply_to(message, error_message)
                return

            # Создание или получение пользователя
            user = self.user_service.get_or_create_user(message.from_user)

            # Проверка реферальной ссылки
            if len(args) > 1 and args[1].startswith('ref'):
                try:
                    referrer_telegram_id = int(args[1].replace('ref', ''))
                    logger.info(f"Processing referral: referrer={referrer_telegram_id}, referee={user_id}")

                    # Проверяем существование реферера
                    referrer = self.db_manager.get_user(referrer_telegram_id)
                    if referrer:
                        # Создаем Trial конфиг для реферера (2 дня)
                        logger.info(f"Creating Trial config for referrer {referrer_telegram_id}")
                        referrer_config = self.device_service.add_device(
                            telegram_id=referrer_telegram_id,
                            device_type="Trial",
                            days=2
                        )
                        if referrer_config:
                            self.bot.send_message(
                                referrer_telegram_id,
                                "🎁 Вам начислен Trial конфиг на 2 дня за приглашение друга!"
                            )
                            logger.info(f"Trial config created for referrer: {referrer_config.marzban_username}")

                        # Создаем Trial конфиг для приглашенного (1 день)
                        logger.info(f"Creating Trial config for referee {user_id}")
                        referee_config = self.device_service.add_device(
                            telegram_id=user_id,
                            device_type="Trial",
                            days=1
                        )
                        if referee_config:
                            self.bot.send_message(
                                user_id,
                                "🎁 Вам начислен Trial конфиг на 1 день!"
                            )
                            logger.info(f"Trial config created for referee: {referee_config.marzban_username}")

                        # Добавляем реферальную связь
                        success = self.db_manager.add_referral(
                            referrer_telegram_id=referrer_telegram_id,
                            referee_telegram_id=user_id
                        )
                        logger.info(f"Referral link added: {success}")

                    else:
                        logger.warning(f"Referrer {referrer_telegram_id} not found")

                except Exception as e:
                    logger.error(f"Error processing referral: {e}", exc_info=True)

            # Проверяем возврат из оплаты
            if len(args) > 1 and args[1].startswith('payment_'):
                self._handle_payment_return(user_id)

            # Проверка принятия соглашения
            if not user or not user.agreement_accepted:
                agreement_text = (
                    "📜 *Пользовательское соглашение*\n\n"
                    "Пользуясь данным сервисом, Вы соглашаетесь с Условиями "
                    "Использования и Конфиденциальности.\n\n"
                    "Для ознакомления с пользовательским соглашением перейдите "
                    "по ссылке: [Пользовательское соглашение](https://telegra.ph/Polzovatelskoe-soglashenie-11-16-9)"
                )
                self.bot.send_message(
                    message.chat.id,
                    agreement_text,
                    parse_mode='Markdown',
                    reply_markup=self.menu_handler.create_agreement_menu()
                )
                return

            # Отправка основного меню
            user_info = self.user_service.get_user_info(user.telegram_id)
            text = MESSAGE_TEMPLATES['welcome'].format(**user_info)
            self.bot.send_message(
                message.chat.id,
                text,
                parse_mode='Markdown',
                reply_markup=self.menu_handler.create_main_menu()
            )

        except Exception as e:
            logger.error(f"Error handling start command: {e}", exc_info=True)
            self.bot.reply_to(message, "Произошла ошибка. Попробуйте позже.")

    def _handle_payment_return(self, user_id: int):
        """Обработка возврата после оплаты."""
        try:
            transactions = self.db_manager.get_pending_transactions(user_id)
            if not transactions:
                logger.info(f"No pending transactions found for user {user_id}")
                return

            latest_transaction = transactions[0]
            logger.info(f"Checking payment status for transaction {latest_transaction.payment_id}")

            payment_status = self.payment_service.check_payment_status(
                latest_transaction.payment_id
            )
            logger.info(f"Payment status received: {payment_status}")

            if payment_status and payment_status.get('paid'):
                logger.info(f"Processing successful payment for user {user_id}")
                # Обновляем баланс
                self.db_manager.update_balance(user_id, latest_transaction.amount)
                # Обновляем статус транзакции
                self.db_manager.update_transaction_status(latest_transaction.payment_id, 'completed')

                # Отправляем уведомление
                success_message = (
                    "✅ Успешное пополнение\n\n"
                    f"**Ваш баланс пополнен на {latest_transaction.amount:.2f} руб**\n"
                )
                user_info = self.user_service.get_user_info(user_id)
                success_message += f"**Текущий баланс: {user_info['balance']:.2f} руб**"
                self.bot.send_message(user_id, success_message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error handling payment return: {e}")

    def handle_help(self, message: Message):
        """Handle /help command."""
        try:
            can_execute, error_message = self.rate_limiter.can_execute(message.from_user.id)
            if not can_execute:
                self.bot.reply_to(message, error_message)
                return

            self.bot.send_message(
                message.chat.id,
                MESSAGE_TEMPLATES['help'],
                parse_mode='Markdown',
                reply_markup=self.menu_handler.create_help_menu()
            )
        except Exception as e:
            logger.error(f"Error handling help command: {e}")
            self.bot.reply_to(
                message,
                "Произошла ошибка. Попробуйте позже."
            )

    def handle_support_reply(self, message: Message):
        """Handle reply from support channel."""
        try:
            self.support_service.handle_support_reply(message)
        except Exception as e:
            logger.error(f"Error handling support reply: {e}")
            self.bot.reply_to(
                message,
                "Произошла ошибка при отправке ответа."
            )

    def handle_user_support_message(self, message: Message):
        """Handle message from user in support mode."""
        try:
            can_execute, error_message = self.rate_limiter.can_execute(message.from_user.id)
            if not can_execute:
                self.bot.reply_to(message, error_message)
                return

            self.support_service.forward_to_support(message)
        except Exception as e:
            logger.error(f"Error handling support message: {e}")
            self.bot.reply_to(
                message,
                "Произошла ошибка. Попробуйте позже."
            )