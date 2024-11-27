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
                    logger.info(f"Referral link from {referrer_telegram_id} to {user_id}")

                    # Проверяем существование реферера
                    referrer = self.db_manager.get_user(referrer_telegram_id)
                    if referrer:
                        # Добавляем связь в таблицу referrals
                        success = self.db_manager.add_referral(
                            referrer_telegram_id=referrer_telegram_id,
                            referee_telegram_id=user_id
                        )
                        logger.info(f"Added referral link: {success}")
                        if success:
                            self.bot.send_message(
                                referrer_telegram_id,
                                f"👥 Новый реферал присоединился к боту!"
                            )
                except Exception as e:
                    logger.error(f"Error processing referral: {e}")

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
                    disable_web_page_preview=True,
                    reply_markup=self.menu_handler.create_agreement_menu()
                )
                return

            # Проверка наличия параметров команды (deep linking)
            if len(args) > 1 and args[1].startswith('payment_'):
                transactions = self.db_manager.get_pending_transactions(user_id)
                if transactions:
                    latest_transaction = transactions[0]
                    payment_status = self.payment_service.check_payment_status(latest_transaction.payment_id)
                    if payment_status and payment_status.get('paid'):
                        success_message = (
                            "✅ Успешное пополнение\n\n"
                            f"**Агрегатор: ЮKassa**\n\n"
                            f"**Payment ID: {latest_transaction.payment_id}**\n\n"
                            f"**Ваш баланс пополнен на {latest_transaction.amount:.2f} руб**\n"
                        )
                        user_info = self.user_service.get_user_info(user_id)
                        success_message += f"**Текущий баланс: {user_info['balance']:.2f} руб**"
                        self.bot.reply_to(message, success_message, parse_mode='Markdown')
                    else:
                        self.bot.reply_to(
                            message,
                            "❌ Платёж не найден или ещё не оплачен\n"
                            "Попробуйте позже или создайте новый платёж."
                        )
                else:
                    logger.warning(f"No pending transactions found for user {user_id}")
                    self.bot.reply_to(
                        message,
                        "❌ Платёж не найден. Попробуйте создать новый платёж."
                    )

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
            self.bot.reply_to(
                message,
                "Произошла ошибка. Попробуйте позже."
            )

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