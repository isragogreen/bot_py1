import os
from pathlib import Path
from dotenv import load_dotenv

class EnvLoader:
    def __init__(self):
        env_path = Path(__file__).parent / '.env'
        load_dotenv(env_path)
        self._cache = {}

    def get(self, key: str, default=None):
        if key in self._cache:
            return self._cache[key]

        value = os.getenv(key, default)
        self._cache[key] = value
        return value

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.get(key, default))
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.get(key, default))
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')

    def has_key(self, key: str) -> bool:
        return self.get(key) is not None and self.get(key) != ''

    def get_list(self, key: str, default=None) -> list:
        value = self.get(key, '')
        if not value:
            return default or []
        return [item.strip() for item in value.split(',')]

env_loader = EnvLoader()
