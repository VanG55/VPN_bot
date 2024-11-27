from telebot import TeleBot
from database.db_manager import DatabaseManager
from config.settings import SUPPORT_GROUP_ID
import re


class SupportService:
    def __init__(self, bot: TeleBot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager
        self.states = {}  # Simple state storage

        # Проверяем доступность группы при инициализации
        try:
            self.bot.get_chat(SUPPORT_GROUP_ID)
            print(f"✅ Successfully connected to support group {SUPPORT_GROUP_ID}")
        except Exception as e:
            print(f"❌ Error connecting to support group: {e}")
            print("Please make sure:")
            print("1. The bot is added to the group as an administrator")
            print("2. The group ID is correct")
            print("3. The bot has permission to send and read messages")

    def start_support_dialog(self, user_id: int) -> None:
        """Set user state to waiting for support message."""
        print(f"Starting support dialog for user {user_id}")
        self.states[user_id] = 'waiting_for_message'
        print(f"Current states: {self.states}")

    def cancel_support_dialog(self, user_id: int) -> None:
        """Remove user from support state."""
        print(f"Cancelling support dialog for user {user_id}")
        if user_id in self.states:
            del self.states[user_id]
        print(f"Current states after cancel: {self.states}")

    def is_waiting_for_message(self, user_id: int) -> bool:
        """Check if user is in support dialog state."""
        is_waiting = self.states.get(user_id) == 'waiting_for_message'
        print(f"Checking support state for user {user_id}: {is_waiting}")
        print(f"Current states: {self.states}")
        return is_waiting

    def forward_to_support(self, message) -> None:
        """Forward user message to support group."""
        try:
            user = self.db_manager.get_user(message.from_user.id)
            if not user:
                print(f"❌ User not found: {message.from_user.id}")
                return

            print(f"📤 Forwarding message to support: {message.text}")
            print(f"From user: {user.display_name} (ID: {user.telegram_id})")

            # Безопасное форматирование текста сообщения
            support_message = (
                "📩 Новое обращение в поддержку\n\n"
                f"👤 От: {user.display_name}\n"
                f"🆔 ID: {user.telegram_id}\n"
                f"📝 Сообщение:\n{message.text}\n\n"
                f"#support #user_{user.telegram_id}"
            )

            print(f"Sending to group {SUPPORT_GROUP_ID}: {support_message}")

            # Отправляем сообщение в группу поддержки
            sent_message = self.bot.send_message(
                SUPPORT_GROUP_ID,
                support_message
            )

            if sent_message:
                print("✅ Message successfully sent to support group")
                # Подтверждаем пользователю
                self.bot.reply_to(
                    message,
                    "✅ Ваше сообщение отправлено в поддержку. Мы ответим вам как можно скорее."
                )
            else:
                raise Exception("Failed to send message to support group")

        except Exception as e:
            print(f"❌ Error forwarding message to support: {e}")
            self.bot.reply_to(
                message,
                "❌ Произошла ошибка при отправке сообщения. Пожалуйста, попробуйте позже."
            )
        finally:
            self.cancel_support_dialog(message.from_user.id)

    def handle_support_reply(self, message) -> None:
        """Handle reply from support to user."""
        try:
            print(f"Processing support reply: {message.text}")

            # Проверяем, что сообщение является ответом
            if not message.reply_to_message or not message.reply_to_message.text:
                print("❌ Not a reply message or no original message text")
                return

            # Извлекаем ID пользователя из тегов
            user_id = self.extract_user_id_from_tags(message.reply_to_message.text)
            if not user_id:
                print(f"❌ Could not extract user ID from message: {message.reply_to_message.text}")
                self.bot.reply_to(message, "❌ Не удалось найти ID пользователя в исходном сообщении")
                return

            print(f"💬 Sending reply to user {user_id}")

            # Отправляем ответ пользователю
            self.bot.send_message(
                user_id,
                f"Ответ от поддержки:\n\n{message.text}"
            )

            # Подтверждаем отправку
            self.bot.reply_to(
                message,
                f"✅ Ответ успешно отправлен пользователю {user_id}"
            )

        except Exception as e:
            print(f"❌ Error sending reply to user: {e}")
            self.bot.reply_to(
                message,
                "❌ Ошибка при отправке ответа пользователю"
            )

    @staticmethod
    def extract_user_id_from_tags(text: str) -> int:
        """Extract user ID from message tags."""
        try:
            match = re.search(r'#user_(\d+)', text)
            if match:
                return int(match.group(1))
            return None
        except Exception as e:
            print(f"Error extracting user ID: {e}")
            return None