from sentence_transformers import SentenceTransformer
from typing import List
from env_loader import env_loader

class EmbeddingGenerator:
    def __init__(self):
        embed_dim = env_loader.get_int('EMBED_DIM', 384)

        if embed_dim == 768:
            model_name = 'sentence-transformers/all-mpnet-base-v2'
        else:
            model_name = 'sentence-transformers/all-MiniLM-L6-v2'

        self.model = SentenceTransformer(model_name)

    def generate(self, text: str) -> List[float]:
        embedding = self.model.encode(text)
        return embedding.tolist()

    def generate_batch(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts)
        return [emb.tolist() for emb in embeddings]

embedding_generator = EmbeddingGenerator()
