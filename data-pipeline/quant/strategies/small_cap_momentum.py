import pandas as pd
from .base_strategy import BaseStrategy

# 중소형 모멘텀형(MOMENTUM) / 변동성돌파형(VOLATILITY_BREAKOUT) 종목에 적용하는 전략
# 20일선 위에서 10일 전고점 돌파 + 거래량 폭발 시 매수
class SmallCapMomentumStrategy(BaseStrategy):
    def __init__(self, df, breakout_window=10, vol_multiplier=2.0, atr_multiplier=2.0):
        super().__init__(df)
        self.breakout_window = breakout_window
        self.vol_multiplier  = vol_multiplier
        self.atr_multiplier = atr_multiplier

    def add_indicators(self):
        # 최근 10일 단기 전고점
        self.df['Recent_High'] = self.df['high_price'].rolling(self.breakout_window).max().shift(1)
        # 동적 익절 라인
        self.df['Dynamic_Target'] = self.df['ma_5'] + (self.df['atr_14'] * 2.5)
        # ATR 손절선
        self.df['ATR_Stop'] = self.df['ma_5'] - (self.df['atr_14'] * self.atr_multiplier)

    def generate_signals(self):
        self.add_indicators()
        self.df['Signal'] = 0.0

        for i in self.df.index:
            close = self.df.loc[i, 'close_price']
            open_price = self.df.loc[i, 'open_price']
            ma_5 = self.df.loc[i, 'ma_5']
            ma_20 = self.df.loc[i, 'ma_20']
            vol = self.df.loc[i, 'volume']
            vol_ma_20 = self.df.loc[i, 'vol_ma_20']
            rec_high = self.df.loc[i, 'Recent_High']
            dyn_target = self.df.loc[i, 'Dynamic_Target']
            atr_stop = self.df.loc[i, 'ATR_Stop']
            atr = self.df.loc[i, 'atr_14']
            
            if pd.isna(ma_5) or pd.isna(ma_20) or pd.isna(vol_ma_20) or pd.isna(rec_high):
                continue

            # 우선순위 1: 긴급 손절 
            if not pd.isna(atr) and not pd.isna(atr_stop):
                if close < atr_stop:
                    self.df.loc[i, 'Signal'] = -2.0
            else:
                if close < ma_5:
                    self.df.loc[i, 'Signal'] = -2.0
            
            if self.df.loc[i, 'Signal'] == -2.0:
                continue

            # 우선순위 2: 과열 익절 — 동적 목표가 초과
            elif not pd.isna(dyn_target) and close > dyn_target:
                self.df.loc[i, 'Signal'] = -1.5

            # 우선순위 3: 기본 청산 — 5일선 붕괴
            elif close < ma_5:
                self.df.loc[i, 'Signal'] = -1.0

            # 우선순위 4: 매수 — 20일선 위 + 10일 전고점 돌파 + 거래량 폭발
            elif(
                close > ma_20
                and close > rec_high 
                and vol > vol_ma_20 * self.vol_multiplier
            ):
                self.df.loc[i, 'Signal'] = 1.0

        self.df = self.df.dropna(subset=['ma_5', 'ma_20', 'atr_14', 'vol_ma_20', 'Recent_High'])
        return self.df