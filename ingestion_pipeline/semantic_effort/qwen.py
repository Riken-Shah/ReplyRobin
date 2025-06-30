from sentence_transformers import SentenceTransformer
from .vector_embeeding import VectorEmbeddingProcess
import numpy as np

class QwenEmbeddingProcess(VectorEmbeddingProcess):
    def load_model(self):
        self.__model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B")

    def embed(self, text: str) -> np.ndarray:
        embedding = self.__model.encode(text, normalize_embeddings=True)
        return embedding


if __name__ == "__main__":
    qwen_embedding_process = QwenEmbeddingProcess()
    text_emb = qwen_embedding_process.embed("Hello, world!")
    text_emb = qwen_embedding_process.embed("Hello, world!" * 5)
    text_emb = qwen_embedding_process.embed("Hello, world!" * 100)
    text_emb = qwen_embedding_process.embed("Hello, world!" * 7)
