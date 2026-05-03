import pandas as pd
import numpy as np
from sqlalchemy import create_engine

DB_URL = "mysql+pymysql://quant_user:0615@localhost:3306/quant_db?charset=utf8mb4"
engine = create_engine(DB_URL)

def calculate_metrics():
    print("📊 [1/4] 데이터베이스에서 주가 데이터 불러오는 중...")
    
    query = """
    SELECT p.stock_id, s.ticker, s.name, p.date, p.close_price
    FROM price_histories p
    JOIN stocks s ON p.stock_id = s.id
    ORDER BY p.stock_id, p.date
    """
    df = pd.read_sql(query, engine)

    print("🧮 [2/4] 수익률 및 변동성 지표 계산 중 (약 10~30초 소요)...")
    df = df.sort_values(by=['stock_id', 'date']).reset_index(drop=True)

    grouped = df.groupby('stock_id')['close_price']

    # 1. 수익률 계산 (pct_change 활용)
    df['daily_return'] = grouped.pct_change(periods=1)
    df['cum_return_30d'] = grouped.pct_change(periods=30)
    df['cum_return_90d'] = grouped.pct_change(periods=90)
    df['cum_return_1y'] = grouped.pct_change(periods=252)

    # 2. 연간화 변동성 계산 (최근 1년=252일 기준)
    df['annual_volatility'] = df.groupby('stock_id')['daily_return'] \
                                .rolling(window=252).std() \
                                .reset_index(level=0, drop=True) * np.sqrt(252)

    # 3. 샤프 지수 계산 (연평균 수익률 - 무위험수익률 / 연간화 변동성)
    # 연평균 수익률 = 최근 252일 일별 수익률의 평균 * 252
    annual_return = df.groupby('stock_id')['daily_return'] \
                      .rolling(window=252).mean() \
                      .reset_index(level=0, drop=True) * 252
                      
    risk_free_rate = 0.035
    df['sharpe_ratio'] = (annual_return - risk_free_rate) / df['annual_volatility']

    df = df.replace([np.inf, -np.inf], np.nan)

    print("💾 [3/4] 계산 결과를 stock_metrics 테이블에 저장 중...")
    result_df = df[['stock_id', 'ticker', 'date', 'daily_return', 
                    'cum_return_30d', 'cum_return_90d', 'cum_return_1y', 
                    'annual_volatility', 'sharpe_ratio']]

    # DB 적재
    result_df.to_sql(name='stock_metrics', con=engine, if_exists='replace', index=False)
    print("✅ 적재 완료!\n")

    print("📈 [4/4] 계산 결과 검증 및 통계 요약")
    
    null_counts = result_df.isnull().sum()
    print(f"[NULL 데이터 확인 (정상적인 과거 영업일 부족 데이터 포함)]\n{null_counts}\n")

    # 통계 출력
    latest_date = df['date'].max()
    latest_df = df[df['date'] == latest_date].dropna(subset=['annual_volatility'])

    print(f"🔥 [최근 영업일 기준 변동성 상위 5개 종목 (High Risk)]")
    top_vol = latest_df.sort_values('annual_volatility', ascending=False).head(5)
    print(top_vol[['name', 'annual_volatility', 'sharpe_ratio']].to_string(index=False))

    print(f"\n🛡️ [최근 영업일 기준 변동성 하위 5개 종목 (Low Risk)]")
    bot_vol = latest_df.sort_values('annual_volatility', ascending=True).head(5)
    print(bot_vol[['name', 'annual_volatility', 'sharpe_ratio']].to_string(index=False))

if __name__ == "__main__":
    calculate_metrics()