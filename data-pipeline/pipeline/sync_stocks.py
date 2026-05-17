import FinanceDataReader as fdr
from sqlalchemy import create_engine, text
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_URL

engine = create_engine(DB_URL)

def sync_krx_stocks():
    print("📈 한국 거래소(KRX) 전체 종목 리스트를 가져오는 중...")

    krx_df = fdr.StockListing('KRX')

    stocks_df = krx_df[['Code', 'Name', 'Market']].rename(columns={
        'Code': 'ticker',
        'Name': 'name',
        'Market': 'market'
    })
    
    insert_query = text("""
                        INSERT IGNORE INTO stocks (ticker, name, market)
                        VALUES (:ticker, :name, :market)
                        """)
    
    new_count = 0
    
    with engine.begin() as conn:
        for _, row in stocks_df.iterrows():
            result = conn.execute(insert_query, {
                'ticker': row['ticker'],
                'name': row['name'],
                'market': row['market']
            })
            if result.rowcount == 1:
                new_count += 1
                
    total = len(stocks_df)
    skipped = total - new_count
    print(f"✅ 처리 완료!")
    print(f"   → 전체 KRX 종목: {total}개")
    print(f"   → 신규 추가:     {new_count}개")
    print(f"   → 이미 존재(스킵): {skipped}개")
    
if __name__ == "__main__":
    sync_krx_stocks()