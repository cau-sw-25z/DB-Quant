import FinanceDataReader as fdr
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime
import time

DB_URL = "mysql+pymysql://quant_user:0615@localhost:3306/quant_db?charset=utf8mb4"
engine = create_engine(DB_URL)

def fetch_and_insert_data(start_date="2024-01-01"):
    print(f"[{datetime.now()}] 전체 주식 데이터 수집 파이프라인 가동...")

    target_stocks_df = pd.read_sql("SELECT id, ticker, name FROM stocks", con=engine)
    total_count = len(target_stocks_df)

    all_data = []

    for index, row in target_stocks_df.iterrows():
        stock_id = row['id']
        ticker = row['ticker']
        name = row['name']

        try:
            print(f"[{index + 1}/{total_count}] 데이터 수집 중: {name} ({ticker})")
            df = fdr.DataReader(ticker, start_date)

            if df.empty:
                continue

            df = df.reset_index()

            df = df.rename(columns={
                'Date': 'date',
                'Open': 'open_price',
                'High': 'high_price',
                'Low': 'low_price',
                'Close': 'close_price',
                'Volume': 'volume',
            })

            df['stock_id'] = stock_id

            df_columns = ['date', 'open_price', 'high_price', 'low_price', 'close_price', 'volume', 'stock_id']
            df = df[df_columns]

            all_data.append(df)

        except Exception as e:
            print(f"⚠️ {name}({ticker}) 수집 실패: {e}")

        time.sleep(0.2)

        if len(all_data) >= 100:
            batch_df = pd.concat(all_data, ignore_index=True)
            batch_df.to_sql(name='price_histories', con=engine, if_exists='append', index=False)
            all_data = []
            print("--- 100개 종목 데이터 DB 중간 적재 완료 ---")

    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        final_df.to_sql('price_histories', con=engine, if_exists='append', index=False)

if __name__ == "__main__":
    fetch_and_insert_data()
