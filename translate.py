import aiohttp
from env_loader import env_loader

class Translator:
    def __init__(self):
        self.api_key = env_loader.get('TRANSLATE_API_KEY')
        self.enabled = bool(self.api_key)

    async def translate_to_english(self, text: str) -> str:
        if not self.enabled:
            return text

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://translation.googleapis.com/language/translate/v2',
                    params={'key': self.api_key},
                    json={
                        'q': text,
                        'target': 'en',
                        'format': 'text'
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['data']['translations'][0]['translatedText']
        except Exception as e:
            print(f"Translation error: {e}")

        return text

    async def detect_language(self, text: str) -> str:
        if not self.enabled:
            return 'unknown'

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://translation.googleapis.com/language/translate/v2/detect',
                    params={'key': self.api_key},
                    json={'q': text}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['data']['detections'][0][0]['language']
        except Exception as e:
            print(f"Language detection error: {e}")

        return 'unknown'

translator = Translator()
