from abc import ABC, abstractmethod
import numpy as np


# Abstract base class for vector embedding processes
class VectorEmbeddingProcess(ABC):
    __model = None

    def __init__(self):
        self.load_model()

    @abstractmethod
    def load_model(self):
        raise NotImplementedError

    @abstractmethod
    def embed(self, text: str) -> np.ndarray:
        raise NotImplementedError
