"""
Модуль для работы с Retrieval-Augmented Generation (RAG).
Запросы к векторной базе, объединение глобального и пользовательского контекста.
"""

import uuid
from env_loader import get_env
from error_handler import log_error

VECTOR_DB = get_env("VECTOR_DB", "pinecone")

class RAGSubworkflow:
    """
    Класс для работы с RAG: запросы, upsert, объединение контекстов.
    """

    def __init__(self, vector_db_client, embeddings_generator):
        self.vector_db_client = vector_db_client
        self.embeddings_generator = embeddings_generator

    def upsert(self, text: str, namespace: str, metadata: dict):
        """
        Сохраняет embedding в векторную базу.
        """
        try:
            if VECTOR_DB == "pinecone":
                # Pinecone сам создаёт эмбеддинг из chunk_text
                vector_id = str(uuid.uuid4())
                record = {
                    "_id": vector_id,
                    "chunk_text": text,
                    **metadata
                }
                self.vector_db_client.upsert_records(namespace, [record])
            elif VECTOR_DB == "qdrant":
                # Для Qdrant эмбеддинг создаём вручную
                point_id = str(uuid.uuid4())
                embedding = self.embeddings_generator.get_embedding(text)
                # Qdrant ожидает payload и vector
                point = self.vector_db_client.models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=metadata | {"chunk_text": text}
                )
                self.vector_db_client.upload_points(
                    collection_name=namespace,
                    points=[point]
                )
            else:
                raise ValueError("Неизвестный тип векторной БД")
        except Exception as e:
            log_error(e, "RAGSubworkflow.upsert")

    def query(self, query_text: str, namespace: str, top_k: int = 5):
        """
        Выполняет запрос к векторной базе.
        """
        try:
            if VECTOR_DB == "pinecone":
                results = self.vector_db_client.query(
                    namespace=namespace,
                    queries=[query_text],
                    top_k=top_k,
                    include_metadata=True
                )
                return [
                    {
                        "score": match["score"],
                        "metadata": match["metadata"]
                    }
                    for match in results["matches"]
                ]
            elif VECTOR_DB == "qdrant":
                embedding = self.embeddings_generator.get_embedding(query_text)
                results = self.vector_db_client.search(
                    collection_name=namespace,
                    query_vector=embedding,
                    limit=top_k,
                    with_payload=True
                )
                return [
                    {
                        "score": point["score"],
                        "metadata": point["payload"]
                    }
                    for point in results
                ]
            else:
                raise ValueError("Неизвестный тип векторной БД")
        except Exception as e:
            log_error(e, "RAGSubworkflow.query")
            return []
