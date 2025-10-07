import asyncio
from typing import List, Optional
from pinecone import Pinecone
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from embeddings import embedding_generator
from env_loader import env_loader

class RAGSubworkflow:
    def __init__(self):
        self.vector_db = env_loader.get('VECTOR_DB', 'pinecone')
        self.topk_docs = env_loader.get_int('RAG_TOPK_DOCS', 5)
        self.topk_user = env_loader.get_int('RAG_TOPK_USER', 10)
        self.embed_dim = env_loader.get_int('EMBED_DIM', 384)

        if self.vector_db == 'pinecone':
            self._init_pinecone()
        else:
            self._init_qdrant()

    def _init_pinecone(self):
        api_key = env_loader.get('PINECONE_API_KEY')
        if not api_key:
            self.enabled = False
            return

        try:
            pc = Pinecone(api_key=api_key)

            index_name = 'bot-rag-index'
            existing_indexes = pc.list_indexes()

            if index_name not in [idx.name for idx in existing_indexes]:
                pc.create_index(
                    name=index_name,
                    dimension=self.embed_dim,
                    metric='cosine'
                )

            self.index = pc.Index(index_name)
            self.enabled = True
        except Exception as e:
            print(f"Pinecone init error: {e}")
            self.enabled = False

    def _init_qdrant(self):
        api_key = env_loader.get('QDRANT_API_KEY')
        url = env_loader.get('QDRANT_URL')

        if not api_key or not url:
            self.enabled = False
            return

        try:
            self.client = QdrantClient(url=url, api_key=api_key)

            collection_name = 'bot_rag_collection'
            collections = self.client.get_collections().collections

            if collection_name not in [c.name for c in collections]:
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.embed_dim,
                        distance=Distance.COSINE
                    )
                )

            self.collection_name = collection_name
            self.enabled = True
        except Exception as e:
            print(f"Qdrant init error: {e}")
            self.enabled = False

    async def upsert(self, text: str, namespace: str, metadata: Optional[dict] = None):
        if not self.enabled:
            return

        try:
            embedding = embedding_generator.generate(text)
            vector_id = f"{namespace}_{hash(text) % 10**10}"

            if self.vector_db == 'pinecone':
                self.index.upsert(
                    vectors=[(vector_id, embedding, {'namespace': namespace, 'text': text, **(metadata or {})})],
                    namespace=namespace
                )
            else:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=[
                        PointStruct(
                            id=vector_id,
                            vector=embedding,
                            payload={'namespace': namespace, 'text': text, **(metadata or {})}
                        )
                    ]
                )
        except Exception as e:
            print(f"RAG upsert error: {e}")

    async def query(self, query_text: str, namespace: str, top_k: int = 5) -> List[str]:
        if not self.enabled:
            return []

        try:
            embedding = embedding_generator.generate(query_text)

            if self.vector_db == 'pinecone':
                results = self.index.query(
                    vector=embedding,
                    top_k=top_k,
                    namespace=namespace,
                    include_metadata=True
                )
                return [match.metadata.get('text', '') for match in results.matches]
            else:
                results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=embedding,
                    limit=top_k,
                    query_filter=Filter(
                        must=[FieldCondition(key='namespace', match=MatchValue(value=namespace))]
                    )
                )
                return [hit.payload.get('text', '') for hit in results]
        except Exception as e:
            print(f"RAG query error: {e}")
            return []

    async def get_context(self, query_text: str, user_namespace: str) -> str:
        global_docs = await self.query(query_text, '0', self.topk_docs)
        user_docs = await self.query(query_text, user_namespace, self.topk_user)

        all_docs = global_docs + user_docs
        return '\n\n'.join(all_docs[:self.topk_docs + self.topk_user])

rag = RAGSubworkflow()
