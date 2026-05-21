from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    def __init__(self, df):
        self.df = df.copy()

    @abstractmethod
    def add_indicators(self):
        pass

    @abstractmethod
    def generate_signals(self):
        pass