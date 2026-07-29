import pandas as pd
from .base_strategy import BaseStrategy

# 트레이딩 레인지 브레이크아웃 전략
class TRBStrategy(BaseStrategy):
    def __init__(self, df, n=50, stop_loss_pct=0.08):
        super().__init__(df)
        self.n = n
        self.stop_loss_pct = stop_loss_pct  # entry_price 대비 손절 기준 (기본 8%)

    def add_indicators(self):
        self.df['N_High'] = self.df['high_price'].rolling(window=self.n).max().shift(1)
        self.df['N_Low'] = self.df['low_price'].rolling(window=self.n).min().shift(1)

    def generate_signals(self):
        self.add_indicators()
        self.df['Signal'] = 0.0

        in_position = False
        entry_price = None

        for i in self.df.index:
            close = self.df.loc[i, 'close_price']
            n_high = self.df.loc[i, 'N_High']
            n_low = self.df.loc[i, 'N_Low']

            if pd.isna(n_high) or pd.isna(n_low):
                continue

            if in_position:
                # 우선순위 1: entry_price 대비 손절
                loss_rate = (close - entry_price) / entry_price
                if loss_rate <= -self.stop_loss_pct:
                    self.df.loc[i, 'Signal'] = -2.0
                    in_position = False
                    entry_price = None
                    continue

                # 우선순위 2: N일 최저가 이탈 매도
                if close < n_low:
                    self.df.loc[i, 'Signal'] = -1.0
                    in_position = False
                    entry_price = None

            else:
                # 매수: 종가가 N일 최고가 돌파
                if close > n_high:
                    self.df.loc[i, 'Signal'] = 1.0
                    in_position = True
                    entry_price = close

        self.df = self.df.dropna(subset=['N_High', 'N_Low'])
        return self.df