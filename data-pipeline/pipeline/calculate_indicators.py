import pandas as pd
import pandas_ta as ta
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.mysql import insert
from datetime import date, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_URL


engine = create_engine(DB_URL)

def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    종목 하나의 가격 DataFrame을 받아서
    MA / RSI / MACD / 볼린저밴드를 계산해서 돌려주는 함수.
    """
    close = df['close_price']
    high = df['high_price']
    low = df['low_price']
    vol = df['volume']
    n = len(close)

    # 이동평균(MA)
    df['ma_5'] = ta.sma(close, length=5)
    df['ma_20'] = ta.sma(close, length=20)
    df['ma_60'] = ta.sma(close, length=60)
    df['ma_120'] = ta.sma(close, length=120)

    # RSI(14일 기준)
    if n >= 15:
        df['rsi_14'] = ta.rsi(close, length=14)
    else:
        df['rsi_14'] = None
    df['rsi_overbought'] = (df['rsi_14'] >= 70).fillna(False)
    df['rsi_oversold']   = (df['rsi_14'] <= 30).fillna(False)
    
    # MACD
    if n >= 35:
        macd_df = ta.macd(close, fast=12, slow=26, signal=9)
        df['macd']        = macd_df['MACD_12_26_9']
        df['macd_signal'] = macd_df['MACDs_12_26_9']
        df['macd_hist']   = macd_df['MACDh_12_26_9']
    else:
        df['macd'] = df['macd_signal'] = df['macd_hist'] = None
    
    # 볼린저밴드 (20일 기준)
    if n >= 20:
        bbands_df = ta.bbands(close, length=20, std=2)
        if bbands_df is not None:
            df['bb_lower'] = bbands_df['BBL_20_2.0_2.0']
            df['bb_mid']   = bbands_df['BBM_20_2.0_2.0']
            df['bb_upper'] = bbands_df['BBU_20_2.0_2.0']
            df['bb_width'] = bbands_df['BBB_20_2.0_2.0']
            df['bb_pct_b'] = bbands_df['BBP_20_2.0_2.0']
        else:
            df['bb_lower'] = df['bb_mid'] = df['bb_upper'] = None
            df['bb_width'] = df['bb_pct_b'] = None
    else:
        df['bb_lower'] = df['bb_mid'] = df['bb_upper'] = None
        df['bb_width'] = df['bb_pct_b'] = None
        
    if n >= 15:
        high_low = high - low
        high_close = (high - close.shift()).abs()
        low_close = (low - close.shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr_14'] = tr.rolling(window=14).mean()
    else:
        df['atr_14'] = None
        
    df['vol_ma_20'] = vol.rolling(window=20).mean().shift(1)

    return df

def _insert_ignore(table, conn, keys, data_iter):
    rows = [dict(zip(keys, row)) for row in data_iter]
    stmt = insert(table.table).prefix_with("IGNORE")
    conn.execute(stmt, rows)

def _process_ticker(stock_id: int, ticker: str, target_date: date = None):
    """
    종목 하나의 지표를 계산하고 technical_indicators 테이블에 저장.
    target_date 있으면 → 해당 날짜만 저장 (일배치용)
    target_date 없으면 → 전 기간 저장 (초기 1회용)
    """
    query = text("""
                SELECT date, open_price, high_price, low_price, close_price, volume
                FROM price_histories
                WHERE stock_id = :stock_id
                ORDER BY date ASC
                """)
    
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"stock_id": stock_id})
        
    if df.empty:
        print(f"   [{ticker}] 주가 데이터 없음 - 건너뜀")
        return
    
    df = calculate_all_indicators(df)
    
    df['stock_id'] = stock_id
    
    cols = [
        'stock_id', 'date',
        'ma_5', 'ma_20', 'ma_60', 'ma_120',
        'rsi_14', 'rsi_overbought', 'rsi_oversold',
        'macd', 'macd_signal', 'macd_hist',
        'bb_upper', 'bb_mid', 'bb_lower', 'bb_width', 'bb_pct_b',
        'atr_14', 'vol_ma_20',
    ]
    result_df = df[cols]
    
    if target_date is not None:
        result_df = result_df[result_df['date'].astype(str) == str(target_date)]
        if result_df.empty:
            print(f"   [{ticker}] {target_date} 데이터 없음 (휴장일?)")
            return
        
    result_df.to_sql(
        name='technical_indicators',
        con=engine,
        if_exists='append',
        index=False,
        method=_insert_ignore
    )
    
def run_full_batch():
    """
    전 종목 전 기간 기술지표를 한 번에 계산해서 DB에 저장.
    실행 전에 technical_indicators 테이블이 비어 있어야 함.
    """
    print("🚀 전 종목 전 기간 기술지표 계산 시작...")
    
    stocks_df = pd.read_sql(
        "SELECT id, ticker, name FROM stocks ORDER BY ticker",
        engine
    )
    total = len(stocks_df)
    print(f"   → 총 {total}개 종목 처리 예정")

    for i, row in stocks_df.iterrows():
        try:
            _process_ticker(row['id'], row['ticker'])
            print(f"   [{i+1}/{total}] {row['name']}({row['ticker']}) 완료")
        except Exception as e:
            # 한 종목 실패해도 다음 종목은 계속 진행
            print(f"   ⚠️ [{row['ticker']}] 실패: {e}")
            continue

    print("✅ 전 종목 처리 완료!")
    
def run_daily_batch(target_date: date = None):
    """
    당일(또는 지정일) 데이터만 계산해서 추가.
    """
    if target_date is None:
        target_date = date.today()
        
    print(f"🔄 [{target_date}] 일배치 기술지표 계산 시작...")
    
    with engine.connect() as conn:
        result = conn.execute(text("SELECT MAX(date) FROM technical_indicators"))
        last_date = result.fetchone()[0]
        
    start = last_date + timedelta(days=1)
    end = target_date

    current = start
    while current <= end:
        print(f"   📅 {current} 계산 중...")
        stocks_df = pd.read_sql(
            "SELECT id, ticker FROM stocks ORDER BY ticker",
            engine
        )
        for _, row in stocks_df.iterrows():
            try:
                _process_ticker(row['id'], row['ticker'], target_date=current)
            except Exception as e:
                print(f"   ⚠️ [{row['ticker']}] 일배치 실패: {e}")
                continue
        print(f"   ✅ {current} 완료!")
        current += timedelta(days=1)

    print(f"✅ 전체 일배치 완료! ({start} ~ {end})")
    
    
def validate_indicators():
    print("\n🔍 적재 결과 검증...")
    
    query = """
    SELECT
        COUNT(*) AS total_rows,
        ROUND(100.0 * SUM(CASE WHEN ma_5   IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS ma5_null_pct,
        ROUND(100.0 * SUM(CASE WHEN ma_120 IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS ma120_null_pct,
        ROUND(100.0 * SUM(CASE WHEN rsi_14 IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS rsi_null_pct,
        ROUND(100.0 * SUM(CASE WHEN macd   IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS macd_null_pct,
        ROUND(100.0 * SUM(CASE WHEN bb_upper IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS bb_null_pct,
        ROUND(100.0 * SUM(CASE WHEN atr_14 IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS atr_null_pct,
        ROUND(100.0 * SUM(CASE WHEN vol_ma_20 IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS vol_ma_null_pct
    FROM technical_indicators
    """
    result = pd.read_sql(query, engine)
    print(result.to_string(index=False))
    
if __name__ == "__main__":
    run_full_batch()
    validate_indicators()