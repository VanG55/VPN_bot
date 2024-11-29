import os
import json
import sqlite3
import shutil
from datetime import datetime
import logging
from typing import Optional, Dict, Any
import zipfile

logger = logging.getLogger('backup')


class BackupService:
    def __init__(self, db_path: str, backup_dir: str = "backups"):
        self.db_path = db_path
        self.backup_dir = backup_dir
        self._ensure_backup_dir()

    def _ensure_backup_dir(self) -> None:
        """Создание директории для бэкапов если она не существует."""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
            logger.info(f"Created backup directory: {self.backup_dir}")

    def create_backup(self) -> Optional[str]:
        """Создание полного бэкапа базы данных и конфигураций."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_{timestamp}.zip"
            backup_path = os.path.join(self.backup_dir, backup_filename)

            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                # Бэкап базы данных
                db_backup = f"vpn_bot_{timestamp}.db"
                with sqlite3.connect(self.db_path) as conn:
                    backup = sqlite3.connect(db_backup)
                    conn.backup(backup)
                    backup.close()
                backup_zip.write(db_backup)
                os.remove(db_backup)

                # Бэкап конфигураций
                configs = self._get_all_configs()
                config_data = json.dumps(configs, indent=2)
                config_file = f"configs_{timestamp}.json"
                with open(config_file, 'w') as f:
                    f.write(config_data)
                backup_zip.write(config_file)
                os.remove(config_file)

            logger.info(f"Created backup: {backup_filename}")
            return backup_path

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return None

    def restore_from_backup(self, backup_path: str) -> bool:
        """Восстановление из бэкапа."""
        try:
            if not os.path.exists(backup_path):
                logger.error(f"Backup file not found: {backup_path}")
                return False

            # Создаем временную директорию для распаковки
            temp_dir = "temp_restore"
            os.makedirs(temp_dir, exist_ok=True)

            with zipfile.ZipFile(backup_path, 'r') as backup_zip:
                backup_zip.extractall(temp_dir)

            # Находим файлы бэкапа
            db_backup = None
            config_backup = None
            for file in os.listdir(temp_dir):
                if file.endswith('.db'):
                    db_backup = os.path.join(temp_dir, file)
                elif file.endswith('.json'):
                    config_backup = os.path.join(temp_dir, file)

            # Восстанавливаем базу данных
            if db_backup:
                shutil.copy2(db_backup, self.db_path)
                logger.info("Database restored successfully")

            # Восстанавливаем конфигурации
            if config_backup:
                with open(config_backup, 'r') as f:
                    configs = json.load(f)
                self._restore_configs(configs)
                logger.info("Configurations restored successfully")

            # Очищаем временные файлы
            shutil.rmtree(temp_dir)
            logger.info("Restore completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error restoring from backup: {e}")
            if os.path.exists('temp_restore'):
                shutil.rmtree('temp_restore')
            return False

    def _get_all_configs(self) -> Dict[str, Any]:
        """Получение всех конфигураций."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT telegram_id, device_type, config_data, 
                           marzban_username, is_active 
                    FROM devices 
                    WHERE is_active = 1
                """)
                configs = {}
                for row in cursor.fetchall():
                    telegram_id = row[0]
                    if telegram_id not in configs:
                        configs[telegram_id] = []
                    configs[telegram_id].append({
                        'device_type': row[1],
                        'config_data': row[2],
                        'marzban_username': row[3]
                    })
                return configs
        except Exception as e:
            self.logger.error(f"Error getting configurations: {e}")
            return {}

    def _restore_configs(self, configs: Dict[str, Any]) -> None:
        """Восстановление конфигураций в базу данных."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Деактивируем все текущие конфигурации
                cursor.execute("UPDATE devices SET is_active = 0")

                # Восстанавливаем конфигурации из бэкапа
                for user_id, user_configs in configs.items():
                    for config in user_configs:
                        cursor.execute("""
                            INSERT INTO devices 
                            (user_id, device_type, config_data, is_active)
                            VALUES (?, ?, ?, 1)
                        """, (user_id, config['device_type'], config['config_data']))
                conn.commit()
        except Exception as e:
            logger.error(f"Error restoring configurations: {e}")

    def cleanup_old_backups(self, days: int = 7) -> None:
        """Удаление старых бэкапов."""
        try:
            current_time = datetime.now()
            for backup_file in os.listdir(self.backup_dir):
                if not backup_file.endswith('.zip'):
                    continue

                backup_path = os.path.join(self.backup_dir, backup_file)
                file_time = datetime.fromtimestamp(os.path.getctime(backup_path))

                if (current_time - file_time).days > days:
                    os.remove(backup_path)
                    logger.info(f"Removed old backup: {backup_file}")

        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")

    def setup_auto_cleanup(self, max_backups: int = 5) -> None:
        """Setup automatic cleanup of old backups."""
        try:
            backups = []
            for file in os.listdir(self.backup_dir):
                if file.endswith('.zip'):
                    path = os.path.join(self.backup_dir, file)
                    backups.append((os.path.getctime(path), path))

            # Сортируем по времени создания (старые в начале)
            backups.sort()

            # Удаляем старые бэкапы, оставляя только max_backups последних
            if len(backups) > max_backups:
                for _, path in backups[:-max_backups]:
                    try:
                        os.remove(path)
                        logger.info(f"Deleted old backup: {path}")
                    except Exception as e:
                        logger.error(f"Failed to delete backup {path}: {e}")

        except Exception as e:
            logger.error(f"Error during auto cleanup: {e}")

    def schedule_backups(self) -> None:
        """Запуск регулярного создания бэкапов."""
        from threading import Thread
        import schedule
        import time

        def run_schedule():
            schedule.every().day.at("00:00").do(self.create_backup)
            schedule.every().week.do(lambda: self.cleanup_old_backups(7))

            while True:
                schedule.run_pending()
                time.sleep(60)

        Thread(target=run_schedule, daemon=True).start()