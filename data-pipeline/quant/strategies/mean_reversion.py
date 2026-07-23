import pandas as pd
from .base_strategy import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    def __init__(self, df):
        super().__init__(df)

    def add_indicators(self):
        pass

    def generate_signals(self):
        self.df['Signal'] = 0.0
        self.df = self.df.dropna(subset=['bb_upper', 'bb_mid', 'bb_lower', 'rsi_14'])
        self.df = self.df.reset_index(drop=True)

        for i in self.df.index:
            close    = self.df.loc[i, 'close_price']
            bb_upper = self.df.loc[i, 'bb_upper']
            bb_mid   = self.df.loc[i, 'bb_mid']
            bb_lower = self.df.loc[i, 'bb_lower']
            rsi      = self.df.loc[i, 'rsi_14']

            if pd.isna(bb_upper) or pd.isna(bb_mid) or pd.isna(bb_lower) or pd.isna(rsi):
                continue

            # 우선순위 1: 긴급 손절 — 하단밴드 3% 이탈
            # ✅ 수정: 0.95 → 0.97 (너무 늦은 손절 방지)
            if close < bb_lower * 0.97:
                self.df.loc[i, 'Signal'] = -2.0

            # 우선순위 2: 전량 익절 — 상단밴드 도달
            elif close > bb_upper:
                self.df.loc[i, 'Signal'] = -1.0

            # 우선순위 3: 부분 익절 — 중심선(bb_mid) 회복
            elif close > bb_mid:
                self.df.loc[i, 'Signal'] = -0.5

            # 우선순위 4: 매수 — 하단밴드 이탈 + 과매도
            # ✅ 수정: rsi < 40 → rsi < 35 (진입 조건 더 선별적으로)
            elif close < bb_lower and rsi < 35:
                self.df.loc[i, 'Signal'] = 1.0

        return self.df