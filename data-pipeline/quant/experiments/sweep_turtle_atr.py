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
ATR_MULTIPLIERS = [1.5, 2.0, 2.5]


def run_sweep():
    tickers = get_all_tickers()
    bt = BacktestEngine(engine)

    for m in ATR_MULTIPLIERS:
        label = f"TURTLE_{m}"
        print(f"\n=== {label} 백테스트 시작 ({len(tickers)}개 종목) ===")

        with engine.begin() as conn:
            conn.execute(text("DELETE FROM backtest_results WHERE strategy_type = :label"), {"label": label})

        success, fail = 0, 0
        for ticker in tickers:
            result = bt.run(
                ticker, START, END,
                strategy_type="TURTLE",
                strategy_params={"atr_multiplier": m},
                save_label=label,
            )
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
            ROUND(AVG(win_rate)*100, 2)           AS 평균승률_pct,
            ROUND(AVG(trade_count), 1)            AS 평균거래횟수
        FROM backtest_results
        WHERE strategy_type LIKE 'TURTLE_%'
        GROUP BY strategy_type
        ORDER BY strategy_type
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    print("\n[ATR 배수별 TURTLE 비교]")
    print(df.to_string(index=False))


if __name__ == "__main__":
    run_sweep()
    print_comparison()