import sqlite3
import secrets
from typing import Optional, Tuple
from .logger import AppLogger

class AuthManager:
    def __init__(self, db_path: str = "auth_data.db"):
        self.db_path = db_path
        self.logger = AppLogger()
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных для хранения аутентификационных данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS auth (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_key TEXT NOT NULL,
                    pin_code TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Ошибка инициализации БД аутентификации: {e}")
    
    def save_credentials(self, api_key: str, pin_code: str) -> bool:
        """Сохранение учетных данных в БД"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Очищаем старые записи
            cursor.execute("DELETE FROM auth")
            
            # Сохраняем новые
            cursor.execute(
                "INSERT INTO auth (api_key, pin_code) VALUES (?, ?)",
                (api_key, pin_code)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сохранения учетных данных: {e}")
            return False
    
    def get_credentials(self) -> Optional[Tuple[str, str]]:
        """Получение сохраненных учетных данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT api_key, pin_code FROM auth ORDER BY id DESC LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            return result if result else None
        except Exception as e:
            self.logger.error(f"Ошибка получения учетных данных: {e}")
            return None
    
    def clear_credentials(self) -> bool:
        """Очистка всех учетных данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM auth")
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Ошибка очистки учетных данных: {e}")
            return False
    
    def generate_pin(self) -> str:
        """Генерация 4-значного PIN-кода"""
        return str(secrets.randbelow(10000)).zfill(4)
    
    def validate_pin(self, input_pin: str) -> bool:
        """Проверка PIN-кода"""
        stored_credentials = self.get_credentials()
        if not stored_credentials:
            return False
        
        stored_pin = stored_credentials[1]
        return input_pin == stored_pin
