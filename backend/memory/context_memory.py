from abc import ABC, abstractmethod

class ContextMemory(ABC):
    @abstractmethod
    def store(self, text: str, metadata: dict) -> None: ...

    @abstractmethod
    def query_similar(self, text: str, n_results: int = 5) -> list: ...

class NoOpMemory(ContextMemory):
    def store(self, text: str, metadata: dict) -> None:
        pass

    def query_similar(self, text: str, n_results: int = 5) -> list:
        return []