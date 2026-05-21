from .base_strategy import BaseStrategy

# 중대형 성장주 / 추세추종형(TREND_FOLLOWING) 종목에 적용하는 전략
# 60일선 위에서 20일 전고점 돌파 시 매수, 20일선 붕괴 시 매도
class TrendFollowingStrategy(BaseStrategy):
    def __init__(self, df, breakout_window=20, ma_exit=20, ma_trend=60):
        super().__init__(df)
        self.breakout_window = breakout_window
        self.ma_exit = ma_exit
        self.ma_trend = ma_trend

    def add_indicators(self):
        # 1. 이동평균선 계산
        self.df['MA_Exit'] = self.df['close_price'].rolling(self.ma_exit).mean()
        self.df['MA_Trend'] = self.df['close_price'].rolling(self.ma_trend).mean()
        # 2. 모멘텀 돌파선 계산
        self.df['Recent_High'] = self.df['high_price'].rolling(self.breakout_window).max().shift(1)
        # 3. 이격도 과열선
        self.df['Overheat_Line'] = self.df['MA_Exit'] * 1.15

    def generate_signals(self):
        self.add_indicators()
        self.df['Signal'] = 0.0

        # 매수: 60일선 위에 위치 & 당일 종가가 20일 전고점 돌파
        buy_cond = (self.df['close_price'] > self.df['MA_Trend']) & (self.df['close_price'] > self.df['Recent_High'])
        self.df.loc[buy_cond, 'Signal'] = 1.0
        # --- 매도 ---
        # 1) 기본 청산: 20일선 붕괴
        self.df.loc[self.df['close_price'] < self.df['MA_Exit'], 'Signal'] = -1.0 
        # 2) 부분 익절: 이격도 과열
        self.df.loc[self.df['close_price'] > self.df['Overheat_Line'], 'Signal'] = -0.5
        # 3) 긴급 손절: 대세 추세선 붕괴
        self.df.loc[self.df['close_price'] < self.df['MA_Trend'], 'Signal'] = -2.0
        
        self.df = self.df.dropna()
        return self.df