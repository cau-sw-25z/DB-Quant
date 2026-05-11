import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from datetime import datetime
from config import DB_URL

engine = create_engine(DB_URL)

# 1. 두 테이블을 합쳐서 분류에 필요한 지표 계산
def load_and_prepare():
    print("📊 [1/4] 지표 데이터 불러오는 중...")
    # stock_metrics: 수익률/변동성
    # 종목별 가장 최신 날짜 행만 가져옴
    metrics_query = """
    SELECT sm.stock_id, sm.ticker, sm.cum_return_30d, sm.cum_return_90d,
        sm.annual_volatility, sm.sharpe_ratio
    FROM stock_metrics sm
    INNER JOIN (
        SELECT stock_id, MAX(date) AS max_date
        FROM stock_metrics
        GROUP BY stock_id
    ) latest ON sm.stock_id = latest.stock_id AND sm.date = latest.max_date
    """
    metrics_df = pd.read_sql(metrics_query, engine)
    
    # price_histories: 최근 60일 고가/저가/거래량 (이동평균, ATR, 거래량 급증 계산용)
    price_query = """
    SELECT stock_id, date, close_price, high_price, low_price, volume
    FROM price_histories
    WHERE date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
    ORDER BY stock_id, date
    """
    price_df = pd.read_sql(price_query, engine)
    
    print(f"   → 지표 데이터: {len(metrics_df)}개 종목")
    print(f"   → 가격 데이터: {len(price_df)}행 (최근 90일)")
    return metrics_df, price_df

# 2. price_histories 에서 추가 지표 계산
def calc_price_features(price_df):
    print("🧮 [2/4] 추가 지표 계산 중 (이동평균, ATR, 거래량 급증)...")
    
    results = []
    
    for stock_id, grp in price_df.groupby('stock_id'):
        grp = grp.sort_values('date').reset_index(drop=True)
        
        if len(grp) < 20:
            continue
        
        close = grp['close_price']
        high = grp['high_price']
        low = grp['low_price']
        vol = grp['volume']
        
        # 1. 이동편균 계산
        ma20 = close.rolling(window=20).mean()
        ma60 = close.rolling(window=60).mean()
        
        # 2. 60일 이평 위에 있는 날 비율
        above_ma60 = (close > ma60).dropna()
        above_ma60_ratio = above_ma60.mean() if len(above_ma60) > 0 else 0.5
        
        # 3. 20일 이평 위에 있는 날 비율
        above_ma20 = (close > ma20).dropna()
        above_ma20_ratio = above_ma20.mean() if len(above_ma20) > 0 else 0.5
        
        # 4. 20일 이평 교차 횟수
        above_flag = (close > ma20).astype(int)
        cross_count = above_flag.diff().abs().sum()
        
        # 5. ATR 비율
        daily_range = high - low
        atr = daily_range.rolling(window=20).mean().iloc[-1]
        last_close = close.iloc[-1]
        atr_ratio = (atr / last_close) if last_close > 0 else 0
        
        # 6. 거래량 급증 빈도
        vol_ma20 = vol.rolling(window=20).mean()
        volume_spike = (vol > vol_ma20 * 2)
        volume_spike_freq = volume_spike.sum()
        
        results.append({
            'stock_id': stock_id,
            'above_ma60_ratio': above_ma60_ratio,
            'above_ma20_ratio': above_ma20_ratio,
            'cross_ma20_freq': int(cross_count),
            'atr_ratio': float(atr_ratio),
            'volume_spike_freq': int(volume_spike_freq)
        })
    
    return pd.DataFrame(results)

# 3. 4가지 유형별 점수 계산

