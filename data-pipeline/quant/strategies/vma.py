import pandas as pd
from .base_strategy import BaseStrategy

# 가변 이동평균 전략
class VMAStrategy(BaseStrategy):
    def __init__(self, df, short_window=20, long_window=60):
        super().__init__(df)
        self.short_window = short_window
        self.long_window = long_window

    def add_indicators(self):
        self.df['VMA_short'] = self.df['close_price'].rolling(window=self.short_window).mean()
        self.df['VMA_long'] = self.df['close_price'].rolling(window=self.long_window).mean()

    def generate_signals(self):
        self.add_indicators()
        self.df = self.df.reset_index(drop=True)
        self.df['Signal'] = 0.0

        in_position = False

        for i in range(1, len(self.df)):
            s_today = self.df.loc[i, 'VMA_short']
            l_today = self.df.loc[i, 'VMA_long']
            s_prev = self.df.loc[i - 1, 'VMA_short']
            l_prev = self.df.loc[i - 1, 'VMA_long']
            close = self.df.loc[i, 'close_price']
            ma_60 = self.df.loc[i, 'ma_60']

            if pd.isna(s_today) or pd.isna(l_today) or pd.isna(s_prev) or pd.isna(l_prev):
                continue

            if in_position:
                # 우선순위 1: ma_60 이탈 손절
                if not pd.isna(ma_60) and close < ma_60:
                    self.df.loc[i, 'Signal'] = -2.0
                    in_position = False
                    continue

                # 우선순위 2: 데드크로스 매도
                if s_prev >= l_prev and s_today < l_today:
                    self.df.loc[i, 'Signal'] = -1.0
                    in_position = False

            else:
                # 골든크로스 매수
                if s_prev < l_prev and s_today >= l_today:
                    self.df.loc[i, 'Signal'] = 1.0
                    in_position = True

        self.df = self.df.drop(columns=['VMA_short', 'VMA_long'])
        return self.df