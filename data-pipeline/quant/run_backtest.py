import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_URL
from sqlalchemy import create_engine, text
from backtest_engine import BacktestEngine
import pandas as pd

engine = create_engine(DB_URL)


# run_backtest.py — get_all_tickers 수정
def get_all_tickers() -> list[str]:
    query = text("""
        SELECT DISTINCT s.ticker
        FROM stocks s
        JOIN price_histories ph ON ph.stock_id = s.id
        WHERE s.name NOT LIKE '%스팩%'
          AND s.name NOT LIKE '%리츠%'
          AND s.name NOT LIKE '%우'
          AND s.name NOT LIKE '%1우'
          AND s.name NOT LIKE '%2우'
          AND s.name NOT LIKE '%3우'
          AND s.name NOT LIKE '%우B'
          AND s.name NOT LIKE '%우C'
        GROUP BY s.ticker
        HAVING AVG(ph.close_price * ph.volume) >= 10000000000
    """)
    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()
    return [r[0] for r in rows]

def print_stats():
    print("\n" + "="*60)
    print("📊 백테스트 결과 통계")
    print("="*60)

    # 전략 vs Buy&Hold 평균 비교
    strategy_query = text("""
        SELECT
            strategy_type,
            COUNT(*)                              AS 종목수,
            ROUND(AVG(total_return)*100, 2)       AS 평균수익률_pct,
            ROUND(AVG(buy_hold_return)*100, 2)    AS 평균BH수익률_pct,
            ROUND(AVG(excess_return)*100, 2)      AS 평균초과수익_pct,
            ROUND(AVG(annual_return)*100, 2)      AS 평균연환산_pct,
            ROUND(AVG(mdd)*100, 2)                AS 평균MDD_pct,
            ROUND(AVG(buy_hold_mdd)*100, 2)       AS 평균BH_MDD_pct,
            ROUND(AVG(sharpe_ratio), 3)           AS 평균샤프,
            ROUND(AVG(buy_hold_sharpe), 3)        AS 평균BH샤프,
            ROUND(AVG(win_rate)*100, 2)           AS 평균승률_pct,
            ROUND(AVG(trade_count), 1)            AS 평균거래횟수
        FROM backtest_results
        GROUP BY strategy_type
    """)
    with engine.connect() as conn:
        df_strategy = pd.read_sql(strategy_query, conn)

    print("\n[전략 vs Buy&Hold 평균 성과 비교]")
    print(df_strategy.to_string(index=False))

    # 전략이 Buy&Hold를 이긴 비율
    beat_query = text("""
        SELECT
            COUNT(*)                                                            AS 총종목수,
            SUM(CASE WHEN total_return > buy_hold_return THEN 1 ELSE 0 END)    AS 전략승리종목수,
            ROUND(SUM(CASE WHEN total_return > buy_hold_return THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS 전략승률_pct
        FROM backtest_results
        WHERE buy_hold_return IS NOT NULL
    """)
    with engine.connect() as conn:
        df_beat = pd.read_sql(beat_query, conn)

    print("\n[전략이 Buy&Hold를 이긴 비율]")
    print(df_beat.to_string(index=False))

    # 수익률 상위 10개 종목 — buy_hold, excess도 같이 표시
    top_query = text("""
        SELECT
            s.name                              AS 종목명,
            s.ticker,
            ROUND(br.total_return * 100, 2)    AS 전략수익률_pct,
            ROUND(br.buy_hold_return * 100, 2) AS BH수익률_pct,
            ROUND(br.excess_return * 100, 2)   AS 초과수익_pct,
            ROUND(br.mdd * 100, 2)             AS 전략MDD_pct,
            ROUND(br.win_rate * 100, 2)        AS 승률_pct,
            br.trade_count                      AS 거래횟수
        FROM backtest_results br
        JOIN stocks s ON br.stock_id = s.id
        ORDER BY br.total_return DESC
        LIMIT 10
    """)
    with engine.connect() as conn:
        df_top = pd.read_sql(top_query, conn)

    print("\n[수익률 상위 10개 종목]")
    print(df_top.to_string(index=False))

    # 수익률 하위 10개 종목
    bot_query = text("""
        SELECT
            s.name                              AS 종목명,
            s.ticker,
            ROUND(br.total_return * 100, 2)    AS 전략수익률_pct,
            ROUND(br.buy_hold_return * 100, 2) AS BH수익률_pct,
            ROUND(br.excess_return * 100, 2)   AS 초과수익_pct,
            ROUND(br.mdd * 100, 2)             AS 전략MDD_pct,
            ROUND(br.win_rate * 100, 2)        AS 승률_pct,
            br.trade_count                      AS 거래횟수
        FROM backtest_results br
        JOIN stocks s ON br.stock_id = s.id
        ORDER BY br.total_return ASC
        LIMIT 10
    """)
    with engine.connect() as conn:
        df_bot = pd.read_sql(bot_query, conn)

    print("\n[수익률 하위 10개 종목]")
    print(df_bot.to_string(index=False))

    # 전체 요약
    summary_query = text("""
        SELECT
            COUNT(*)                              AS 총종목수,
            ROUND(AVG(total_return)*100, 2)       AS 전체평균수익률_pct,
            ROUND(AVG(buy_hold_return)*100, 2)    AS 전체평균BH수익률_pct,
            ROUND(AVG(excess_return)*100, 2)      AS 전체평균초과수익_pct,
            ROUND(MAX(total_return)*100, 2)       AS 최고수익률_pct,
            ROUND(MIN(total_return)*100, 2)       AS 최저수익률_pct,
            ROUND(AVG(win_rate)*100, 2)           AS 전체평균승률_pct,
            SUM(CASE WHEN total_return > 0 THEN 1 ELSE 0 END)  AS 수익종목수,
            SUM(CASE WHEN total_return <= 0 THEN 1 ELSE 0 END) AS 손실종목수
        FROM backtest_results
    """)
    with engine.connect() as conn:
        df_summary = pd.read_sql(summary_query, conn)

    print("\n[전체 요약]")
    print(df_summary.to_string(index=False))
    print("="*60)
        
def main():
    START = "2022-01-01"
    END = "2025-12-31"

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE backtest_results"))
    print("🗑️  기존 백테스트 결과 초기화 완료\n")

    tickers = get_all_tickers()
    print(f"백테스트 대상 종목: {len(tickers)}개 ({START} ~ {END})\n")

    bt = BacktestEngine(engine)

    print("=== DYNAMIC 백테스트 ===")
    success, fail = 0, 0
    for ticker in tickers:
        result = bt.run(ticker, START, END)
        if result:
            success += 1
        else:
            fail += 1
    print(f"DYNAMIC 완료! 성공 {success}개 / 실패·제외 {fail}개\n")

    print("=== TURTLE 백테스트 ===")
    success, fail = 0, 0
    for ticker in tickers:
        result = bt.run(ticker, START, END, strategy_type="TURTLE")
        if result:
            success += 1
        else:
            fail += 1
    print(f"TURTLE 완료! 성공 {success}개 / 실패·제외 {fail}개\n")

    print_stats()


if __name__ == "__main__":
    main()