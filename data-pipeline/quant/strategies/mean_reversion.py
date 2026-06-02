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
        self.df = self.df.dropna(subset=['ma_20', 'bb_upper', 'bb_lower', 'rsi_14'])
        self.df = self.df.reset_index(drop=True)
        
        for i in self.df.index:
            close = self.df.loc[i, 'close_price']
            bb_upper = self.df.loc[i, 'bb_upper']
            bb_lower = self.df.loc[i, 'bb_lower']
            ma_20 = self.df.loc[i, 'ma_20']
            rsi = self.df.loc[i, 'rsi_14']
            
        # 우선순위 1: 손절 — 하단밴드 5% 이탈
        if close < bb_lower * 0.95:
            self.df.loc[i, 'Signal'] = -2.0

        # 우선순위 2: 전량 익절 — 상단밴드 터치
        elif close > bb_upper:
            self.df.loc[i, 'Signal'] = -1.0

        # 우선순위 3: 부분 익절 — MA20 회복
        elif close > ma_20:
            self.df.loc[i, 'Signal'] = -0.5

        # 우선순위 4: 매수 — 하단밴드 이탈 + 과매도
        elif close < bb_lower and rsi < 40:
            self.df.loc[i, 'Signal'] = 1.0

        return self.df