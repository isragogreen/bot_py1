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

class MainWorkflow:
    def __init__(self, db: Database, ui_callback: Optional[Callable] = None):
        self.db = db
        self.ui_callback = ui_callback
        self.llm = LLMSubworkflow(db)
        self.doc_processor = DocProcessing(db)
        self.proactive: Optional[ProactiveWorkflow] = None

        self.running = False
        self.queue_task: Optional[asyncio.Task] = None

        self.roles = {
            'TECH': env_loader.get_float('TECH_temp', 0.1),
            'FRIEND': env_loader.get_float('FRIEND_temp', 0.9),
            'ADVISOR': env_loader.get_float('ADVISOR_temp', 0.4),
            'AGITATOR': env_loader.get_float('AGITATOR_temp', 0.5),
            'OPERATOR': env_loader.get_float('OPERATOR_temp', 0.3)
        }

        for role in self.roles.keys():
            self.db.add_to_blacklist(role.lower())

    def set_proactive(self, proactive: ProactiveWorkflow):
        self.proactive = proactive

    async def initialize(self):
        self.log("Initializing system...")

        only_free = self.db.get_setting('only_free_llms', True)
        models = await fetch_free_llms(only_free)
        self.db.set_free_llms(models)
        self.log(f"Loaded {len(models)} models")

        await self.doc_processor.clone_and_process()

        iteration = self.db.get_iteration_count()
        if iteration == 0:
            self.log("Performing initial full scoring...")
            model_list = [m[0] for m in models]
            if model_list:
                await self.llm.full_scoring(
                    model_list[:20],
                    "Hello, how are you?",
                    0.7,
                    'system'
                )

        self.log("System initialized")

    def log(self, message: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)

        if self.ui_callback:
            self.ui_callback('log', log_msg)

    async def start(self):
        if self.running:
            return

        await self.initialize()

        self.running = True
        self.queue_task = asyncio.create_task(self.process_queue())

        if self.proactive:
            self.proactive.start()

        self.log("Main workflow started")

    async def stop(self):
        if not self.running:
            return

        self.running = False

        if self.queue_task:
            self.queue_task.cancel()
            try:
                await self.queue_task
            except asyncio.CancelledError:
                pass

        if self.proactive:
            await self.proactive.stop()

        self.log("Main workflow stopped")

    async def process_queue(self):
        while self.running:
            try:
                item = self.db.get_queue_item()

                if item:
                    item_id, nick, text, ts = item
                    await self.process_message(nick, text)
                    self.db.remove_from_queue(item_id)
                else:
                    await asyncio.sleep(1)

            except Exception as e:
                self.log(f"Queue processing error: {e}")
                await asyncio.sleep(1)

    def clean_message(self, text: str) -> str:
        remove_emoji = self.db.get_setting('remove_emoji', True)

        if remove_emoji:
            emoji_pattern = re.compile(
                "["
                "\U0001F600-\U0001F64F"
                "\U0001F300-\U0001F5FF"
                "\U0001F680-\U0001F6FF"
                "\U0001F1E0-\U0001F1FF"
                "\U00002702-\U000027B0"
                "\U000024C2-\U0001F251"
                "]+",
                flags=re.UNICODE
            )
            text = emoji_pattern.sub('', text)

        return text.lower().strip()

    def determine_role(self, text: str) -> str:
        text_lower = text.lower()

        if any(word in text_lower for word in ['help', 'error', 'bug', 'code', 'technical']):
            return 'TECH'
        elif any(word in text_lower for word in ['feel', 'sad', 'happy', 'friend']):
            return 'FRIEND'
        elif any(word in text_lower for word in ['advice', 'suggest', 'recommend', 'should']):
            return 'ADVISOR'
        elif any(word in text_lower for word in ['boring', 'nothing', 'quiet']):
            return 'AGITATOR'
        else:
            return 'OPERATOR'

    async def process_message(self, nick: str, text: str):
        try:
            if self.db.is_blacklisted(nick):
                self.log(f"Message from blacklisted user {nick} ignored")
                return

            cleaned_text = self.clean_message(text)

            translated_text = await translator.translate_to_english(cleaned_text)

            self.db.add_history(nick, cleaned_text, 'user')

            await rag.upsert(cleaned_text, nick)
            if translated_text != cleaned_text:
                await rag.upsert(translated_text, nick, {'translated': True})

            bot_enabled = self.db.get_setting('bot_enabled', False)
            if not bot_enabled:
                self.log(f"Bot disabled, message from {nick} saved but not processed")
                return

            role = self.determine_role(translated_text)
            temperature = self.roles.get(role, 0.7)

            context = await rag.get_context(translated_text, nick)

            prompt = f"""You are a {role} assistant.
Context: {context}

User message: {translated_text}

Respond in the same language as the original user message. Be helpful and friendly."""

            model = await self.llm.select_best_model(nick)

            if not model:
                models = self.db.get_free_llms()
                if models:
                    model = models[0][0]
                else:
                    self.log(f"No models available")
                    return

            response = await self.llm.call_llm(model, prompt, temperature)

            if response:
                response_translated = await translator.translate_to_english(response)

                self.db.add_history(nick, response, 'bot')

                await rag.upsert(response, nick)
                if response_translated != response:
                    await rag.upsert(response_translated, nick, {'translated': True})

                self.log(f"Response sent to {nick} (role: {role}, model: {model})")

                if self.ui_callback:
                    self.ui_callback('response', {'nick': nick, 'text': response})

                iteration = self.db.increment_iteration()
                score_refresh = env_loader.get_int('SCORE_REFRESH_EVERY', 5)
                score_top_n = env_loader.get_int('SCORE_TOP_N', 10)

                if iteration % score_refresh == 0:
                    self.log(f"Triggering model scoring (iteration {iteration})")
                    all_models = [m[0] for m in self.db.get_free_llms()]
                    await self.llm.full_scoring(all_models[:20], translated_text, temperature, 'system')
                else:
                    top_models = self.db.get_top_models(score_top_n)
                    if top_models:
                        await self.llm.score_top_models(top_models, translated_text, temperature, nick)

                    best_model = self.db.get_best_model_for_user(nick)
                    if best_model:
                        self.db.set_user_model(nick, best_model)

                self.db.set_setting('last_message_time', datetime.now().timestamp())

        except Exception as e:
            self.log(f"Error processing message from {nick}: {e}")

    async def handle_incoming_message(self, nick: str, text: str):
        if self.db.is_blacklisted(nick):
            return

        self.db.add_to_queue(nick, text)
        self.log(f"Message from {nick} added to queue (size: {self.db.get_queue_size()})")

        if self.ui_callback:
            self.ui_callback('queue_size', self.db.get_queue_size())
