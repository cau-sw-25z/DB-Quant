import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy import text
from strategy_factory import StrategyFactory
import math


HARD_STOP = -1


class BacktestEngine:
    def __init__(self, engine, initial_capital=1_000_000):
        self.engine = engine
        self.initial_capital = initial_capital
        self.factory = StrategyFactory()

    def _get_stock_id(self, ticker: str) -> int | None:
        """strategy_type은 동적으로 결정하므로 stock_id만 조회"""
        query = text("""
            SELECT id FROM stocks WHERE ticker = :ticker
        """)
        with self.engine.connect() as conn:
            result = conn.execute(query, {"ticker": ticker}).fetchone()

        if result is None:
            print(f"[{ticker}] 종목 정보 없음")
            return None

        return result[0]

    def _fetch_data(self, stock_id: int, start_date: str, end_date: str) -> pd.DataFrame | None:
        query = text("""
            SELECT ph.date, ph.open_price, ph.high_price, ph.low_price,
                   ph.close_price, ph.volume,
                   ti.ma_5, ti.ma_20, ti.ma_60,
                   ti.rsi_14, ti.bb_upper, ti.bb_mid, ti.bb_lower,
                   ti.atr_14, ti.vol_ma_20, ti.adx_14
            FROM price_histories ph
            LEFT JOIN technical_indicators ti
                ON ti.stock_id = ph.stock_id AND ti.date = ph.date
            WHERE ph.stock_id = :stock_id
              AND ph.date BETWEEN :start AND :end
            ORDER BY ph.date ASC
        """)
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn, params={
                    "stock_id": stock_id,
                    "start":    start_date,
                    "end":      end_date,
                })
        except Exception as e:
            print(f"[stock_id={stock_id}] DB 조회 실패: {e}")
            return None

        if df is None or len(df) < 60:
            print(f"[stock_id={stock_id}] 데이터 부족 ({len(df) if df is not None else 0}행)")
            return None

        return df

    def _generate_dynamic_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        날짜별 ADX를 기준으로 두 전략 시그널 중 하나를 선택.
        ADX > 25  → TrendFollowingStrategy 시그널 사용
        ADX ≤ 25  → MeanReversionStrategy 시그널 사용
        ADX NaN   → 시그널 0 (관망)

        strategy_used 컬럼에 진입 전략을 기록해서
        _simulate_trades에서 진입/청산 전략 일관성을 보장함.
        """
        trend_obj = self.factory.get_strategy_by_name("TREND_FOLLOWING", df.copy())
        mean_obj  = self.factory.get_strategy_by_name("MEAN_REVERSION",  df.copy())

        if trend_obj is None or mean_obj is None:
            return pd.DataFrame()

        trend_df = trend_obj.generate_signals()[['date', 'Signal']].rename(
            columns={'Signal': 'trend_signal'}
        )
        mean_df = mean_obj.generate_signals()[['date', 'Signal']].rename(
            columns={'Signal': 'mean_signal'}
        )

        base = df[['date', 'open_price', 'close_price', 'adx_14']].copy()
        base = base.merge(trend_df, on='date', how='left')
        base = base.merge(mean_df,  on='date', how='left')
        base['trend_signal'] = base['trend_signal'].fillna(0.0)
        base['mean_signal']  = base['mean_signal'].fillna(0.0)

        def pick_signal(row):
            adx = row['adx_14']
            if pd.isna(adx):
                return 0.0, 'NONE'
            if adx > 25:
                return row['trend_signal'], 'TREND'
            return row['mean_signal'], 'MEAN'

        base[['Signal', 'strategy_used']] = base.apply(
            pick_signal, axis=1, result_type='expand'
        )

        return base[['date', 'open_price', 'close_price', 'Signal', 'strategy_used']].reset_index(drop=True)
    
    def _generate_static_signals(self, df: pd.DataFrame, strategy_type: str, strategy_params: dict = None) -> pd.DataFrame:
        """
        단일 전략(TRB/VMA 등)만 써서 시그널 생성. ADX 분기 없이 전략 하나로만 전 종목 테스트할 때 사용.
        """
        obj = self.factory.get_strategy_by_name(strategy_type, df.copy(), params=strategy_params)
        if obj is None:
            return pd.DataFrame()

        signal_df = obj.generate_signals()
        signal_df['strategy_used'] = strategy_type

        return signal_df[['date', 'open_price', 'close_price', 'Signal', 'strategy_used']].reset_index(drop=True)

    def _simulate_trades(self, signal_df: pd.DataFrame) -> list[dict]:
        """
        매매 시뮬레이션.

        손절 우선순위:
        1. 하드 손절 (HARD_STOP = -8%) — 전략/진입전략 무관, 항상 최우선
        2. 전략 기반 청산 — 진입 전략과 동일한 전략 신호일 때만 실행

        진입 전략(entry_strategy)을 기억해서
        전략이 바뀐 상태의 청산 신호는 무시함.
        """
        trades = []
        position       = None
        entry_strategy = None

        rows = signal_df.reset_index(drop=True)

        for i in range(len(rows) - 1):
            signal           = rows.loc[i, 'Signal']
            current_strategy = rows.loc[i, 'strategy_used']
            current_close    = rows.loc[i, 'close_price']
            next_open        = rows.loc[i + 1, 'open_price']
            next_date        = rows.loc[i + 1, 'date']

            if pd.isna(next_open) or next_open <= 0:
                continue

            # ── 우선순위 1: 하드 손절 ──────────────────────────────────
            # 전략 조건보다 먼저 체크, 진입 전략 무관하게 항상 발동
            if position is not None:
                loss_rate = (current_close - position['buy_price']) / position['buy_price']
                if loss_rate <= HARD_STOP:
                    profit_rate = (next_open - position['buy_price']) / position['buy_price']
                    trades.append({
                        'buy_date':      position['buy_date'],
                        'sell_date':     next_date,
                        'buy_price':     position['buy_price'],
                        'sell_price':    next_open,
                        'profit_rate':   profit_rate,
                        'signal_type':   -2.0,
                        'weight':        position['remaining'],
                        'strategy_used': entry_strategy,
                    })
                    position       = None
                    entry_strategy = None
                    continue  # 이미 청산했으니 아래 로직 건너뜀

            # ── 우선순위 2: 매수 진입 ──────────────────────────────────
            if signal == 1.0 and position is None:
                position = {
                    'buy_price': next_open,
                    'buy_date':  next_date,
                    'remaining': 1.0,
                }
                entry_strategy = current_strategy  # 진입 전략 저장

            # ── 우선순위 3: 전략 기반 청산 ────────────────────────────
            # 포지션 있고, 진입 전략과 현재 전략이 동일할 때만 반응
            elif signal < 0 and position is not None:
                if current_strategy != entry_strategy:
                    # 전략이 바뀐 상태의 청산 신호는 무시
                    continue

                profit_rate = (next_open - position['buy_price']) / position['buy_price']

                # 부분 익절 (50%)
                if math.isclose(signal, -0.5) and position['remaining'] > 0.5:
                    trades.append({
                        'buy_date':      position['buy_date'],
                        'sell_date':     next_date,
                        'buy_price':     position['buy_price'],
                        'sell_price':    next_open,
                        'profit_rate':   profit_rate,
                        'signal_type':   signal,
                        'weight':        0.5,
                        'strategy_used': entry_strategy,
                    })
                    position['remaining'] = 0.5

                # 전량 청산 (손절 / 익절 / 기본 청산)
                elif not math.isclose(signal, -0.5):
                    trades.append({
                        'buy_date':      position['buy_date'],
                        'sell_date':     next_date,
                        'buy_price':     position['buy_price'],
                        'sell_price':    next_open,
                        'profit_rate':   profit_rate,
                        'signal_type':   signal,
                        'weight':        position['remaining'],
                        'strategy_used': entry_strategy,
                    })
                    position       = None
                    entry_strategy = None

        return trades

    def _calc_metrics(self, trades: list[dict], start_date: str, end_date: str,
                  buy_hold_metrics: dict) -> dict | None:
        if not trades:
            return None

        from collections import defaultdict
        rt_map = defaultdict(float)

        for t in trades:
            rt_map[t['buy_date']] += t['profit_rate'] * t['weight']

        rt_returns = list(rt_map.values())

        total_return = 1.0
        for r in rt_returns:
            total_return *= (1 + r)
        total_return -= 1.0

        days  = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days
        years = days / 365
        annual_return = (1 + total_return) ** (1 / max(years, 0.01)) - 1

        win_rate = len([r for r in rt_returns if r > 0]) / len(rt_returns)

        cumulative = [1.0]
        for r in rt_returns:
            cumulative.append(cumulative[-1] * (1 + r))
        peak = cumulative[0]
        mdd  = 0.0
        for v in cumulative:
            peak = max(peak, v)
            drawdown = (v - peak) / peak
            mdd = min(mdd, drawdown)

        # 샤프비율 — 거래 단위 수익률을 실제 거래 빈도 기준으로 연환산
        MIN_TRADES_FOR_SHARPE = 5  # 표본이 이보다 적으면 표준편차 추정이 불안정해서 신뢰 불가
        risk_free = 0.03
        n = len(rt_returns)

        if n >= MIN_TRADES_FOR_SHARPE and np.std(rt_returns) > 0:
            trades_per_year = n / max(years, 0.01)
            risk_free_per_trade = risk_free / trades_per_year
            sharpe = (
                (np.mean(rt_returns) - risk_free_per_trade)
                / np.std(rt_returns)
                * np.sqrt(trades_per_year)
            )
        else:
            sharpe = None

        bh_return = buy_hold_metrics['return']
        excess_return = (total_return - bh_return) if bh_return is not None else None

        return {
            'total_return':    round(total_return, 6),
            'buy_hold_return':  bh_return,
            'buy_hold_mdd':     buy_hold_metrics['mdd'],
            'buy_hold_sharpe':  buy_hold_metrics['sharpe'],
            'excess_return':    round(excess_return, 6) if excess_return is not None else None,
            'annual_return':    round(annual_return, 6),
            'mdd':              round(mdd, 6),
            'sharpe_ratio':     round(sharpe, 4) if sharpe is not None else None,
            'win_rate':         round(win_rate, 4),
            'trade_count':      len(rt_returns),
        }

    def _save_result(self, stock_id: int, strategy_type: str,
                     start_date: str, end_date: str, metrics: dict):
        cleaned = {}
        for k, v in metrics.items():
            try:
                cleaned[k] = None if (isinstance(v, float) and np.isnan(v)) else v
            except (TypeError, ValueError):
                cleaned[k] = v

        query = text("""
            INSERT INTO backtest_results
                (stock_id, strategy_type, start_date, end_date,
                total_return, buy_hold_return, buy_hold_mdd, buy_hold_sharpe, excess_return,
                annual_return, mdd, sharpe_ratio,
                win_rate, trade_count, created_at)
            VALUES
                (:stock_id, :strategy_type, :start_date, :end_date,
                :total_return, :buy_hold_return, :buy_hold_mdd, :buy_hold_sharpe, :excess_return,
                :annual_return, :mdd, :sharpe_ratio,
                :win_rate, :trade_count, :created_at)
            ON DUPLICATE KEY UPDATE
                total_return    = VALUES(total_return),
                buy_hold_return = VALUES(buy_hold_return),
                buy_hold_mdd    = VALUES(buy_hold_mdd),
                buy_hold_sharpe = VALUES(buy_hold_sharpe),
                excess_return   = VALUES(excess_return),
                annual_return   = VALUES(annual_return),
                mdd             = VALUES(mdd),
                sharpe_ratio    = VALUES(sharpe_ratio),
                win_rate        = VALUES(win_rate),
                trade_count     = VALUES(trade_count),
                created_at      = VALUES(created_at)
        """)
        with self.engine.begin() as conn:
            conn.execute(query, {
                "stock_id":      stock_id,
                "strategy_type": strategy_type,
                "start_date":    start_date,
                "end_date":      end_date,
                "created_at":    datetime.now(),
                **cleaned,
            })

    def run(self, ticker: str, start_date: str, end_date: str,
            strategy_type: str = None, strategy_params: dict = None,
            save_label: str = None) -> dict | None:
        stock_id = self._get_stock_id(ticker)
        if stock_id is None:
            return None

        df = self._fetch_data(stock_id, start_date, end_date)
        if df is None:
            return None

        buy_hold_metrics = self._calc_buy_hold_metrics(df)

        if strategy_type is None:
            signal_df = self._generate_dynamic_signals(df)
            save_type = 'DYNAMIC'
        else:
            signal_df = self._generate_static_signals(df, strategy_type, strategy_params)
            save_type = save_label or strategy_type

        if signal_df.empty:
            return None

        trades = self._simulate_trades(signal_df)
        if not trades:
            print(f"[{ticker}] 거래 없음")
            return None

        metrics = self._calc_metrics(trades, start_date, end_date, buy_hold_metrics)
        if metrics is None:
            return None

        self._save_result(stock_id, save_type, start_date, end_date, metrics)
        
        # ✅ None 안전하게 처리 — 값 없으면 "N/A"로 표시
        def fmt_pct(v):
            return f"{v*100:.1f}%" if v is not None else "N/A"

        def fmt_signed_pct(v):
            return f"{v*100:+.1f}%" if v is not None else "N/A"

        bh_str      = fmt_pct(metrics['buy_hold_return'])
        ex_str      = fmt_signed_pct(metrics['excess_return'])
        bh_mdd_str  = fmt_pct(metrics['buy_hold_mdd'])
        sharpe_str  = f"{metrics['sharpe_ratio']}" if metrics['sharpe_ratio'] is not None else "N/A"
        bh_sharpe_str = f"{metrics['buy_hold_sharpe']}" if metrics['buy_hold_sharpe'] is not None else "N/A"

        print(f"[{ticker}] DYNAMIC | "
            f"전략 {metrics['total_return']*100:.1f}% | "
            f"B&H {bh_str} | "
            f"초과 {ex_str} | "
            f"전략MDD {metrics['mdd']*100:.1f}% vs B&H MDD {bh_mdd_str} | "
            f"전략샤프 {sharpe_str} vs B&H샤프 {bh_sharpe_str}")

        return metrics
    
    def _calc_buy_hold_metrics(self, df: pd.DataFrame) -> dict:

        prices = df[['date', 'close_price']].dropna().reset_index(drop=True)
        if prices.empty:
            return {'return': None, 'mdd': None, 'sharpe': None}

        first_open = df['open_price'].iloc[0]
        if pd.isna(first_open) or first_open <= 0:
            return {'return': None, 'mdd': None, 'sharpe': None}

        # 첫날 시가 대비 매일 종가의 누적 수익률
        cumulative = (prices['close_price'] / first_open).tolist()

        # 총수익률
        total_return = cumulative[-1] - 1.0

        # MDD
        peak = cumulative[0]
        mdd = 0.0
        for v in cumulative:
            peak = max(peak, v)
            drawdown = (v - peak) / peak
            mdd = min(mdd, drawdown)

        # 일별 수익률 → 샤프 계산용
        daily_returns = prices['close_price'].pct_change().dropna().tolist()
        risk_free_daily = 0.03 / 252
        if len(daily_returns) > 1 and np.std(daily_returns) > 0:
            sharpe = (np.mean(daily_returns) - risk_free_daily) / np.std(daily_returns) * np.sqrt(252)
        else:
            sharpe = None

        return {
            'return': round(total_return, 6),
            'mdd':    round(mdd, 6),
            'sharpe': round(sharpe, 4) if sharpe is not None else None,
        }