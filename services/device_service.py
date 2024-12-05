import os
import json
import qrcode
from qrcode.constants import ERROR_CORRECT_L
import io
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from database.models import Device
from database.db_manager import DatabaseManager
from config.settings import (
    DEFAULT_PLAN_PRICE,
    MARZBAN_PROTOCOLS
)
from services.marzban_service import MarzbanService
from telebot import TeleBot
import logging
logger = logging.getLogger('device_service')

class DeviceService:
    def __init__(self, db_manager: DatabaseManager, marzban_service: MarzbanService, bot: TeleBot):
        self.db_manager = db_manager
        self.marzban = marzban_service
        self.bot = bot  # Добавьте эту строку
        self.logger = logging.getLogger('device_service')

    def format_device_info(self, device: Device) -> Tuple[str, Optional[io.BytesIO]]:
        try:
            marzban_config = self.marzban.get_user_config(device.marzban_username)
            if not marzban_config:
                return "Ошибка получения информации об устройстве", None

            links = marzban_config.get('links', [])
            vless_link = next((link for link in links if link.startswith('vless://')), '')

            info_text = f"""
    ℹ️ *Информация:*
    👤 Пользователь: `{device.telegram_id}`
    📱 Устройство: {device.device_type}
    📅 Дата создания: {device.created_at}
    ⌛ Дата истечения: {device.expires_at}
    🌍 Страна: 🇩🇪 Германия
    🔒 Протокол: Vless

    1️⃣ *Скопируйте конфигурацию*
    Нажмите на ссылку ниже, чтобы скопировать ⬇️
    `{device.marzban_username}`

    2️⃣ *Скопируйте ссылку для подключения:*
    `{vless_link}`
    """

            qr = qrcode.QRCode(
                version=1,
                error_correction=ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(vless_link)
            qr.make(fit=True)

            qr_buffer = io.BytesIO()
            qr.make_image(fill_color="black", back_color="white").save(qr_buffer, "PNG")
            qr_buffer.seek(0)

            return info_text, qr_buffer

        except Exception as e:
            self.logger.error(f"Error formatting device info: {e}")
            return "Ошибка форматирования информации об устройстве", None

    def add_device(self, telegram_id: int, device_type: str, days: int = 30) -> Optional[Device]:
        try:
            if not self.can_add_device(telegram_id):
                return None

            # Проверяем достаточно ли денег на балансе для создания конфига
            total_cost = DEFAULT_PLAN_PRICE * days  # Считаем полную стоимость за все дни
            user = self.db_manager.get_user(telegram_id)

            if not user or user.balance < total_cost:
                self.logger.info(f"Insufficient balance: required {total_cost}, available {user.balance if user else 0}")
                return None

            marzban_username = f"vless_{device_type.lower()}_{int(datetime.now().timestamp())}"
            self.logger.info(f"Creating Marzban user: {marzban_username}")

            marzban_user = self.marzban.create_user(marzban_username, days)
            if not marzban_user:
                return None

            device = Device(
                telegram_id=telegram_id,
                device_type=device_type,
                config_data=json.dumps(marzban_user),  # сохраняем полный ответ от Marzban
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=days),
                marzban_username=marzban_username  # важно сохранить это
            )

            device_id = self.db_manager.add_device(device)
            if device_id:
                # Списываем полную стоимость за все дни
                self.db_manager.update_balance(telegram_id, -total_cost)
                device.id = device_id
                return device

            return None

        except Exception as e:
            self.logger.error(f"Error adding device: {e}")
            return None

    def get_device_status(self, device: Device) -> Dict[str, Any]:
        """Get device status and usage info."""
        try:
            # Если expires_at является строкой, используем её напрямую
            if isinstance(device.expires_at, str):
                expires = device.expires_at
            else:
                expires = device.expires_at.strftime("%d.%m.%Y %H:%M:%S") if device.expires_at else 'Бессрочно'

            # То же самое для created_at
            if isinstance(device.created_at, str):
                created = device.created_at
            else:
                created = device.created_at.strftime("%d.%m.%Y %H:%M:%S") if device.created_at else 'Неизвестно'

            return {
                'status': 'active' if device.is_active else 'inactive',
                'created': created,
                'expires': expires
            }

        except Exception as e:
            self.logger.error(f"Error getting device status: {e}")
            return {
                'status': 'error',
                'created': 'Неизвестно',
                'expires': 'Неизвестно'
            }

        except Exception as e:
            self.logger.error(f"Error getting device status: {e}")
            return {
                'status': 'error',
                'created': 'Неизвестно',
                'expires': 'Неизвестно'
            }

    def get_user_devices(self, telegram_id: int) -> List[Device]:
        """Get all active devices for user."""
        return self.db_manager.get_user_devices(telegram_id)

    def save_config_file(self, config_data: str, device_type: str) -> str:
        """Save config to temporary file."""
        try:
            configs = json.loads(config_data)
            formatted_text = self.format_config_for_device(configs, device_type)

            filename = f"{device_type}_config_{datetime.now().timestamp()}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(formatted_text)
            return filename
        except Exception as e:
            self.logger.error(f"Error saving config file: {e}")
            return ""

    def can_add_device(self, telegram_id: int) -> bool:
        """Check if user can add new device."""
        try:
            user = self.db_manager.get_user(telegram_id)
            return user and user.balance >= DEFAULT_PLAN_PRICE
        except Exception as e:
            self.logger.error(f"Error checking if user can add device: {e}")
            return False

    def get_user_status(self, username: str) -> bool:
        try:
            user_config = self.marzban.get_user_config(username)
            return user_config and user_config.get('status') == 'active'
        except Exception as e:
            logger.error(f"Error checking user status: {e}")
            return False

    def check_deactivated_configs(self):
        try:
            # Получаем все активные устройства для всех пользователей
            active_devices = self.db_manager.get_all_active_devices()  # Этот метод нужно будет добавить
            for device in active_devices:
                if not self.get_user_status(device.marzban_username):
                    self.permanently_delete_config(device.marzban_username)
                    logger.info(f"Config {device.marzban_username} was deactivated by v2iplimit and removed")
        except Exception as e:
            logger.error(f"Error checking deactivated configs: {e}")



    def format_config_for_device(self, configs: dict, device_type: str) -> str:
        """Format Marzban config for specific device type."""
        try:
            formatted_text = f"=== Конфигурация для {device_type} ===\n\n"
            available_protocols = MARZBAN_PROTOCOLS.get(device_type, {})

            for protocol, config in configs['proxies'].items():
                if available_protocols.get(protocol, False) and 'uri' in config:
                    formatted_text += f"--- {protocol.upper()} ---\n"
                    formatted_text += f"Ссылка для подключения:\n{config['uri']}\n\n"

            if formatted_text == f"=== Конфигурация для {device_type} ===\n\n":
                return "Нет доступных конфигураций для данного типа устройства"

            return formatted_text

        except Exception as e:
            self.logger.error(f"Error formatting config: {e}")
            return "Ошибка форматирования конфигурации"

    def cleanup_config_file(self, filename: str) -> None:
        """Remove temporary config file."""
        try:
            if filename and os.path.exists(filename):
                os.remove(filename)
        except Exception as e:
            self.logger.error(f"Error removing config file: {e}")

    def permanently_delete_config(self, username: str):
        try:
            device = self.db_manager.get_device_by_marzban_username(username)
            if not device:
                logger.warning(f"Device not found: {username}")
                return

            # Удаляем из Marzban
            if self.marzban.delete_user(username):
                # Деактивируем в БД
                self.db_manager.deactivate_device(device.id)

                # Уведомляем пользователя
                message = (
                    "🚫 *Доступ заблокирован*\n\n"
                    "Ваш VPN профиль был заблокирован из-за попытки использования "
                    "с нескольких устройств одновременно.\n\n"
                    "Для продолжения работы создайте новый профиль."
                )

                self.bot.send_message(
                    device.telegram_id,
                    message,
                    parse_mode='Markdown'
                )

        except Exception as e:
            logger.error(f"Error permanently deleting config: {e}")