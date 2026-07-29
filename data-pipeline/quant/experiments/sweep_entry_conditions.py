import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_URL
from sqlalchemy import create_engine, text
from backtest_engine import BacktestEngine
from run_backtest import get_all_tickers
import pandas as pd

engine = create_engine(DB_URL)

START = "2022-01-01"
END = "2025-12-31"

# 원본 vs 완화 버전 비교
VARIANTS = {
    "DYNAMIC_BASE": {
        "adx_split": 25,
        "TREND_FOLLOWING": {"adx_threshold": 25, "vol_multiplier": 1.5},
        "MEAN_REVERSION": {"rsi_threshold": 35},
    },
    "DYNAMIC_RELAXED": {
        "adx_split": 20,
        "TREND_FOLLOWING": {"adx_threshold": 20, "vol_multiplier": 1.2},
        "MEAN_REVERSION": {"rsi_threshold": 40},
    },
}


def run_variant(label: str, params: dict):
    tickers = get_all_tickers()
    bt = BacktestEngine(engine)

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM backtest_results WHERE strategy_type = :label"), {"label": label})

    print(f"\n=== {label} 백테스트 시작 ({len(tickers)}개 종목) ===")
    success, fail = 0, 0
    for ticker in tickers:
        result = bt.run(ticker, START, END, save_label=label, dynamic_params=params)
        if result:
            success += 1
        else:
            fail += 1
    print(f"{label} 완료! 성공 {success}개 / 실패·제외 {fail}개")


def print_comparison():
    query = text("""
        SELECT
            strategy_type,
            COUNT(*)                              AS 종목수,
            ROUND(AVG(total_return)*100, 2)       AS 평균수익률_pct,
            ROUND(AVG(mdd)*100, 2)                AS 평균MDD_pct,
            ROUND(AVG(sharpe_ratio), 3)           AS 평균샤프,
            ROUND(AVG(win_rate)*100, 2)           AS 평균승률_pct,
            ROUND(AVG(trade_count), 1)            AS 평균거래횟수
        FROM backtest_results
        WHERE strategy_type IN ('DYNAMIC_BASE', 'DYNAMIC_RELAXED')
        GROUP BY strategy_type
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    print("\n[진입조건 완화 비교]")
    print(df.to_string(index=False))


if __name__ == "__main__":
    for label, params in VARIANTS.items():
        run_variant(label, params)
    print_comparison()