class StockScorer:
    """종목별로 4가지 전략 유형 점수를 계산"""
    
    def score_trend_following(self, row, vol_low_threshold):
        """추세추종형: 장기 이평 위에 오래 있을수록, 방향성 뚜렷할수록 높은 점수"""
        score = 0.0
        
        if row['above_ma60_ratio'] >= 0.6:
            score += 2.0
            
        if row['above_ma20_ratio'] >= 0.5:
            score += 1.0
            
        if pd.notna(row['cum_return_90d']) and row['cum_return_90d'] > 0:
            score += 1.0
            
        if pd.notna(row['annual_volatility']) and row['annual_volatility'] <= vol_low_threshold:
            score += 5.0
                    
        return score
    
    def score_mean_reversion(self, row, vol_low_threshold):
        """평균회귀형: 변동성 낮고 평균 주변을 왔다갔다 할수록 높은 점수"""
        score = 0.0
        
        if pd.notna(row['annual_volatility']) and row['annual_volatility'] <= vol_low_threshold:
            score += 2.0
            
        if row['cross_ma20_freq'] >= 4:
            score += 1.5
            
        if 0.35 <= row['above_ma60_ratio'] <= 0.65:
            score += 1.0
        
        return score
    
    def score_momentum(self, row):
        """모멘텀형: 최근 수익률 높고 거래량 급증이 많을수록 높은 점수"""
        score = 0.0
        
        if pd.notna(row['cum_return_30d']) and row['cum_return_30d'] >= 0.05:
            score += 2.0
            
        if row['volume_spike_freq'] >= 3:
            score += 1.5
        
        if pd.notna(row['cum_return_90d']) and row['cum_return_90d'] > 0:
            score += 1.0
            
        return score
    
    def score_volatility_breakout(self, row, vol_high_threshold):
        """변동성돌파형: 일중 변동폭 크고 급등락 빈번할수록 높은 점수"""
        score = 0.0
        
        if pd.notna(row['annual_volatility']) and row['annual_volatility'] >= vol_high_threshold:
            score += 2.0
            
        if row['atr_ratio'] >= 0.03:
            score += 1.5
            
        if row['cross_ma20_freq'] >= 6:
            score += 1.0
            
        return score
    
    def calculate_all_scores(self, df):
        """전체 종목에 대해 4가지 점수를 한 번에 계산"""
        vol_series = df['annual_volatility'].dropna()
        vol_low = vol_series.quantile(0.33)
        vol_high = vol_series.quantile(0.67)
        
        print(f"   → 변동성 기준값: 낮음={vol_low:.4f}, 높음={vol_high:.4f}")
        df['score_trend']     = df.apply(lambda r: self.score_trend_following(r, vol_low), axis=1)
        df['score_mean_rev']  = df.apply(lambda r: self.score_mean_reversion(r, vol_low), axis=1)
        df['score_momentum']  = df.apply(lambda r: self.score_momentum(r), axis=1)
        df['score_vol_break'] = df.apply(lambda r: self.score_volatility_breakout(r, vol_high), axis=1)
        
        return df
    
# 4. 최고 점수 유형 확정 + DB 저장
def classify_and_save(df):
    print("💾 [3/4] 최종 분류 후 stock_classification 테이블 저장 중...")
    
    SCORE_TO_TYPE = {
        'score_trend': 'TREND_FOLLOWING', # 추세추종형
        'score_mean_rev': 'MEAN_REVERSION', # 평균회귀형
        'score_momentum': 'MOMENTUM', # 모멘텀형
        'score_vol_break': 'VOLATILITY_BREAKOUT' # 변동성돌파형
    }
    score_cols = list(SCORE_TO_TYPE.keys())
    
    df['strategy_type'] = df[score_cols].idxmax(axis=1).map(SCORE_TO_TYPE)
    df['score'] = df[score_cols].max(axis=1)
    df['classified_at'] = datetime.now()
    
    result_df = df[['stock_id', 'ticker', 'strategy_type', 'score', 'classified_at']]
    
    result_df.to_sql(
        name='stock_classification',
        con=engine,
        if_exists='replace',
        index=False
    )
    print(f"✅ 저장 완료: {len(result_df)}개 종목")
    return df

# 5. 편중 여부 확인
def print_summary(df):
    print("\n📈 [4/4] 유형별 종목 분포 (편중 여부 확인)")
    print("=" * 55)
    counts = df['strategy_type'].value_counts()
    for strategy, count in counts.items():
        ratio = count / len(df) * 100
        bar = '█' * int(ratio / 3)
        print(f"  {strategy:<25} {count:>5}개  {ratio:>5.1f}%  {bar}")
    print(f"  {'합계':<25} {len(df):>5}개")
    print("=" * 55)
    
    max_ratio = counts.max() / len(df) * 100
    if max_ratio > 40:
        top_type = counts.idxmax()
        print(f"\n⚠️  '{top_type}' 유형이 {max_ratio:.1f}%로 편중되어 있어!")
        print("   → 스코어링 기준값(임계값) 조정을 고려해봐.")
    else:
        print("\n✅ 유형 분포가 균형적이야! 기준값 OK.")
        
def main():
    print(f"🚀 종목 전략 유형 분류 시작 [{datetime.now().strftime('%Y-%m-%d %H:%M')}]\n")
    
    # 1. 데이터 로드
    metrics_df, price_df = load_and_prepare()
    
    # 2. 가격 데이터로 추가 지표 계산
    features_df = calc_price_features(price_df)
    
    # 3. 두 DataFrame 합치기
    df = pd.merge(metrics_df, features_df, on='stock_id', how='inner')
    print(f"   → 병합 결과: {len(df)}개 종목 분류 대상")
    
    # 4. 점수 계산
    scorer = StockScorer()
    df = scorer.calculate_all_scores(df)
    
    # 5. 분류 + 저장
    df = classify_and_save(df)
    
    # 6. 분포 출력
    print_summary(df)
    
    print(f"\n🎉 분류 완료!")
    
if __name__ == "__main__":
    main()