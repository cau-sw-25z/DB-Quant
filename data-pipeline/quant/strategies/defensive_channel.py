from .base_strategy import BaseStrategy
import pandas as pd

# 저변동성 방어주 종목에 적용하는 전략
# MA20 기준 ±envelope_pct% 채널 하단 이탈 시 매수, 상단 도달 시 매도
class DefensiveChannelStrategy(BaseStrategy):
    def __init__(self, df):
        super().__init__(df)

    def add_indicators(self):
        pass

    def generate_signals(self):
        self.add_indicators()
        self.df['Signal'] = 0.0

        for i in self.df.index:
            close = self.df.loc[i, 'close_price']
            bb_upper = self.df.loc[i, 'bb_upper']
            bb_lower = self.df.loc[i, 'bb_lower']
            bb_mid = self.df.loc[i, 'bb_mid']
            rsi = self.df.loc[i, 'rsi_14']

            if pd.isna(bb_upper) or pd.isna(bb_mid) or pd.isna(bb_lower) or pd.isna(rsi):
                continue

            # 우선순위 1: 손절 — 채널 하단보다 3% 더 밀릴 때
            if close < bb_lower * 0.98:
                self.df.loc[i, 'Signal'] = -2.0

            # 우선순위 2: 익절 — 채널 상단 도달
            elif close > bb_upper:
                self.df.loc[i, 'Signal'] = -1.0
            
            elif close > bb_mid:
                self.df.loc[i, 'Signal'] = -0.5

            # 우선순위 3: 매수 — 채널 하단 이탈
            elif close < bb_lower and rsi <= 35:
                self.df.loc[i, 'Signal'] = 1.0

        self.df = self.df.dropna(subset=['bb_upper', 'bb_mid', 'bb_lower', 'rsi_14'])
        return self.df