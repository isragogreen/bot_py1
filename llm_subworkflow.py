import aiohttp
import asyncio
from typing import Optional, List
from env_loader import env_loader
from db import Database

class LLMSubworkflow:
    def __init__(self, db: Database):
        self.db = db
        self.api_key = env_loader.get('OPENROUTER_API_KEY')
        self.enabled = bool(self.api_key)
        self.quality_threshold = env_loader.get_float('QUALITY_THRESHOLD', 7.0)
        self.trial_count = env_loader.get_int('TRIAL_COUNT', 3)

    async def call_llm(self, model: str, prompt: str, temperature: float = 0.7) -> Optional[str]:
        if not self.enabled:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://openrouter.ai/api/v1/chat/completions',
                    headers={
                        'Authorization': f'Bearer {self.api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': model,
                        'messages': [{'role': 'user', 'content': prompt}],
                        'temperature': temperature
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content']
        except Exception as e:
            print(f"LLM call error for {model}: {e}")

        return None

    async def evaluate_response(self, response: str) -> float:
        if not response:
            return 0.0

        score = 5.0

        if len(response) > 50:
            score += 1.0
        if len(response) > 150:
            score += 1.0

        words = response.split()
        if len(words) > 10:
            score += 0.5
        if len(words) > 30:
            score += 0.5

        if '?' in response or '!' in response:
            score += 0.5

        if any(word.lower() in response.lower() for word in ['however', 'therefore', 'because', 'additionally']):
            score += 0.5

        return min(score, 10.0)

    async def score_model(self, model: str, prompt: str, temperature: float, nick: str) -> float:
        scores = []

        for _ in range(self.trial_count):
            response = await self.call_llm(model, prompt, temperature)
            if response:
                score = await self.evaluate_response(response)
                scores.append(score)
            else:
                scores.append(0.0)

        avg_score = sum(scores) / len(scores) if scores else 0.0

        self.db.set_model_score(nick, model, avg_score)

        return avg_score

    async def score_top_models(self, models: List[str], prompt: str, temperature: float, nick: str):
        tasks = [self.score_model(model, prompt, temperature, nick) for model in models]
        await asyncio.gather(*tasks)

    async def full_scoring(self, models: List[str], prompt: str, temperature: float, nick: str = 'system'):
        print(f"Starting full scoring for {len(models)} models...")
        await self.score_top_models(models, prompt, temperature, nick)
        print(f"Full scoring completed")

    async def select_best_model(self, nick: str) -> Optional[str]:
        user_model = self.db.get_user_model(nick)

        if user_model:
            return user_model

        best_model = self.db.get_best_model_for_user(nick)

        if best_model:
            self.db.set_user_model(nick, best_model)
            return best_model

        top_models = self.db.get_top_models(1)
        if top_models:
            model = top_models[0]
            self.db.set_user_model(nick, model)
            return model

        return None
