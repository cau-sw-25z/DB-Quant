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


def run_single_strategy(strategy_type: str):
    tickers = get_all_tickers()
    print(f"\n=== {strategy_type} 백테스트 시작 ({len(tickers)}개 종목) ===")

    bt = BacktestEngine(engine)
    success, fail = 0, 0

    for ticker in tickers:
        result = bt.run(ticker, START, END, strategy_type=strategy_type)
        if result:
            success += 1
        else:
            fail += 1

    print(f"{strategy_type} 완료! 성공 {success}개 / 실패·제외 {fail}개")


def print_stats_for(strategy_type: str):
    query = text("""
        SELECT
            COUNT(*)                              AS 종목수,
            ROUND(AVG(total_return)*100, 2)       AS 평균수익률_pct,
            ROUND(AVG(buy_hold_return)*100, 2)    AS 평균BH수익률_pct,
            ROUND(AVG(mdd)*100, 2)                AS 평균MDD_pct,
            ROUND(AVG(win_rate)*100, 2)           AS 평균승률_pct,
            ROUND(AVG(trade_count), 1)            AS 평균거래횟수
        FROM backtest_results
        WHERE strategy_type = :strategy_type
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"strategy_type": strategy_type})
    print(f"\n[{strategy_type} 결과]")
    print(df.to_string(index=False))


def main():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM backtest_results WHERE strategy_type IN ('TURTLE')"))
    print("🗑️  기존 결과 초기화 완료")

    run_single_strategy("TURTLE")

    print_stats_for("TURTLE")

if __name__ == "__main__":
    main()