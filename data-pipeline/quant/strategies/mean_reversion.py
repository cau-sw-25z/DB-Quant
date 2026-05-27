from .base_strategy import BaseStrategy

# 대형 가치주 / 평균회귀형(MEAN_REVERSION) 종목에 적용하는 전략
# 볼린저 밴드 + RSI 조합으로 과매도 구간에서 매수, 밴드 상단에서 매도
class MeanReversionStrategy(BaseStrategy):
    def __init__(self, df):
        super().__init__(df)
        
    def add_indicators(self):
        pass

    def generate_signals(self):
        self.df['Signal'] = 0.0

        # 조건 1. 매수: 주가가 하단 밴드르 뚫고 내려가며 RSI가 30 이하(과매도)일 때
        self.df.loc[(self.df['close_price'] < self.df['bb_lower']) & (self.df['rsi_14'] < 40),'Signal'] = 1.0

        # 조건 2. 1차 분할 매도: 주가가 중심선(MA20)을 회복했을 때 (-0.5 시그널)
        self.df.loc[self.df['close_price'] > self.df['ma_20'], 'Signal'] = -0.5

        # 조건 3. 2차 전량 익절: 상단 밴드(Upper)를 터치했을 때 (-1 시그널)
        self.df.loc[self.df['close_price'] > self.df['bb_upper'], 'Signal'] = -1.0

        # 조건 4. 손절: 주가가 하단 밴드보다 5% 이상 더 폭락할 때 (-2 시그널)
        self.df.loc[self.df['close_price'] < (self.df['bb_lower'] * 0.95), 'Signal'] = -2.0

        self.df = self.df.dropna(subset=['ma_20', 'bb_upper', 'bb_lower', 'rsi_14'])
        return self.df