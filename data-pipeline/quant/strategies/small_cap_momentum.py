import pandas as pd
from .base_strategy import BaseStrategy

# 중소형 모멘텀형(MOMENTUM) / 변동성돌파형(VOLATILITY_BREAKOUT) 종목에 적용하는 전략
# 20일선 위에서 10일 전고점 돌파 + 거래량 폭발 시 매수
class SmallCapMomentumStrategy(BaseStrategy):
    def __init__(self, df, breakout_window=10, vol_multiplier=2.0, ma_fast=5, ma_slow=20):
        super().__init__(df)
        self.breakout_window = breakout_window
        self.vol_multiplier = vol_multiplier
        self.ma_fast = ma_fast
        self.ma_slow = ma_slow

    def add_indicators(self):
        # 1.  이동평균선
        self.df['MA_Fast'] = self.df['close_price'].rolling(self.ma_fast).mean()
        self.df['MA_Slow'] = self.df['close_price'].rolling(self.ma_slow).mean()
        # 2. 최근 10일 단기 전고점
        self.df['Recent_High'] = self.df['high_price'].rolling(self.breakout_window).max().shift(1)
        # 3. 거래량 필터
        self.df['Vol_MA20'] = self.df['volume'].rolling(20).mean().shift(1)

        # 변동성 계산
        high_low = self.df['high_price'] - self.df['low_price']
        high_close = (self.df['high_price'] - self.df['close_price'].shift()).abs()
        low_close = (self.df['low_price'] - self.df['close_price'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        self.df['ATR'] = tr.rolling(window=14).mean()
        # 동적 익절 라인 설정
        self.df['Dynamic_Target'] = self.df['MA_Fast'] + (self.df['ATR'] * 2.5)


    def generate_signals(self):
        self.add_indicators()
        self.df['Signal'] = 0.0

        # 조건 1. 매수
        # 주가가 20일 선 위에서 놀고 있으며 & 오늘 종가가 10일 전고점을 뚫었고 & 오늘 거래량이 20일 평균 대비 N배 터짐
        buy_cond = ((self.df['close_price'] > self.df['MA_Slow']) &
                        (self.df['close_price'] > self.df['Recent_High']) &
                        (self.df['volume'] > (self.df['Vol_MA20'] * self.vol_multiplier))
                        )
        self.df.loc[buy_cond, 'Signal'] = 1.0

        # --- 조건 2. 익절/청산 ---
        # 1) 5일선 붕괴
        self.df.loc[self.df['close_price'] < self.df['MA_Fast'], 'Signal'] = -1.0
        # 2) 이격도 과열
        self.df.loc[self.df['close_price'] > self.df['Dynamic_Target'], 'Signal'] = -1.0
        # 3) 고점 대비 거래량 폭발 음봉
        cond_dump = (
            (self.df['close_price'] < self.df['open_price']) &
            (self.df['volume'] > self.df['Vol_MA20'] * 5)
        )
        self.df.loc[cond_dump, 'Signal'] = -2.0

        self.df = self.df.dropna()
        return self.df