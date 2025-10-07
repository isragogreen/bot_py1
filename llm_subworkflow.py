"""
Модуль для работы с LLM и скорингом моделей.
Синхронная логика выбора оптимальной модели для пользователя.
"""

from db import Database
from error_handler import log_error
from env_loader import get_env
import concurrent.futures
import requests

QUALITY_THRESHOLD = float(get_env("QUALITY_THRESHOLD", 7.0))
SCORE_TOP_N = int(get_env("SCORE_TOP_N", 10))
OPENROUTER_API_KEY = get_env("OPENROUTER_API_KEY")
DEFAULT_SCORER_MODEL = get_env("FREE_LLMS_DEFAULT", "mistralai/mistral-7b-instruct:free").split(",")[0].strip()
MAX_TOKENS = int(get_env("MAX_TOKENS", 128))
TIMEOUT = int(get_env("LLM_TIMEOUT", 30))

class LLMSubworkflow:
    """
    Класс для работы с LLM и скорингом моделей.
    """

    def __init__(self, db: Database):
        self.db = db

    def score_models(self, nick: str, message: str):
        """
        Выполняет скоринг моделей для пользователя параллельно.
        """
        try:
            top_models = self.db.get_top_models(SCORE_TOP_N)
            results = {}

            # Параллельные запросы к моделям
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(top_models))) as executor:
                future_to_model = {
                    executor.submit(self._get_model_answer, model, message): model
                    for model in top_models
                }
                for future in concurrent.futures.as_completed(future_to_model):
                    model = future_to_model[future]
                    try:
                        answer = future.result()
                        results[model] = answer
                    except Exception as e:
                        log_error(e, f"LLMSubworkflow.score_models:{model}")
                        results[model] = ""

            # Параллельный скоринг ответов через модель-оценщик
            scores = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(results))) as executor:
                future_to_model = {
                    executor.submit(self._score_answer, message, results[model]): model
                    for model in results
                }
                for future in concurrent.futures.as_completed(future_to_model):
                    model = future_to_model[future]
                    try:
                        score = future.result()
                        scores[model] = score
                    except Exception as e:
                        log_error(e, f"LLMSubworkflow.score_models:score:{model}")
                        scores[model] = QUALITY_THRESHOLD

            # Запись скоринга в базу с нормализацией
            for model, score in scores.items():
                self.db.set_model_score(nick, model, score)

            # Сортировка и выбор лидера
            sorted_models = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            if sorted_models:
                leader_model = sorted_models[0][0]
                self.db.set_user_model(nick, leader_model)

        except Exception as e:
            log_error(e, "LLMSubworkflow.score_models")

    def _get_model_answer(self, model: str, message: str) -> str:
        """
        Получает ответ от указанной модели через OpenRouter API.
        """
        try:
            if not OPENROUTER_API_KEY:
                return ""
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": message}],
                "max_tokens": MAX_TOKENS
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            log_error(e, f"LLMSubworkflow._get_model_answer:{model}")
            return ""

    def _score_answer(self, user_message: str, model_answer: str) -> float:
        """
        Оценивает качество ответа через модель-оценщик (LLM).
        """
        try:
            if not OPENROUTER_API_KEY or not model_answer:
                return QUALITY_THRESHOLD
            prompt = (
                f"Поступило сообщение от пользователя: {user_message}\n"
                f"Я ответил: {model_answer}\n"
                "Дай оценку моего ответа в баллах от 1 до 10 (высший балл). "
                "Ответь только числом."
            )
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
            payload = {
                "model": DEFAULT_SCORER_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 10
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            score_str = data["choices"][0]["message"]["content"].strip()
            try:
                score = float(score_str)
            except Exception:
                score = QUALITY_THRESHOLD
            return score
        except Exception as e:
            log_error(e, "LLMSubworkflow._score_answer")
            return QUALITY_THRESHOLD

    def get_best_model(self, nick: str) -> str:
        """
        Получает лучшую модель для пользователя.
        """
        try:
            return self.db.get_best_model_for_user(nick)
        except Exception as e:
            log_error(e, "LLMSubworkflow.get_best_model")
            return ""

    def generate_response(self, nick: str, prompt: str) -> str:
        """
        Генерирует ответ для пользователя с помощью лучшей модели.
        """
        try:
            model = self.get_best_model(nick)
            if not OPENROUTER_API_KEY or not model:
                return "Нет доступной модели или ключа API"
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 256
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            answer = data["choices"][0]["message"]["content"]
            return answer
        except Exception as e:
            log_error(e, "LLMSubworkflow.generate_response")
            return "Ошибка генерации ответа"
