"""
Модуль для генерации эмбеддингов текста.
Использует SentenceTransformers или другой выбранный метод.
"""

from env_loader import get_env
from error_handler import log_error

EMBED_DIM = int(get_env("EMBED_DIM", 384))

class EmbeddingsGenerator:
    """
    Класс для генерации эмбеддингов текста.
    """

    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer
            # Выбор модели по размеру эмбеддинга
            if EMBED_DIM == 384:
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
            else:
                self.model = SentenceTransformer('all-mpnet-base-v2')
        except Exception as e:
            log_error(e, "EmbeddingsGenerator.__init__")
            self.model = None

    def get_embedding(self, text: str):
        """
        Получает эмбеддинг для текста.
        """
        if not self.model or not text.strip():
            return []
        try:
            return self.model.encode(text)
        except Exception as e:
            log_error(e, "EmbeddingsGenerator.get_embedding")
            return []

embeddings = EmbeddingsGenerator()
