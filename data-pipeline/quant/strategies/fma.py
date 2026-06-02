import pandas as pd
from .base_strategy import BaseStrategy

# 고정 이동평균 전략
class FMAStrategy(BaseStrategy):
    def __init__(self, short_window=20, long_window=60, hold_days=10):
        super().__init__()
        self.short_window = short_window
        self.long_window = long_window
        self.hold_days = hold_days
        
    def add_indicators(self):
        self.df['FMA_short'] = self.df['close_price'].rolling(window=self.short_window).mean()
        self.df['FMA_long'] = self.df['close_price'].rolling(window=self.long_window).mean()

    def generate_signals(self):
        self.add_indicators()
        self.df = self.df.reset_index(drop=True)
        self.df['signal'] = 0.0
        
        for i in range(1, len(self.df)):
            s_today = self.df.loc[i, 'FMA_short']
            l_today = self.df.loc[i, 'FMA_long']
            s_prev = self.df.loc[i-1, 'FMA_short']
            l_prev = self.df.loc[i-1, 'FMA_long']
            
            if pd.isna(s_today) or pd.isna(l_today) or pd.isna(s_prev) or pd.isna(l_prev):
                continue
            
            # 청산 예정일에 도달 -> 기계적 청산
            if exit_row is not None and i >= exit_row:
                self.df.loc[i, 'signal'] = -1.0
                exit_row = None
                
            elif exit_row is None:
                if s_prev < l_prev and s_today >= l_today:
                    self.df.loc[i, 'signal'] = 1.0
                    exit_row = i + self.hold_days
            
        self.df = self.df.drop(columns=['FMA_short', 'FMA_long'])
        return self.df