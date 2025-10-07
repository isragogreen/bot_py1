"""
Главный рабочий процесс системы
Обрабатывает очередь сообщений, управляет RAG, LLM и скорингом моделей
"""

import asyncio
import re
from datetime import datetime
from typing import Optional, Callable
from db import Database
from env_loader import env_loader
from llm_subworkflow import LLMSubworkflow
from rag_subworkflow import rag
from translate import translator
from doc_processing import DocProcessing
from proactive_workflow import ProactiveWorkflow
from fetch_free_llms import fetch_free_llms
from logger import logger, LogLevel
from error_handler import log_error

class BotController:
    """
    Управление состоянием бота: полная остановка, остановка обработки сообщений.
    """
    def __init__(self):
        self.running = True
        self.processing = True

    def stop_all(self):
        """Полная остановка всех процессов."""
        self.running = False
        self.processing = False

    def stop_processing(self):
        """Остановка обработки сообщений и proactive."""
        self.processing = False

    def start_processing(self):
        """Возобновление обработки сообщений."""
        self.processing = True

class MainWorkflow:
    """
    Основной workflow для обработки сообщений и управления системой
    Координирует работу всех подсистем: LLM, RAG, Doc Processing, Proactive
    """

    def __init__(self, db: Database, ui_callback: Optional[Callable] = None):
        self.db = db
        self.ui_callback = ui_callback
        self.llm = LLMSubworkflow(db)
        self.doc_processor = DocProcessing(db)
        self.proactive: Optional[ProactiveWorkflow] = None

        self.running = False
        self.queue_task: Optional[asyncio.Task] = None
        self.processed_count = 0  # Счетчик обработанных сообщений

        # Роли ботов и их температуры для генерации ответов
        self.roles = {
            'TECH': env_loader.get_float('TECH_temp', 0.1),       # Технический бот - точность
            'FRIEND': env_loader.get_float('FRIEND_temp', 0.9),   # Дружелюбный - креативность
            'ADVISOR': env_loader.get_float('ADVISOR_temp', 0.4), # Советник - сбалансированность
            'AGITATOR': env_loader.get_float('AGITATOR_temp', 0.5), # Агитатор - умеренная креативность
            'OPERATOR': env_loader.get_float('OPERATOR_temp', 0.3)  # Оператор - точность
        }

        # Автоматически добавляем все системные роли в черный список
        for role in self.roles.keys():
            self.db.add_to_blacklist(role.lower())

        logger.info("Main workflow initialized", "MAIN")

    def set_proactive(self, proactive: ProactiveWorkflow):
        """Установка проактивного workflow"""
        self.proactive = proactive

    async def initialize(self):
        """
        Инициализация системы при старте
        - Загрузка списка LLM моделей
        - Обработка документов из репозитория
        - Первичный скоринг моделей
        """
        logger.info("Initializing system...", "MAIN")

        # Загрузка списка доступных LLM моделей
        only_free = self.db.get_setting('only_free_llms', True)
        logger.debug(f"Fetching models (only_free={only_free})", "MAIN")

        models = await fetch_free_llms(only_free)
        self.db.set_free_llms(models)
        logger.info(f"Loaded {len(models)} LLM models", "MAIN")

        # Обработка документов из GitHub/GitLab репозитория
        logger.debug("Starting document processing", "MAIN")
        await self.doc_processor.clone_and_process()

        # Проверка необходимости первичного скоринга
        iteration = self.db.get_iteration_count()
        if iteration == 0:
            logger.info("Performing initial full scoring of all models...", "MAIN")
            model_list = [m[0] for m in models]
            if model_list:
                # Скорим первые 20 моделей для ускорения старта
                await self.llm.full_scoring(
                    model_list[:20],
                    "Hello, how are you?",
                    0.7,
                    'system'
                )
            logger.info("Initial scoring completed", "MAIN")

        logger.info("System initialized successfully", "MAIN")

    async def start(self):
        """Запуск главного workflow"""
        if self.running:
            logger.warning("Main workflow already running", "MAIN")
            return

        await self.initialize()

        self.running = True
        # Запуск асинхронной обработки очереди
        self.queue_task = asyncio.create_task(self.process_queue())

        # Запуск проактивных агентов
        if self.proactive:
            self.proactive.start()

        logger.info("Main workflow started", "MAIN")

        # Уведомление UI о запуске
        if self.ui_callback:
            self.ui_callback('status', 'running')

    async def stop(self):
        """Остановка главного workflow"""
        if not self.running:
            logger.warning("Main workflow not running", "MAIN")
            return

        logger.info("Stopping main workflow...", "MAIN")
        self.running = False

        # Остановка задачи обработки очереди
        if self.queue_task:
            self.queue_task.cancel()
            try:
                await self.queue_task
            except asyncio.CancelledError:
                logger.debug("Queue processing task cancelled", "MAIN")

        # Остановка проактивных агентов
        if self.proactive:
            await self.proactive.stop()

        logger.info("Main workflow stopped", "MAIN")

        # Уведомление UI об остановке
        if self.ui_callback:
            self.ui_callback('status', 'stopped')

    async def process_queue(self):
        """
        Асинхронная обработка очереди сообщений
        Работает в бесконечном цикле пока running=True
        """
        logger.debug("Queue processing loop started", "MAIN")

        while self.running:
            try:
                # Получение следующего сообщения из очереди
                item = self.db.get_queue_item()

                if item:
                    item_id, nick, text, ts = item
                    logger.debug(f"Processing message from queue: {nick}", "QUEUE")

                    # Обработка сообщения
                    await self.process_message(nick, text)

                    # Удаление из очереди после успешной обработки
                    self.db.remove_from_queue(item_id)

                    # Обновление счетчика обработанных сообщений
                    self.processed_count += 1
                    if self.ui_callback:
                        self.ui_callback('processed_count', self.processed_count)
                else:
                    # Очередь пуста - ожидание
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Queue processing error: {e}", "QUEUE")
                await asyncio.sleep(1)

    def clean_message(self, text: str) -> str:
        """
        Очистка текста сообщения
        - Удаление эмодзи (если включено)
        - Приведение к нижнему регистру
        """
        remove_emoji = self.db.get_setting('remove_emoji', True)

        if remove_emoji:
            # Regex для удаления всех Unicode emoji
            emoji_pattern = re.compile(
                "["
                "\U0001F600-\U0001F64F"  # Эмоции
                "\U0001F300-\U0001F5FF"  # Символы и пиктограммы
                "\U0001F680-\U0001F6FF"  # Транспорт и карты
                "\U0001F1E0-\U0001F1FF"  # Флаги
                "\U00002702-\U000027B0"  # Дингбаты
                "\U000024C2-\U0001F251"  # Дополнительные символы
                "]+",
                flags=re.UNICODE
            )
            text = emoji_pattern.sub('', text)
            logger.debug("Emojis removed from message", "CLEANER")

        return text.lower().strip()

    def determine_role(self, text: str) -> str:
        """
        Определение роли бота на основе содержания сообщения
        Анализирует ключевые слова для выбора подходящей роли
        """
        text_lower = text.lower()

        # Технический бот - для вопросов по программированию и ошибкам
        if any(word in text_lower for word in ['help', 'error', 'bug', 'code', 'technical']):
            logger.debug("Role determined: TECH", "ROLE")
            return 'TECH'

        # Дружелюбный бот - для эмоциональных сообщений
        elif any(word in text_lower for word in ['feel', 'sad', 'happy', 'friend']):
            logger.debug("Role determined: FRIEND", "ROLE")
            return 'FRIEND'

        # Советник - для запроса рекомендаций
        elif any(word in text_lower for word in ['advice', 'suggest', 'recommend', 'should']):
            logger.debug("Role determined: ADVISOR", "ROLE")
            return 'ADVISOR'

        # Агитатор - для скучающих пользователей
        elif any(word in text_lower for word in ['boring', 'nothing', 'quiet']):
            logger.debug("Role determined: AGITATOR", "ROLE")
            return 'AGITATOR'

        # По умолчанию - оператор
        else:
            logger.debug("Role determined: OPERATOR (default)", "ROLE")
            return 'OPERATOR'

    async def process_message(self, nick: str, text: str):
        """
        Полная обработка одного сообщения
        1. Проверка blacklist
        2. Очистка и перевод
        3. Сохранение в историю и RAG
        4. Определение роли
        5. Генерация ответа через LLM
        6. Сохранение ответа
        7. Скоринг моделей
        """
        try:
            logger.debug(f"Processing message from {nick}: {text[:50]}...", "PROCESS")

            # Шаг 1: Проверка черного списка
            if self.db.is_blacklisted(nick):
                logger.info(f"Message from blacklisted user {nick} ignored", "BLACKLIST")
                return

            # Шаг 2: Очистка текста сообщения
            cleaned_text = self.clean_message(text)
            logger.debug(f"Cleaned text: {cleaned_text[:50]}...", "PROCESS")

            # Шаг 3: Перевод на английский для обработки
            translated_text = await translator.translate_to_english(cleaned_text)
            if translated_text != cleaned_text:
                logger.debug("Message translated to English", "TRANSLATE")

            # Шаг 4: Сохранение в историю
            self.db.add_history(nick, cleaned_text, 'user')
            logger.debug(f"Message saved to history for {nick}", "HISTORY")

            # Шаг 5: Сохранение в RAG (namespace = ник пользователя)
            await rag.upsert(cleaned_text, nick)
            if translated_text != cleaned_text:
                await rag.upsert(translated_text, nick, {'translated': True})
            logger.debug(f"Message upserted to RAG (namespace={nick})", "RAG")

            # Уведомление UI о входящем сообщении
            if self.ui_callback:
                self.ui_callback('incoming_message', {'nick': nick, 'text': text})

            # Проверка: включен ли бот
            bot_enabled = self.db.get_setting('bot_enabled', False)
            if not bot_enabled:
                logger.info(f"Bot disabled, message from {nick} saved but not processed", "PROCESS")
                return

            # Шаг 6: Определение роли для ответа
            role = self.determine_role(translated_text)
            temperature = self.roles.get(role, 0.7)
            logger.info(f"Role selected: {role} (temp={temperature})", "ROLE")

            # Шаг 7: Получение контекста из RAG
            # Объединяем глобальный контекст (namespace=0) и контекст пользователя
            logger.debug("Fetching RAG context", "RAG")
            context = await rag.get_context(translated_text, nick)

            # Шаг 8: Формирование промпта для LLM
            prompt = f"""You are a {role} assistant.
Context: {context}

User message: {translated_text}

Respond in the same language as the original user message. Be helpful and friendly."""

            logger.debug(f"Prompt created (length={len(prompt)})", "LLM")

            # Шаг 9: Выбор лучшей модели для пользователя
            model = await self.llm.select_best_model(nick)

            if not model:
                # Если модель не найдена - берем первую доступную
                models = self.db.get_free_llms()
                if models:
                    model = models[0][0]
                    logger.warning(f"No model found for {nick}, using default: {model}", "LLM")
                else:
                    logger.error("No models available in database", "LLM")
                    return

            logger.info(f"Using model: {model}", "LLM")

            # Шаг 10: Генерация ответа от LLM
            response = await self.llm.call_llm(model, prompt, temperature)

            if response:
                logger.info(f"Response generated (length={len(response)})", "LLM")

                # Шаг 11: Перевод ответа на английский для RAG
                response_translated = await translator.translate_to_english(response)

                # Шаг 12: Сохранение ответа в историю
                self.db.add_history(nick, response, 'bot')

                # Шаг 13: Сохранение ответа в RAG
                await rag.upsert(response, nick)
                if response_translated != response:
                    await rag.upsert(response_translated, nick, {'translated': True})

                logger.info(f"Response to {nick} processed successfully", "PROCESS")

                # Уведомление UI об исходящем сообщении
                if self.ui_callback:
                    self.ui_callback('outgoing_message', {'nick': nick, 'text': response})

                # Шаг 14: Скоринг моделей
                iteration = self.db.increment_iteration()
                score_refresh = env_loader.get_int('SCORE_REFRESH_EVERY', 5)
                score_top_n = env_loader.get_int('SCORE_TOP_N', 10)

                if iteration % score_refresh == 0:
                    # Полный ресоринг всех моделей
                    logger.info(f"Triggering full model re-scoring (iteration {iteration})", "SCORING")
                    all_models = [m[0] for m in self.db.get_free_llms()]
                    await self.llm.full_scoring(all_models[:20], translated_text, temperature, 'system')
                else:
                    # Скоринг только топ-N моделей для данного пользователя
                    logger.debug(f"Scoring top {score_top_n} models for {nick}", "SCORING")
                    top_models = self.db.get_top_models(score_top_n)
                    if top_models:
                        await self.llm.score_top_models(top_models, translated_text, temperature, nick)

                    # Обновление закрепленной модели для пользователя
                    best_model = self.db.get_best_model_for_user(nick)
                    if best_model:
                        self.db.set_user_model(nick, best_model)
                        logger.debug(f"Best model for {nick}: {best_model}", "SCORING")

                # Обновление времени последнего сообщения (для проактивных агентов)
                self.db.set_setting('last_message_time', datetime.now().timestamp())

            else:
                logger.error(f"Failed to generate response for {nick}", "LLM")

        except Exception as e:
            logger.error(f"Error processing message from {nick}: {e}", "PROCESS")
            log_error(e, "MainWorkflow")

    async def handle_incoming_message(self, nick: str, text: str):
        """
        Обработчик входящих сообщений из Telegram
        Добавляет сообщение в очередь если пользователь не в blacklist
        """
        # Проверка черного списка
        if self.db.is_blacklisted(nick):
            logger.debug(f"Incoming message from blacklisted {nick} ignored", "TELEGRAM")
            return

        # Добавление в очередь для последующей обработки
        self.db.add_to_queue(nick, text)
        queue_size = self.db.get_queue_size()

        logger.info(f"Message from {nick} added to queue (size: {queue_size})", "TELEGRAM")

        # Уведомление UI об изменении размера очереди
        if self.ui_callback:
            self.ui_callback('queue_size', queue_size)
