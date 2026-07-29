import pandas as pd
from .base_strategy import BaseStrategy

# 터틀 트레이딩 전략 (단순화 버전)
# 20일 신고가 돌파 매수, ATR 기반 손절, 10일 신저가 청산
class TurtleStrategy(BaseStrategy):
    def __init__(self, df, entry_window=20, exit_window=10, atr_multiplier=2.0):
        super().__init__(df)
        self.entry_window = entry_window
        self.exit_window = exit_window
        self.atr_multiplier = atr_multiplier  # 손절 폭 = entry_price - N × ATR

    def add_indicators(self):
        # 진입 기준: N일 최고가 돌파
        self.df['Entry_High'] = self.df['high_price'].rolling(window=self.entry_window).max().shift(1)
        # 청산 기준: N일 최저가 이탈 (진입 window보다 짧게 잡는 게 터틀 원칙)
        self.df['Exit_Low'] = self.df['low_price'].rolling(window=self.exit_window).min().shift(1)

    def generate_signals(self):
        self.add_indicators()
        self.df['Signal'] = 0.0

        in_position = False
        entry_price = None
        stop_price = None

        for i in self.df.index:
            close = self.df.loc[i, 'close_price']
            entry_high = self.df.loc[i, 'Entry_High']
            exit_low = self.df.loc[i, 'Exit_Low']
            atr = self.df.loc[i, 'atr_14']

            if pd.isna(entry_high) or pd.isna(exit_low):
                continue

            if in_position:
                # 우선순위 1: ATR 기반 손절 (터틀 핵심 규칙)
                if stop_price is not None and close <= stop_price:
                    self.df.loc[i, 'Signal'] = -2.0
                    in_position = False
                    entry_price = None
                    stop_price = None
                    continue

                # 우선순위 2: N일 신저가 이탈 청산
                if close < exit_low:
                    self.df.loc[i, 'Signal'] = -1.0
                    in_position = False
                    entry_price = None
                    stop_price = None

            else:
                # 매수: N일 신고가 돌파
                if close > entry_high:
                    self.df.loc[i, 'Signal'] = 1.0
                    in_position = True
                    entry_price = close
                    # ATR 없으면(초반 데이터 부족) 손절선 생략
                    if not pd.isna(atr):
                        stop_price = entry_price - self.atr_multiplier * atr

        self.df = self.df.dropna(subset=['Entry_High', 'Exit_Low'])
        return self.df