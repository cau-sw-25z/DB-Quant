import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_URL

engine = create_engine(DB_URL)

ADX_THRESHOLD = 25.0  # 이 값 하나만 바꾸면 전체 분류 기준 바뀜


def load_latest_adx() -> pd.DataFrame:
    """각 종목의 최신 ADX 값 로드"""
    print("📊 [1/3] 최신 ADX 데이터 불러오는 중...")

    query = text("""
        SELECT ti.stock_id, ti.adx_14
        FROM technical_indicators ti
        INNER JOIN (
            SELECT stock_id, MAX(date) AS max_date
            FROM technical_indicators
            GROUP BY stock_id
        ) latest ON ti.stock_id = latest.stock_id AND ti.date = latest.max_date
        JOIN stocks s ON ti.stock_id = s.id
        WHERE s.name NOT LIKE '%스팩%'
        AND s.name NOT LIKE '%리츠%'
        AND s.name NOT LIKE '%우'
        AND s.name NOT LIKE '%1우'
        AND s.name NOT LIKE '%2우'
        AND s.name NOT LIKE '%3우'
        AND s.name NOT LIKE '%우B'
        AND s.name NOT LIKE '%우C'
    """)

    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    print(f"   → {len(df)}개 종목 로드 완료")
    return df


def classify(df: pd.DataFrame) -> pd.DataFrame:
    """ADX 기준으로 TREND_FOLLOWING / MEAN_REVERSION / UNCLASSIFIED 분류"""
    print("🧮 [2/3] ADX 기반 분류 중...")

    def classify_one(adx):
        if pd.isna(adx):
            return 'UNCLASSIFIED', 0.0
        elif adx > ADX_THRESHOLD:
            return 'TREND_FOLLOWING', round(float(adx), 2)
        else:
            return 'MEAN_REVERSION', round(float(adx), 2)

    results = df['adx_14'].apply(classify_one)
    df['strategy_type'] = results.apply(lambda x: x[0])
    df['score'] = results.apply(lambda x: x[1])
    df['classified_at'] = datetime.now()

    return df


def save(df: pd.DataFrame):
    """stock_classification 테이블 전체 덮어쓰기"""
    print("💾 [3/3] stock_classification 테이블 저장 중...")

    result_df = df[['stock_id', 'strategy_type', 'score', 'classified_at']]
    result_df.to_sql(
        name='stock_classification',
        con=engine,
        if_exists='replace',
        index=False
    )
    print(f"✅ 저장 완료: {len(result_df)}개 종목")


def print_summary(df: pd.DataFrame):
    print("\n📈 분류 결과")
    print("=" * 50)
    counts = df['strategy_type'].value_counts()
    for strategy, count in counts.items():
        ratio = count / len(df) * 100
        bar = '█' * int(ratio / 3)
        print(f"  {strategy:<20} {count:>5}개  {ratio:>5.1f}%  {bar}")
    print(f"  {'합계':<20} {len(df):>5}개")
    print("=" * 50)

    unclassified_ratio = counts.get('UNCLASSIFIED', 0) / len(df) * 100
    if unclassified_ratio > 20:
        print(f"\n⚠️  미분류 종목이 {unclassified_ratio:.1f}%야. ADX_THRESHOLD 조정 고려해봐.")


def main():
    print(f"🚀 종목 전략 유형 분류 시작 [{datetime.now().strftime('%Y-%m-%d %H:%M')}]")
    print(f"   기준: ADX > {ADX_THRESHOLD} → TREND_FOLLOWING, 이하 → MEAN_REVERSION\n")

    df = load_latest_adx()
    df = classify(df)
    save(df)
    print_summary(df)

    print(f"\n🎉 분류 완료!")


if __name__ == "__main__":
    main()