import FinanceDataReader as fdr
from sqlalchemy import create_engine
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

    try:
        stocks_df.to_sql(name='stocks', con=engine, if_exists='append', index=False)
        print(f"✅ 총 {len(stocks_df)}개의 대한민국 상장 주식 종목이 DB에 등록되었습니다!")
    except Exception as e:
        print(f"❌ DB 저장 중 에러 발생: {e}")

if __name__ == "__main__":
    sync_krx_stocks()