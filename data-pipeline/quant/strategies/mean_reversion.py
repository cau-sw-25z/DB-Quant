from .base_strategy import BaseStrategy

# 대형 가치주 / 평균회귀형(MEAN_REVERSION) 종목에 적용하는 전략
# 볼린저 밴드 + RSI 조합으로 과매도 구간에서 매수, 밴드 상단에서 매도
class MeanReversionStrategy(BaseStrategy):
    def __init__(self, df, bb_window=20, bb_std=2.0, rsi_window=14):
        super().__init__(df)
        self.bb_window = bb_window
        self.bb_std = bb_std
        self.rsi_window = rsi_window

    def add_indicators(self):
        # 1. 볼린저 밴드 계산
        self.df['MA20'] = self.df['close_price'].rolling(self.bb_window).mean()
        self.df['STD'] = self.df['close_price'].rolling(self.bb_window).std()
        self.df['Upper'] = self.df['MA20'] + (self.df['STD'] * self.bb_std)
        self.df['Lower'] = self.df['MA20'] - (self.df['STD'] * self.bb_std)

        # 2. RSI 계산 (단순 이동평균 방식)
        delta = self.df['close_price'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=self.rsi_window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_window).mean()
        rs = gain / loss
        self.df['RSI'] = 100 - (100 / (1 + rs))

    def generate_signals(self):
        self.add_indicators()
        self.df['Signal'] = 0.0

        # 조건 1. 매수: 주가가 하단 밴드르 뚫고 내려가며 RSI가 30 이하(과매도)일 때
        self.df.loc[(self.df['close_price'] < self.df['Lower']) & (self.df['RSI'] < 40),'Signal'] = 1.0

        # 조건 2. 1차 분할 매도: 주가가 중심선(MA20)을 회복했을 때 (-0.5 시그널)
        self.df.loc[self.df['close_price'] > self.df['MA20'], 'Signal'] = -0.5

        # 조건 3. 2차 전량 익절: 상단 밴드(Upper)를 터치했을 때 (-1 시그널)
        self.df.loc[self.df['close_price'] > self.df['Upper'], 'Signal'] = -1.0

        # 조건 4. 손절: 주가가 하단 밴드보다 5% 이상 더 폭락할 때 (-2 시그널)
        self.df.loc[self.df['close_price'] < (self.df['Lower'] * 0.95), 'Signal'] = -2.0

        self.df = self.df.dropna()
        return self.df