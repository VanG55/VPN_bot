from telebot import TeleBot
from telebot.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from database.db_manager import DatabaseManager
from services.user_service import UserService
from services.device_service import DeviceService
from services.payment_service import PaymentService
from services.support_service import SupportService
from services.qr_service import QRService
from utils.rate_limiter import RateLimiter
from .menu_handler import MenuHandler
from config.settings import MESSAGE_TEMPLATES, SUPPORT_WELCOME_MESSAGE
import logging
from datetime import datetime
from datetime import datetime, timedelta, timezone
from config.settings import DEFAULT_PLAN_PRICE
from database.models import Device

logger = logging.getLogger('callback_handler')


class CallbackHandler:
    def __init__(
            self,
            bot: TeleBot,
            db_manager: DatabaseManager,
            qr_service: QRService = None,
            rate_limiter: RateLimiter = None
    ):
        self.bot = bot
        self.db_manager = db_manager
        self.qr_service = qr_service or QRService()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.user_service = UserService(db_manager)
        self.device_service = DeviceService(db_manager)
        self.payment_service = PaymentService(db_manager)
        self.support_service = SupportService(bot, db_manager)
        self.menu_handler = MenuHandler()
        self.user_states = {}

    def register_handlers(self):
        """Register callback query handlers."""
        self.bot.callback_query_handler(func=lambda call: True)(self.handle_callback)
        self.bot.message_handler(
            func=lambda message: self.support_service.is_waiting_for_message(message.from_user.id)
        )(self.handle_support_message)

    def handle_callback(self, call: CallbackQuery):
        """Route callback queries to appropriate handlers."""
        try:
            # Проверка и соглашение
            user = self.db_manager.get_user(call.from_user.id)
            if not user:
                self.bot.answer_callback_query(call.id, "Нужно запустить бота командой /start")
                return

            if not user.agreement_accepted and call.data != 'accept_agreement':
                agreement_text = (
                    "📜 *Пользовательское соглашение*\n\n"
                    "Для использования бота необходимо принять соглашение"
                )
                self.bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=agreement_text,
                    parse_mode='Markdown',
                    reply_markup=self.menu_handler.create_agreement_menu()
                )
                return

            # Проверка ограничения частоты
            can_continue, message = self.rate_limiter.add_click(call.from_user.id)
            if not can_continue:
                self.bot.answer_callback_query(call.id, message)
                return

            if message:  # Предупреждение
                self.bot.answer_callback_query(call.id, message)

            handlers = {
                'accept_agreement': self.handle_agreement_acceptance,
                'update': self.handle_update,
                'my_devices': self.handle_devices,
                'top_up': self.handle_top_up,
                'help': self.handle_help,
                'back_to_menu': self.handle_back_to_menu,
                'add_device': self.handle_add_device,
                'start_support': self.handle_start_support,
                'referral': self.handle_referral,  # Добавляем обработчик для реферальной системы
                'custom_amount': self.handle_custom_amount,
                'payment_history': self.handle_payment_history
            }

            if call.data in handlers:
                handlers[call.data](call)
            elif call.data.startswith('top_up_'):
                self.handle_top_up_amount(call)
            elif call.data.startswith('select_device_'):
                self.handle_select_device(call)

        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            self.bot.answer_callback_query(
                call.id,
                "Произошла ошибка. Попробуйте еще раз."
            )

    def handle_cancel_input(self, call: CallbackQuery):
        """Handle cancel button press during input."""
        try:
            # Очищаем состояние пользователя
            if call.from_user.id in self.user_states:
                del self.user_states[call.from_user.id]

            # Возвращаемся к меню пополнения
            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=MESSAGE_TEMPLATES['top_up_info'],
                parse_mode='Markdown',
                reply_markup=self.menu_handler.create_top_up_menu()
            )
            self.bot.answer_callback_query(call.id)
        except Exception as e:
            logger.error(f"Error handling cancel input: {e}")
            self.bot.answer_callback_query(
                call.id,
                "Произошла ошибка. Попробуйте еще раз."
            )

    def handle_custom_amount(self, call: CallbackQuery):
        """Handle custom amount top up."""
        try:
            msg = "Введите сумму пополнения (от 10 до 10000 руб):"
            sent_msg = self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=msg,
                reply_markup=self.menu_handler.create_cancel_menu()
            )

            # Регистрируем следующий шаг
            self.bot.register_next_step_handler(sent_msg, self.process_custom_amount)

        except Exception as e:
            logger.error(f"Error handling custom amount: {e}")
            self.bot.answer_callback_query(
                call.id,
                "Произошла ошибка. Попробуйте еще раз."
            )

    def process_custom_amount(self, message: Message):
        """Process custom amount message."""
        try:
            user_id = message.from_user.id

            try:
                amount = float(message.text.replace(',', '.'))
                if 10 <= amount <= 10000:
                    if not hasattr(self, 'user_states'):
                        self.user_states = {}

                    self.user_states[user_id] = {'action': 'waiting_email', 'amount': amount}

                    msg = ("Введите email для отправки чека.\n"
                           "❗️ Email будет использован только для отправки чека об оплате.")

                    sent_msg = self.bot.send_message(
                        message.chat.id,
                        msg,
                        reply_markup=self.menu_handler.create_cancel_menu()  # Используем существующий метод
                    )

                    self.bot.register_next_step_handler(sent_msg, self.process_email_input)
                else:
                    self.bot.reply_to(
                        message,
                        "❌ Сумма должна быть от 10 до 10000 руб.\nПопробуйте еще раз.",
                        reply_markup=self.menu_handler.create_cancel_menu()  # Используем существующий метод
                    )
            except ValueError:
                self.bot.reply_to(
                    message,
                    "❌ Пожалуйста, введите корректную сумму числом.",
                    reply_markup=self.menu_handler.create_cancel_menu()  # Используем существующий метод
                )

        except Exception as e:
            logger.error(f"Error processing custom amount: {e}", exc_info=True)
            self.bot.reply_to(
                message,
                "Произошла ошибка. Попробуйте еще раз."
            )

    def handle_payment_history(self, call: CallbackQuery):
        """Handle payment history button press."""
        try:
            # Получаем только успешные транзакции
            transactions = self.db_manager.get_user_transactions(call.from_user.id)

            if not transactions:
                text = "*📊 История пополнений*\n\nУ вас пока нет успешных пополнений."
            else:
                text = "*📊 История пополнений*\n\n"
                for tx in transactions:
                    date = tx['created_at']
                    if isinstance(date, str):
                        date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
                    date_str = date.strftime("%d.%m.%Y %H:%M")
                    text += (
                        f"✅ {date_str}\n"
                        f"└ Сумма: {tx['amount']:.2f}₽\n\n"
                    )

            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode='Markdown',
                reply_markup=self.menu_handler.create_back_to_menu()
            )

        except Exception as e:
            logger.error(f"Error showing payment history: {e}")
            self.bot.answer_callback_query(
                call.id,
                "Произошла ошибка. Попробуйте еще раз."
            )

    def handle_payment_history(self, call: CallbackQuery):
        """Handle payment history button press."""
        try:
            transactions = self.db_manager.get_user_transactions(call.from_user.id)

            if not transactions:
                text = "📊 История пополнений\n\nУ вас пока нет успешных пополнений."
            else:
                text = "📊 История пополнений\n\n"
                for tx in transactions:
                    try:
                        # Безопасное получение и форматирование даты
                        created_at = tx['created_at']
                        if isinstance(created_at, str):
                            try:
                                # Пробуем разные форматы даты
                                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                                    try:
                                        date_obj = datetime.strptime(created_at, fmt)
                                        created_at = date_obj.strftime("%d.%m.%Y %H:%M")
                                        break
                                    except ValueError:
                                        continue
                            except Exception:
                                created_at = "Дата неизвестна"

                        amount = float(tx['amount'])
                        text += f"✅ {created_at}\n└ Сумма: {amount:.2f}₽\n\n"

                    except Exception as e:
                        logger.error(f"Error formatting transaction: {e}")
                        # Если что-то пошло не так, просто показываем сумму
                        try:
                            amount = float(tx['amount'])
                            text += f"✅ Сумма: {amount:.2f}₽\n\n"
                        except:
                            text += "✅ Транзакция\n\n"

            # Отправляем сообщение без Markdown разметки
            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                reply_markup=self.menu_handler.create_back_to_menu()
            )

        except Exception as e:
            logger.error(f"Error showing payment history: {e}")
            self.bot.answer_callback_query(
                call.id,
                "Произошла ошибка. Попробуйте еще раз."
            )

        except Exception as e:
            logger.error(f"Error showing payment history: {e}")
            self.bot.answer_callback_query(
                call.id,
                "Произошла ошибка. Попробуйте еще раз."
            )

    def handle_update(self, call: CallbackQuery):
        """Handle update button press."""
        try:
            user_info = self.user_service.get_user_info(call.from_user.id)
            text = MESSAGE_TEMPLATES['welcome'].format(**user_info)

            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode='Markdown',
                reply_markup=self.menu_handler.create_main_menu()
            )
        except Exception as e:
            if "message is not modified" in str(e):
                self.bot.answer_callback_query(call.id, "ℹ️ Информация уже актуальна")
            else:
                logger.error(f"Error updating main menu: {e}")
                self.bot.answer_callback_query(
                    call.id,
                    "Произошла ошибка при обновлении. Попробуйте еще раз."
                )

    def handle_devices(self, call: CallbackQuery):
        try:
            devices = self.device_service.get_user_devices(call.from_user.id)
            devices_info = "*📱 Список ваших устройств:*\n\n"

            current_time = datetime.now()
            if devices:
                for i, device in enumerate(devices, 1):
                    try:
                        if isinstance(device.created_at, str):
                            created = datetime.strptime(device.created_at.split('.')[0], "%Y-%m-%d %H:%M:%S")
                        else:
                            created = device.created_at

                        if isinstance(device.expires_at, str):
                            expires = datetime.strptime(device.expires_at.split('.')[0], "%Y-%m-%d %H:%M:%S")
                        else:
                            expires = device.expires_at

                        devices_info += (
                            f"{i}. *{device.device_type}*\n"
                            f"   📅 Создано: {created.strftime('%Y-%m-%d %H:%M:%S')} (МСК)\n"
                            f"   🕒 Истекает: {expires.strftime('%Y-%m-%d %H:%M:%S')} (МСК)\n"
                            f"   ✅ Активен\n\n"
                        )
                    except Exception as e:
                        logger.error(f"Error formatting device: {e}")
            else:
                devices_info += "У вас пока нет активных устройств.\n\n"

            devices_info += "_(для установки VPN нажмите 'Добавить устройство')_"

            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=devices_info,
                parse_mode='Markdown',
                reply_markup=self.menu_handler.create_devices_menu()
            )
        except Exception as e:
            logger.error(f"Error handling devices menu: {e}")
            self.bot.answer_callback_query(
                call.id,
                "Произошла ошибка. Попробуйте еще раз."
            )

    def handle_top_up(self, call: CallbackQuery):
        """Handle top up button press."""
        try:
            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=MESSAGE_TEMPLATES['top_up_info'],
                parse_mode='Markdown',
                reply_markup=self.menu_handler.create_top_up_menu()
            )
        except Exception as e:
            logger.error(f"Error showing top up menu: {e}")
            self.bot.answer_callback_query(
                call.id,
                "Произошла ошибка. Попробуйте еще раз."
            )

    def handle_help(self, call: CallbackQuery):
        """Handle help button press."""
        try:
            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=MESSAGE_TEMPLATES['help'],
                parse_mode='Markdown',
                reply_markup=self.menu_handler.create_help_menu()
            )
        except Exception as e:
            logger.error(f"Error showing help menu: {e}")
            self.bot.answer_callback_query(
                call.id,
                "Произошла ошибка. Попробуйте еще раз."
            )

    def handle_back_to_menu(self, call: CallbackQuery):
        """Handle back to menu button press."""
        try:
            # Отменяем режим поддержки, если он был активен
            self.support_service.cancel_support_dialog(call.from_user.id)
            self.handle_update(call)
        except Exception as e:
            logger.error(f"Error returning to main menu: {e}")
            self.bot.answer_callback_query(
                call.id,
                "Произошла ошибка. Попробуйте еще раз."
            )

    def handle_add_device(self, call: CallbackQuery):
        """Handle add device button press."""
        try:
            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="*Выберите тип устройства:*",
                parse_mode='Markdown',
                reply_markup=self.menu_handler.create_device_types_menu()
            )
        except Exception as e:
            logger.error(f"Error showing device types menu: {e}")
            self.bot.answer_callback_query(
                call.id,
                "Произошла ошибка. Попробуйте еще раз."
            )

    def handle_top_up_amount(self, call: CallbackQuery):
        """Handle top up amount selection."""
        try:
            # Сохраняем выбранную сумму во временное хранилище
            amount = float(call.data.split('_')[2])
            self.user_states[call.from_user.id] = {'action': 'waiting_email', 'amount': amount}

            # Запрашиваем email
            msg = ("Введите email для отправки чека.\n"
                   "❗️ Email будет использован только для отправки чека об оплате.")

            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=msg,
                reply_markup=self.menu_handler.create_cancel_menu()  # Заменили на create_cancel_menu
            )

            # Регистрируем обработчик для следующего сообщения
            self.bot.register_next_step_handler(call.message, self.process_email_input)

        except Exception as e:
            logger.error(f"Error handling top up amount: {e}")
            self.bot.answer_callback_query(
                call.id,
                "Произошла ошибка. Попробуйте еще раз."
            )

    def process_email_input(self, message: Message):
        """Process email input for payment."""
        try:
            user_id = message.from_user.id
            if user_id not in self.user_states:
                self.bot.reply_to(message, "Произошла ошибка. Начните процесс оплаты заново.")
                return

            email = message.text.strip().lower()
            # Простая валидация email
            if '@' not in email or '.' not in email:
                self.bot.reply_to(message, "Некорректный email. Пожалуйста, введите правильный email.")
                self.bot.register_next_step_handler(message, self.process_email_input)
                return

            amount = self.user_states[user_id]['amount']

            # Создаем платеж
            payment_data = self.payment_service.create_payment_link(
                telegram_id=user_id,  # Изменено с user_id на telegram_id
                amount=amount,
                email=email
            )

            if payment_data and payment_data['success']:
                payment_message = (
                    "💰 *Пополнение баланса*\n\n"
                    f"Сумма: *{amount}* руб.\n"
                    f"Email для чека: {email}\n"
                    "Для оплаты перейдите по ссылке ниже 👇"
                )

                keyboard = InlineKeyboardMarkup()
                keyboard.add(
                    InlineKeyboardButton("💳 Оплатить", url=payment_data['payment_url'])
                )
                keyboard.add(
                    InlineKeyboardButton("🔙 Вернуться в меню", callback_data='back_to_menu')
                )

                self.bot.send_message(
                    message.chat.id,
                    payment_message,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            else:
                self.bot.reply_to(
                    message,
                    "❌ Ошибка при создании платежа. Попробуйте позже."
                )

            # Очищаем состояние пользователя
            del self.user_states[user_id]

        except Exception as e:
            logger.error(f"Error processing email input: {e}")
            self.bot.reply_to(
                message,
                "Произошла ошибка. Попробуйте еще раз."
            )

    def handle_select_device(self, call: CallbackQuery):
        """Handle device type selection."""
        try:
            device_type = call.data.split('_')[2]

            # Сохраняем выбранный тип устройства
            if not hasattr(self, 'user_states'):
                self.user_states = {}

            self.user_states[call.from_user.id] = {
                'device_type': device_type,
                'action': 'waiting_days'
            }

            # Запрашиваем количество дней
            msg = self.menu_handler.create_device_selection_message()

            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=msg,
                reply_markup=self.menu_handler.create_cancel_menu()
            )

            # Регистрируем обработчик для следующего сообщения
            self.bot.register_next_step_handler(call.message, self.process_days_selection)

        except Exception as e:
            logger.error(f"Error handling device selection: {e}")
            self.bot.answer_callback_query(
                call.id,
                "Произошла ошибка. Попробуйте еще раз."
            )

    def process_days_selection(self, message: Message):
        """Process days selection."""
        try:
            user_id = message.from_user.id
            if user_id not in self.user_states:
                return

            try:
                days = int(message.text)

                # Специальная проверка для тестового тарифа
                if days == 999:  # Специальный код для тестового тарифа
                    minutes = 2
                    cost = DEFAULT_PLAN_PRICE
                    current_time = datetime.now()
                    expires_at = current_time + timedelta(minutes=minutes)

                    test_message = (
                        "⚠️ Внимание! Вы выбрали тестовый тариф:\n"
                        f"Длительность: {minutes} минуты\n"
                        f"Стоимость: {cost} руб."
                    )
                    self.bot.reply_to(message, test_message)

                elif not (1 <= days <= 30):
                    self.bot.reply_to(
                        message,
                        "❌ Пожалуйста, введите число от 1 до 30."
                    )
                    return
                else:
                    cost = days * DEFAULT_PLAN_PRICE
                    current_time = datetime.now()
                    expires_at = current_time + timedelta(hours=24 * days)

                user = self.db_manager.get_user(user_id)
                if user.balance < cost:
                    self.bot.reply_to(
                        message,
                        f"❌ Недостаточно средств. Требуется: {cost} руб."
                    )
                    return

                device = Device(
                    telegram_id=user_id,  # Изменено с user_id на telegram_id
                    device_type=self.user_states[user_id]['device_type'],
                    config_data=self.device_service._generate_config(
                        self.user_states[user_id]['device_type']
                    ),
                    expires_at=expires_at
                )

                device_id = self.db_manager.add_device(device)
                if device_id:
                    self.db_manager.update_balance(user_id, -cost)

                    if days == 999:
                        success_message = (
                            f"✅ Тестовый конфиг {device.device_type} создан!\n"
                            f"Срок действия: 2 минуты\n"
                            f"Стоимость: {cost} руб."
                        )
                    else:
                        success_message = (
                            f"✅ Устройство {device.device_type} успешно добавлено!\n"
                            f"Срок действия: {days} дней\n"
                            f"Стоимость: {cost} руб."
                        )
                    self.bot.reply_to(message, success_message)

                    config_file = self.device_service.save_config_file(
                        device.config_data,
                        device.device_type
                    )

                    if config_file:
                        with open(config_file, 'rb') as config:
                            self.bot.send_document(
                                message.chat.id,
                                config,
                                caption=f"📋 Конфигурация для устройства {device.device_type}"
                            )
                        self.device_service.cleanup_config_file(config_file)

                    self.bot.send_message(
                        message.chat.id,
                        "Выберите дальнейшее действие:",
                        reply_markup=self.menu_handler.create_back_to_menu()
                    )

            except ValueError:
                self.bot.reply_to(
                    message,
                    "❌ Пожалуйста, введите корректное число от 1 до 30 или 999 для тестового тарифа."
                )

        except Exception as e:
            logger.error(f"Error processing days selection: {e}")
            self.bot.reply_to(
                message,
                "Произошла ошибка. Попробуйте еще раз."
            )
        finally:
            if user_id in self.user_states:
                del self.user_states[user_id]

    def handle_referral(self, call: CallbackQuery):
        """Handle referral program button press."""
        try:
            user_id = call.from_user.id
            bot_username = "VangVPN_bot"
            ref_link = f"https://t.me/{bot_username}?start=ref{user_id}"

            stats = self.db_manager.get_referral_stats(user_id)

            text = (
                "🤝 *РЕФЕРАЛЬНАЯ ПРОГРАММА*\n"
                "Приводите друзей и зарабатывайте 15% с их пополнений.\n\n"
                "⬇️ *Ваша реферальная ссылка (нажми, чтобы скопировать):*\n"
                f"`{ref_link}`\n\n"
                "❗️ Нажмите на ссылку для автоматического копирования\n\n"
                "🏅 *Статистика:*\n"
                f"├ Приведено друзей: `{stats['referrals_count']}`\n"
                f"├ Бонусных рублей за все время: `{stats['total_earnings']:.2f}₽`\n"
                f"└ Уже начислено на баланс: `{stats['total_earnings']:.2f}₽`\n\n"  # Изменили эту строку
                "*Условия:*\n"
                "1. Вы направляете свою реферальную ссылку другу, который ни разу не заходил в наш бот\n"
                "2. Друг производит оплату подписки.\n"
                "3. Вы получаете 15% за пополнения приведенных друзей!"
            )

            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode='Markdown',
                reply_markup=self.menu_handler.create_back_to_menu()
            )

        except Exception as e:
            logger.error(f"Error handling referral menu: {e}")
            self.bot.answer_callback_query(
                call.id,
                "Произошла ошибка. Попробуйте еще раз."
            )

    def handle_support_message(self, message: Message):
        """Handle user message in support mode."""
        try:
            logger.info(f"Processing support message from user {message.from_user.id}")
            self.support_service.forward_to_support(message)
        except Exception as e:
            logger.error(f"Error handling support message: {e}")
            self.bot.reply_to(message, "Произошла ошибка. Попробуйте позже.")

    def handle_start_support(self, call: CallbackQuery):
        """Start support dialog."""
        try:
            user_id = call.from_user.id
            logger.info(f"Starting support dialog for user {user_id}")

            # Включаем режим ожидания сообщения
            self.support_service.start_support_dialog(user_id)

            # Отвечаем пользователю
            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=SUPPORT_WELCOME_MESSAGE,
                reply_markup=self.menu_handler.create_back_to_menu()
            )
            self.bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error starting support dialog: {e}")
            self.bot.answer_callback_query(
                call.id,
                "Произошла ошибка. Попробуйте еще раз."
            )

    def handle_agreement_acceptance(self, call: CallbackQuery):
        """Handle agreement acceptance."""
        try:
            # Обновляем статус в БД
            user = self.db_manager.get_user(call.from_user.id)
            if user:
                # Обновляем статус соглашения
                self.db_manager.update_agreement_status(call.from_user.id, True)

                # Показываем основное меню
                user_info = self.user_service.get_user_info(call.from_user.id)
                text = MESSAGE_TEMPLATES['welcome'].format(**user_info)

                self.bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=text,
                    parse_mode='Markdown',
                    reply_markup=self.menu_handler.create_main_menu()
                )

                self.bot.answer_callback_query(
                    call.id,
                    "✅ Спасибо за принятие соглашения!"
                )
        except Exception as e:
            logger.error(f"Error handling agreement acceptance: {e}")
            self.bot.answer_callback_query(
                call.id,
                "Произошла ошибка. Попробуйте еще раз."
            )