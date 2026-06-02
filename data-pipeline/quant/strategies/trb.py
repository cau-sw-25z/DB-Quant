import pandas as pd
from .base_strategy import BaseStrategy

# 트레이딩 레인지 브레이크아웃 전략
class TRBStrategy(BaseStrategy):
    def __init__(self, df, n=50):
        super().__init__(df)
        self.n = n
        
    def add_indicators(self):
        self.df['N_High'] = self.df['high_price'].rolling(window=self.n).max().shift(1)
        self.df['N_Low'] = self.df['low_price'].rolling(window=self.n).min().shift(1)

    def generate_signals(self):
        self.add_indicators()
        self.df['Signal'] = 0.0
        
        for i in self.df.index:
            close = self.df.loc[i, 'close_price']
            n_high = self.df.loc[i, 'N_High']
            n_low = self.df.loc[i, 'N_Low']
            
            if pd.isna(n_high) or pd.isna(n_low):
                continue
            
            # 매수: 종가가 N일 최고가 돌파
            if close > n_high:
                self.df.loc[i, 'Signal'] = 1.0
                
            # 매도: 종가가 N일 최저가 이탈
            elif close < n_low:
                self.df.loc[i, 'Signal'] = -1.0
                
        self.df = self.df.dropna(subset=['N_High', 'N_Low'])
        return self.df