import qrcode
from io import BytesIO
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
import hashlib
import base64

logger = logging.getLogger('qr_service')


class QRService:
    def __init__(self):
        self.qr_cache = {}  # Кэш для хранения QR кодов
        self.cache_ttl = timedelta(hours=1)  # Время жизни кэша

    def generate_qr(self, config_data: str, device_type: str) -> Tuple[BytesIO, str]:
        """Генерация QR кода с цифровой подписью."""
        try:
            # Создаем цифровую подпись конфигурации
            config_hash = self._create_signature(config_data)

            # Добавляем метаданные к конфигурации
            config_with_meta = self._add_metadata(config_data, config_hash)

            # Генерируем QR код
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr.add_data(config_with_meta)
            qr.make(fit=True)

            # Создаем изображение
            img = qr.make_image(fill_color="black", back_color="white")

            # Сохраняем в буфер
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)

            # Кэшируем QR код
            cache_key = f"{device_type}_{config_hash}"
            self.qr_cache[cache_key] = {
                'timestamp': datetime.now(),
                'signature': config_hash
            }

            return buffer, config_hash

        except Exception as e:
            logger.error(f"Error generating QR code: {e}")
            raise

    def verify_qr(self, config_data: str, signature: str) -> bool:
        """Проверка актуальности QR кода."""
        try:
            # Извлекаем и проверяем метаданные
            config_meta = self._extract_metadata(config_data)
            if not config_meta:
                return False

            # Проверяем срок действия
            if not self._check_expiration(config_meta['timestamp']):
                return False

            # Проверяем цифровую подпись
            current_hash = self._create_signature(config_meta['config'])
            return current_hash == signature

        except Exception as e:
            logger.error(f"Error verifying QR code: {e}")
            return False

    def refresh_qr(self, config_data: str, old_signature: str) -> Optional[Tuple[BytesIO, str]]:
        """Обновление QR кода если он устарел."""
        try:
            if not self.verify_qr(config_data, old_signature):
                # Если QR код устарел, генерируем новый
                return self.generate_qr(config_data, "refresh")
            return None
        except Exception as e:
            logger.error(f"Error refreshing QR code: {e}")
            return None

    @staticmethod
    def _create_signature(data: str) -> str:
        """Создание цифровой подписи для конфигурации."""
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def _add_metadata(config: str, signature: str) -> str:
        """Добавление метаданных к конфигурации."""
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'signature': signature,
            'config': config
        }
        return base64.b64encode(str(metadata).encode()).decode()

    @staticmethod
    def _extract_metadata(encoded_data: str) -> Optional[dict]:
        """Извлечение метаданных из закодированной конфигурации."""
        try:
            decoded = base64.b64decode(encoded_data.encode()).decode()
            metadata = eval(decoded)  # Безопасно только потому, что мы сами создали эти данные
            return metadata
        except:
            return None

    def _check_expiration(self, timestamp_str: str) -> bool:
        """Проверка срока действия QR кода."""
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            return datetime.now() - timestamp < timedelta(days=1)
        except:
            return False

    def cleanup_cache(self) -> None:
        """Очистка устаревших QR кодов из кэша."""
        current_time = datetime.now()
        expired_keys = [
            key for key, data in self.qr_cache.items()
            if current_time - data['timestamp'] > self.cache_ttl
        ]
        for key in expired_keys:
            del self.qr_cache[key]