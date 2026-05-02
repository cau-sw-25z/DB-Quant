import pandas as pd
from sqlalchemy import create_engine

DB_URL = "mysql+pymysql://quant_user:0615@localhost:3306/quant_db?charset=utf8mb4"
engine = create_engine(DB_URL)

def validate_data():
    print("🔍 [1/3] 데이터 정합성 검증 시작...\n")
    
    # 1. NULL 값 검사
    null_query = """
    SELECT COUNT(*) as cnt
    FROM price_histories
    WHERE open_price IS NULL OR close_price IS NULL 
        OR high_price IS NULL OR low_price IS NULL OR date IS NULL;
    """
    null_cnt = pd.read_sql(null_query, engine).iloc[0]['cnt']
    print(f"✔️ NULL 값 검사: {'✅ 통과 (0건)' if null_cnt == 0 else f'❌ 실패 ({null_cnt}건 발견)'}")
    
    # 2. 이상치 검사 (고가 < 저가 이거나, 종가가 0 이하인 경우)
    anomaly_query = """
    SELECT COUNT(*) as cnt
    FROM price_histories
    WHERE high_price < low_price OR close_price <= 0;
    """
    anomaly_cnt = pd.read_sql(anomaly_query, engine).iloc[0]['cnt']
    print(f"✔️ 이상치 검사(고가<저가, 종가<=0): {'✅ 통과 (0건)' if anomaly_cnt == 0 else f'❌ 실패 ({anomaly_cnt}건 발견)'}")

    # 3. 거래량 0 검사
    vol_zero_query = """
    SELECT COUNT(*) as cnt
    FROM price_histories
    WHERE volume = 0;
    """
    vol_zero_cnt = pd.read_sql(vol_zero_query, engine).iloc[0]['cnt']
    print(f"✔️ 거래량 0 검사 (거래정지 등): {vol_zero_cnt}건 발견 (참고사항)")
    
    # 4. 종목별 데이터 적재 현황 (상위 5개)
    print("\n📊 [2/3] 주요 종목별 데이터 적재 현황 (TOP 5)")
    count_query = """
    SELECT s.name as '종목명', COUNT(p.date) as '영업일_데이터수'
    FROM stocks s
    JOIN price_histories p ON s.id = p.stock_id
    GROUP BY s.id, s.name
    ORDER BY '영업일_데이터수' DESC
    LIMIT 5;
    """
    count_df = pd.read_sql(count_query, engine)
    print(count_df.to_string(index=False))
    
def extract_sample_for_notion():
    print("\n📝 [3/3] 팀 공유용 샘플 데이터 추출 (삼성전자 최근 5일)...")
    sample_query = """
    SELECT date as '날짜', open_price as '시가', high_price as '고가', low_price as '저가', close_price as '종가', volume as '거래량'
    FROM price_histories
    WHERE stock_id = (SELECT id FROM stocks WHERE name = '삼성전자')
    ORDER BY date DESC
    LIMIT 5;
    """
    sample_df = pd.read_sql(sample_query, engine)
    print("\n" + sample_df.to_markdown(index=False))

if __name__ == "__main__":
    validate_data()
    extract_sample_for_notion()