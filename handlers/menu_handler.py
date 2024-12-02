from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import (
    DEVICE_TYPES,
    TOP_UP_OPTIONS,
)
from typing import List
from database.models import Device

class MenuHandler:
    @staticmethod
    def create_agreement_menu() -> InlineKeyboardMarkup:
        """Create agreement acceptance keyboard."""
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton("📜 Принять соглашение", callback_data='accept_agreement'))
        return keyboard

    @staticmethod
    def create_main_menu() -> InlineKeyboardMarkup:
        """Create main menu keyboard."""
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton("🔄 Обновить", callback_data='update'))
        keyboard.row(InlineKeyboardButton("📱 Мои устройства", callback_data='my_devices'))
        keyboard.row(InlineKeyboardButton("💰 Пополнить баланс", callback_data='top_up'))
        keyboard.row(InlineKeyboardButton("👥 Реферальная программа", callback_data='referral'))
        keyboard.row(InlineKeyboardButton("ℹ️ Помощь", callback_data='help'))
        return keyboard

    @staticmethod
    def create_devices_menu() -> InlineKeyboardMarkup:
        """Create devices menu keyboard."""
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton("➕ Добавить устройство", callback_data='add_device'))
        keyboard.row(InlineKeyboardButton("🔙 Вернуться в меню", callback_data='back_to_menu'))
        return keyboard

    def create_device_info_menu(self, device_id: int) -> InlineKeyboardMarkup:
        """Create device info menu keyboard."""
        keyboard = InlineKeyboardMarkup()
        keyboard.row(
            InlineKeyboardButton(
                "🔄 Обновить конфиг",
                callback_data=f"refresh_config_{device_id}"
            ),
            InlineKeyboardButton(
                "⏳ Продлить",
                callback_data=f"extend_device_{device_id}"
            )
        )
        keyboard.row(
            InlineKeyboardButton(
                "💾 Скачать конфиг",
                callback_data=f"download_config_{device_id}"
            )
        )
        keyboard.row(
            InlineKeyboardButton(
                "❌ Удалить",
                callback_data=f"delete_device_{device_id}"
            ),
            InlineKeyboardButton(
                "🔙 Назад",
                callback_data="my_devices"
            )
        )
        return keyboard

    def create_devices_list_menu(self, devices: List[Device]) -> InlineKeyboardMarkup:
        """Create menu with list of devices."""
        keyboard = InlineKeyboardMarkup()
        for device in devices:
            keyboard.row(
                InlineKeyboardButton(
                    f"📱 {device.device_type}",
                    callback_data=f"device_info_{device.id}"
                )
            )
        keyboard.row(InlineKeyboardButton("➕ Добавить устройство", callback_data='add_device'))
        keyboard.row(InlineKeyboardButton("🔙 Вернуться в меню", callback_data='back_to_menu'))
        return keyboard

    def create_my_devices_button(self) -> InlineKeyboardMarkup:
        """Create button to return to devices menu."""
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton("📱 К моим устройствам", callback_data='my_devices'))
        return keyboard

    def create_cancel_menu_devices(self) -> InlineKeyboardMarkup:
        """Create cancel keyboard for devices."""
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton("❌ Отмена", callback_data='my_devices'))
        return keyboard

    @staticmethod
    def create_device_types_menu() -> InlineKeyboardMarkup:
        """Create device types selection keyboard."""
        keyboard = InlineKeyboardMarkup()
        for device_type in DEVICE_TYPES:
            keyboard.row(InlineKeyboardButton(
                f"📱 {device_type}",
                callback_data=f'select_device_{device_type}'
            ))
        keyboard.row(InlineKeyboardButton("🔙 Назад", callback_data='my_devices'))
        return keyboard

    @staticmethod
    def create_top_up_menu() -> InlineKeyboardMarkup:
        """Create top-up menu keyboard."""
        keyboard = InlineKeyboardMarkup()
        for amount in TOP_UP_OPTIONS:
            keyboard.row(InlineKeyboardButton(
                f"💰 {amount} руб",
                callback_data=f'top_up_{amount}'
            ))
        keyboard.row(InlineKeyboardButton(
            "💰 Другая сумма",
            callback_data='custom_amount'
        ))
        keyboard.row(InlineKeyboardButton(
            "📊 История пополнений",
            callback_data='payment_history'
        ))
        keyboard.row(InlineKeyboardButton("🔙 Вернуться в меню", callback_data='back_to_menu'))
        return keyboard

    @staticmethod
    def create_cancel_menu() -> InlineKeyboardMarkup:
        """Create cancel keyboard."""
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton("❌ Отмена", callback_data='cancel_input'))  # Изменим callback_data здесь
        return keyboard

    @staticmethod
    def create_help_menu() -> InlineKeyboardMarkup:
        """Create help menu keyboard."""
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton("📝 Написать в поддержку", callback_data='start_support'))
        keyboard.row(InlineKeyboardButton("🔙 Вернуться в меню", callback_data='back_to_menu'))
        return keyboard

    @staticmethod
    def create_back_to_menu() -> InlineKeyboardMarkup:
        """Create back to menu keyboard."""
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton("🔙 Вернуться в меню", callback_data='back_to_menu'))
        return keyboard

    @staticmethod
    def create_device_selection_message() -> str:
        return "Укажите количество дней для приобретения конфига (от 1 до 30):"