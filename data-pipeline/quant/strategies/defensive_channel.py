from .base_strategy import BaseStrategy
import pandas as pd

# 저변동성 방어주 종목에 적용하는 전략
# MA20 기준 ±envelope_pct% 채널 하단 이탈 시 매수, 상단 도달 시 매도
class DefensiveChannelStrategy(BaseStrategy):
    def __init__(self, df, envelope_pct=0.05):
        super().__init__(df)
        self.envelope_pct = envelope_pct

    def add_indicators(self):
        # 엔벨로프 상/하단 채널
        self.df['Ch_Upper'] = self.df['ma_20'] * (1 + self.envelope_pct)
        self.df['Ch_Lower'] = self.df['ma_20'] * (1 - self.envelope_pct)

    def generate_signals(self):
        self.add_indicators()
        self.df['Signal'] = 0.0

        for i in self.df.index:
            close   = self.df.loc[i, 'close_price']
            ch_upper = self.df.loc[i, 'Ch_Upper']
            ch_lower = self.df.loc[i, 'Ch_Lower']

            if pd.isna(ch_upper) or pd.isna(ch_lower):
                continue

            # 우선순위 1: 손절 — 채널 하단보다 3% 더 밀릴 때
            if close < ch_lower * 0.97:
                self.df.loc[i, 'Signal'] = -2.0

            # 우선순위 2: 익절 — 채널 상단 도달
            elif close > ch_upper:
                self.df.loc[i, 'Signal'] = -1.0

            # 우선순위 3: 매수 — 채널 하단 이탈
            elif close < ch_lower:
                self.df.loc[i, 'Signal'] = 1.0

        self.df = self.df.dropna(subset=['ma_20'])
        return self.df