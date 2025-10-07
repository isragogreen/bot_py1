import os

_env_cache = {}

def get_env(key, default=None):
    """
    Получает значение переменной из .env.
    Кэширует значения для ускорения.
    """
    global _env_cache
    if not _env_cache:
        env_file = os.getenv("ENV_FILE", ".env")
        if not os.path.exists(env_file):
            return default
        with open(env_file, encoding='utf-8') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    k, v = line.strip().split('=', 1)
                    _env_cache[k.strip()] = v.strip()
    return _env_cache.get(key, default)
