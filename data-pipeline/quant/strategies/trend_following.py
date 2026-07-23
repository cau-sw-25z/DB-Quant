import pandas as pd
from .base_strategy import BaseStrategy


class TrendFollowingStrategy(BaseStrategy):
    def __init__(self, df, breakout_window=20, atr_multiplier=1.5):
        super().__init__(df)
        self.breakout_window = breakout_window
        self.atr_multiplier = atr_multiplier

    def generate_signals(self):
        self.add_indicators()
        self.df['Signal'] = 0.0

        for i in self.df.index:
            close    = self.df.loc[i, 'close_price']
            ma_20    = self.df.loc[i, 'ma_20']
            ma_60    = self.df.loc[i, 'ma_60']
            rec_high = self.df.loc[i, 'Recent_High']
            overheat = self.df.loc[i, 'Overheat_Line']
            adx      = self.df.loc[i, 'adx_14']
            vol      = self.df.loc[i, 'volume']
            vol_ma   = self.df.loc[i, 'vol_ma_20']
            atr      = self.df.loc[i, 'atr_14']
            atr_stop = self.df.loc[i, 'ATR_Stop']

            if pd.isna(ma_20) or pd.isna(ma_60) or pd.isna(rec_high):
                continue

            # 우선순위 1: 긴급 손절
            if not pd.isna(atr) and not pd.isna(atr_stop):
                if close < atr_stop:
                    self.df.loc[i, 'Signal'] = -2.0
            else:
                if close < ma_60:
                    self.df.loc[i, 'Signal'] = -2.0

            if self.df.loc[i, 'Signal'] == -2.0:
                continue

            # 우선순위 2: 기본 청산 — ma_20 붕괴 (원복)
            if close < ma_20:
                self.df.loc[i, 'Signal'] = -1.0

            # 우선순위 3: 부분 익절 — 이격도 과열
            elif close > overheat:
                self.df.loc[i, 'Signal'] = -0.5

            # 우선순위 4: 매수
            elif (
                close > ma_60
                and ma_20 > ma_60
                and close > rec_high
                and not pd.isna(adx) and adx >= 25
                and not pd.isna(vol_ma) and vol > vol_ma * 1.5
            ):
                self.df.loc[i, 'Signal'] = 1.0

        self.df = self.df.dropna(subset=['ma_20', 'ma_60', 'Recent_High'])
        return self.df