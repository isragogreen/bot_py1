"""
Модуль для перевода текста.
Использует внешний API, если доступен, иначе fallback на локальный перевод (заглушка).
"""

from env_loader import get_env
from error_handler import log_error
import requests

TRANSLATE_API_KEY = get_env("TRANSLATE_API_KEY")
TRANSLATE_TIMEOUT = int(get_env("TRANSLATE_TIMEOUT", 10))

class Translator:
    """
    Класс для перевода текста на английский.
    """

    def __init__(self):
        self.api_key = TRANSLATE_API_KEY

    def translate_to_english(self, text: str) -> str:
        """
        Переводит текст на английский язык.
        """
        if not text.strip():
            return ""
        if not self.api_key:
            # Fallback: возвращаем исходный текст (или используем локальный переводчик)
            return text
        try:
            # Пример для Google Translate API (замените на ваш API)
            url = "https://translation.googleapis.com/language/translate/v2"
            params = {
                "q": text,
                "target": "en",
                "key": self.api_key
            }
            resp = requests.post(url, data=params, timeout=TRANSLATE_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            return data["data"]["translations"][0]["translatedText"]
        except Exception as e:
            log_error(e, "Translator.translate_to_english")
            return text

translator = Translator()
