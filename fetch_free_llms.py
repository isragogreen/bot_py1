"""
Модуль для получения списка бесплатных LLM моделей через OpenRouter API.
"""

import requests
from env_loader import get_env
from error_handler import log_error

OPENROUTER_API_KEY = get_env("OPENROUTER_API_KEY")
FREE_LLMS_DEFAULT = get_env("FREE_LLMS_DEFAULT", "")

def fetch_free_llms(only_free: bool = True):
    """
    Получает список моделей LLM.
    Если only_free=True, фильтрует только бесплатные модели.
    Если нет ключа API, возвращает дефолтный список из .env.
    """
    models = []
    try:
        if not OPENROUTER_API_KEY:
            # Нет ключа — используем дефолтный список
            for idx, name in enumerate(FREE_LLMS_DEFAULT.split(',')):
                models.append((idx, name.strip()))
            return models

        url = "https://openrouter.ai/api/v1/models"
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for idx, model in enumerate(data.get("models", [])):
            if only_free and model.get("pricing", {}).get("unit_price", 1) > 0:
                continue
            models.append((idx, model["id"]))
        return models
    except Exception as e:
        log_error(e, "fetch_free_llms")
        # В случае ошибки — возвращаем дефолтный список
        for idx, name in enumerate(FREE_LLMS_DEFAULT.split(',')):
            models.append((idx, name.strip()))
        return models
