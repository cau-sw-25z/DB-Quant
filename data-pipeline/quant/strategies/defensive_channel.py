from .base_strategy import BaseStrategy

# 저변동성 방어주 종목에 적용하는 전략
# MA20 기준 ±envelope_pct% 채널 하단 이탈 시 매수, 상단 도달 시 매도
class DefensiveChannelStrategy(BaseStrategy):
    def __init__(self, df, ma_window=20, envelope_pct=0.05):
        super().__init__(df)
        self.ma_window = ma_window
        self.envelope_pct = envelope_pct

    def add_indicators(self):
        # 1. 중심선
        self.df['MA20'] = self.df['close_price'].rolling(self.ma_window).mean()
        # 2. 엔벨로프 상/하단 채널
        self.df['Ch_Upper'] = self.df['MA20'] * (1 + self.envelope_pct)
        self.df['Ch_Lower'] = self.df['MA20'] * (1 - self.envelope_pct)

    def generate_signals(self):
        self.add_indicators()
        self.df['Signal'] = 0.0

        # 조건 1. 매수: 주가가 채널 하단선보다 낮아질 때
        self.df.loc[self.df['close_price'] < self.df['Ch_Lower'], 'Signal'] = 1.0
        # 조건 2. 익절: 주가가 채널 상단선에 도달할 때
        self.df.loc[self.df['close_price'] > self.df['Ch_Upper'], 'Signal'] = -1.0
        # 조건 3. 손절: 주가가 하단선보다 3% 더 밀릴 때
        self.df.loc[self.df['close_price'] < self.df['Ch_Lower'] * 0.97, 'Signal'] = -2.0

        self.df = self.df.dropna()
        return self.df