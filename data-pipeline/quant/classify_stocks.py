import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
    
    print(f"   → 지표 데이터: {len(metrics_df)}개 종목")
    return metrics_df

# 2. price_histories 에서 추가 지표 계산
def calc_price_features():
    print("🧮 [2/4] 추가 지표 계산 중 (이동평균, ATR, 거래량 급증)...")

    ti_query = """
    SELECT ti.stock_id, ti.ma_20, ti.ma_60, ti.atr_14, ti.vol_ma_20,
        ph.close_price, ph.high_price, ph.low_price, ph.volume, ph.date
    FROM technical_indicators ti
    JOIN price_histories ph ON ti.stock_id = ph.stock_id AND ti.date = ph.date
    WHERE ti.date >= DATE_SUB(CURDATE(), INTERVAL 120 DAY)
    ORDER BY ti.stock_id, ti.date
    """
    ti_df = pd.read_sql(ti_query, engine)
    
    results = []
    
    for stock_id, grp in ti_df.groupby('stock_id'):
        grp = grp.sort_values('date').reset_index(drop=True)
        
        if len(grp) < 20:
            continue
        
        close = grp['close_price']
        vol = grp['volume']
        ma20 = grp['ma_20']
        ma60 = grp['ma_60']
        atr_14 = grp['atr_14']
        vol_ma20 = grp['vol_ma_20']
        
        # 60일 이평 위에 있는 날 비율
        valid_ma60 = ma60.dropna()
        if len(valid_ma60) > 0:
            above_ma60_ratio = (close[-len(valid_ma60):] > valid_ma60).mean()
        else:
            above_ma60_ratio = 0.5
        
        # 3. 20일 이평 위에 있는 날 비율
        above_ma20 = (close > ma20).dropna()
        above_ma20_ratio = above_ma20.mean() if len(above_ma20) > 0 else 0.5
        
        # 4. 20일 이평 교차 횟수
        above_flag = (close > ma20).astype(int)
        cross_count = above_flag.diff().abs().sum()
        
        # 5. ATR 비율
        last_atr = atr_14.dropna().iloc[-1] if grp['atr_14'].notna().any() else 0
        last_close = close.iloc[-1]
        atr_ratio = (last_atr / last_close) if last_close > 0 else 0
        
        # 6. 거래량 급증 빈도
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

# 3. 5가지 유형별 점수 계산

class StockScorer:
    """
    순차 규칙 기반 분류 (스코어링 X)
    우선순위: 변동성돌파형 → 모멘텀형 → 추세추종형 → LOW_VOLATILITY → 평균회귀형
    가장 강한 특징을 가진 유형으로 먼저 분류하고, 해당 안되면 다음으로 넘어감
    """
    def classify_one(self, row):

        vol   = row['annual_volatility'] if pd.notna(row['annual_volatility']) else 0
        atr   = row['atr_ratio']
        ret30 = row['cum_return_30d'] if pd.notna(row['cum_return_30d']) else 0
        ret90 = row['cum_return_90d'] if pd.notna(row['cum_return_90d']) else 0
        spike = row['volume_spike_freq']
        ma60  = row['above_ma60_ratio']
        cross = row['cross_ma20_freq']

        # 1순위: 변동성돌파형
        if vol >= 0.8 and atr >= 0.07:
            score = vol + atr * 10
            return 'VOLATILITY_BREAKOUT', round(score, 2)

        # 2순위: 모멘텀형
        if ret30 >= 0.10 and spike >= 2:
            score = ret30 * 10 + spike
            return 'MOMENTUM', round(score, 2)

        # 3순위: 추세추종형
        if ma60 >= 0.60 and ret90 > 0:
            score = ma60 * 10 + ret90 * 5
            return 'TREND_FOLLOWING', round(score, 2)

        # 4순위: 저변동성 채널형
        if vol <= 0.25 and cross >= 3 and 0.40 <= ma60 <= 0.60:
            score = cross + (1 - vol) * 5
            return 'LOW_VOLATILITY', round(score, 2)
        
        # 5순위: 평균회귀형 - 변동성 낮고 이평 교차 빈번한 종목만
        if vol <= 0.30 and cross >= 2:
            score = cross + (1 - vol) * 5
            return 'MEAN_REVERSION', round(score, 2)

        # 위 조건 모두 해당 안되면 미분류
        return 'UNCLASSIFIED', 0.0

    def calculate_all_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """전체 종목 분류"""
        results = df.apply(self.classify_one, axis=1)

        df['strategy_type'] = results.apply(lambda x: x[0])
        df['score']         = results.apply(lambda x: x[1])

        return df
    
# 4. 최고 점수 유형 확정 + DB 저장
def classify_and_save(df: pd.DataFrame):
    print("💾 [3/4] 최종 분류 후 stock_classification 테이블 저장 중...")

    # strategy_type, score가 이미 calculate_all_scores에서 채워져 있음
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
        bar   = '█' * int(ratio / 3)
        print(f"  {strategy:<25} {count:>5}개  {ratio:>5.1f}%  {bar}")
    print(f"  {'합계':<25} {len(df):>5}개")
    print("=" * 55)

    # ✅ UNCLASSIFIED 제외하고 편중 여부 판단
    classified = counts.drop('UNCLASSIFIED', errors='ignore')
    unclassified_cnt = counts.get('UNCLASSIFIED', 0)
    unclassified_ratio = unclassified_cnt / len(df) * 100

    # 미분류 비율 경고
    if unclassified_ratio > 20:
        print(f"\n⚠️  미분류 종목이 {unclassified_ratio:.1f}%야. 새 전략 추가를 고려해봐.")

    # 분류된 종목 중 편중 여부
    if len(classified) > 0:
        max_ratio = classified.max() / len(df) * 100
        if max_ratio > 40:
            top_type = classified.idxmax()
            print(f"\n⚠️  '{top_type}' 유형이 {max_ratio:.1f}%로 편중되어 있어!")
        else:
            print("\n✅ 유형 분포가 균형적이야!")
        
def main():
    print(f"🚀 종목 전략 유형 분류 시작 [{datetime.now().strftime('%Y-%m-%d %H:%M')}]\n")
    
    # 1. 데이터 로드
    metrics_df = load_and_prepare()
    
    # 2. 가격 데이터로 추가 지표 계산
    features_df = calc_price_features()
    
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