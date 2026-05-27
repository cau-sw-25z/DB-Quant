from .base_strategy import BaseStrategy
import pandas as pd

# 중대형 성장주 / 추세추종형(TREND_FOLLOWING) 종목에 적용하는 전략
# 60일선 위에서 20일 전고점 돌파 시 매수, 20일선 붕괴 시 매도
class TrendFollowingStrategy(BaseStrategy):
    def __init__(self, df, breakout_window=20):
        super().__init__(df)
        self.breakout_window = breakout_window

    def add_indicators(self):
        # 20일 전고점 (돌파 기준)
        self.df['Recent_High'] = self.df['high_price'].rolling(self.breakout_window).max().shift(1)
        # 이격도 과열선
        self.df['Overheat_Line'] = self.df['ma_20'] * 1.15

    def generate_signals(self):
        self.add_indicators()
        self.df['Signal'] = 0.0

        for i in self.df.index:
            close    = self.df.loc[i, 'close_price']
            ma_20    = self.df.loc[i, 'ma_20']
            ma_60    = self.df.loc[i, 'ma_60']
            rec_high = self.df.loc[i, 'Recent_High']
            overheat = self.df.loc[i, 'Overheat_Line']

            if pd.isna(ma_20) or pd.isna(ma_60) or pd.isna(rec_high):
                continue

            # 우선순위 1: 긴급 손절 — 60일선 완전 붕괴
            if close < ma_60:
                self.df.loc[i, 'Signal'] = -2.0

            # 우선순위 2: 기본 청산 — 20일선 붕괴
            elif close < ma_20:
                self.df.loc[i, 'Signal'] = -1.0

            # 우선순위 3: 부분 익절 — 이격도 과열
            elif close > overheat:
                self.df.loc[i, 'Signal'] = -0.5

            # 우선순위 4: 매수 — 60일선 위 + 20일 전고점 돌파
            elif close > ma_60 and close > rec_high:
                self.df.loc[i, 'Signal'] = 1.0

        self.df = self.df.dropna(subset=['ma_20', 'ma_60', 'Recent_High'])
        return self.df