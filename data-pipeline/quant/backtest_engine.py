import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy import text
from strategy_factory import StrategyFactory

class BacktestEngine:
    def __init__(self, engine, initial_capital=1_000_000):
        self.engine = engine
        self.initial_capital = initial_capital
        self.factory = StrategyFactory()
        
    def _fetch_data(self, stock_id: int, start_date: str, end_date: str) -> pd.DataFrame | None:
        query = text("""
                    SELECT ph.date, ph.open_price, ph.high_price, ph.low_price,
                        ph.close_price, ph.volume,
                        ti.ma_5, ti.ma_20, ti.ma_60,
                        ti.rsi_14, ti.bb_upper, ti.bb_mid, ti.bb_lower,
                        ti.atr_14, ti.vol_ma_20
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
                    "start": start_date, 
                    "end": end_date,
                })
        except Exception as e:
            print(f"[stock_id={stock_id}] DB 조회 실패: {e}")
            return None
        
        if df is None or len(df) < 60:
            print(f"[stock_id={stock_id}] 데이터 부족 ({len(df) if df is not None else 0}행)")
            return None
        return df
    
    def _get_stock_info(self, ticker: str) -> tuple[int, str] | None:
        query = text("""
                    SELECT sc.stock_id, sc.strategy_type
                    FROM stock_classification sc
                    JOIN stocks s ON sc.stock_id = s.id
                    WHERE s.ticker = :ticker
                    """)
        with self.engine.connect() as conn:
            result = conn.execute(query, {"ticker": ticker}).fetchone()

        if result is None:
            print(f"[{ticker}] 분류 정보 없음")
            return None
        
        stock_id, strategy_type = result[0], result[1]
        if strategy_type in ("UNCLASSIFIED", "VOLATILITY_BREAKOUT"):
            print(f"[{ticker}] 백테스트 제외 전략: {strategy_type}")
            return None
        
        return stock_id, strategy_type
    
    def _simulate_trades(self, signal_df: pd.DataFrame) -> list[dict]:
        trades = []
        position = None
        
        rows = signal_df.reset_index(drop=True)
        
        for i in range(len(rows) - 1):
            signal = rows.loc[i, 'Signal']
            next_open = rows.loc[i + 1, 'open_price']
            next_date = rows.loc[i + 1, 'date']
            
            if signal == 1.0 and position is None:
                if pd.isna(next_open) or next_open <= 0:
                    continue
                position = {
                    'buy_price': next_open,
                    'buy_date': next_date
                }
                
            elif signal < 0 and position is not None:
                profit_rate = (next_open - position['buy_price']) / position['buy_price']
                trades.append({
                    'buy_date': position['buy_date'],
                    'sell_date': next_date,
                    'buy_price': position['buy_price'],
                    'sell_price': next_open,
                    'profit_rate': profit_rate,
                    'signal_type': signal,
                })
                position = None
        
        return trades
    
    def _calc_metrics(self, trades: list[dict], start_date: str, end_date: str) -> dict:
        if not trades:
            return None
        
        returns = [t['profit_rate'] for t in trades]
        
        # 총 수익률(복리 계산)
        total_return = 1.0
        for r in returns:
            total_return *= (1 + r)
        total_return -= 1.0
        
        # 보유 기간(일수)
        days = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days
        years = days /365
        
        # 연환산 수익률
        annual_return = (1 + total_return) ** (1 / max(years, 0.01)) - 1
        
        # 승률
        win_rate = len([r for r in returns if r > 0]) / len(returns)
        
        # MDD (최데 낙폭)
        cumulative = [1.0]
        for r in returns:
            cumulative.append(cumulative[-1] * (1 + r))
        peak = cumulative[0]
        mdd = 0.0
        for v in cumulative:
            peak = max(peak, v)
            drawdown = (v - peak) / peak
            mdd = min(mdd, drawdown)
            
        # 샤프 지수(무위험 수익률 3% 가정)
        risk_free = 0.03 / 252
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = (np.mean(returns) -risk_free) / np.std(returns) * np.sqrt(252)
        else:
            sharpe = None
        
        return {
            'total_return': round(total_return, 6),
            'annual_return': round(annual_return, 6),
            'mdd': round(mdd, 6),
            'sharpe_ratio': round(sharpe, 4) if sharpe else None,
            'win_rate': round(win_rate, 4),
            'trade_count': len(trades),
        }
        
    def _save_result(self, stock_id: int, strategy_type: str, start_date: str, end_date: str, metrics: dict):
        import numpy as np
        
        cleaned = {}
        for k, v in metrics.items():
            try:
                if isinstance(v, float) and np.isnan(v):
                    cleaned[k] = None
                else:
                    cleaned[k] = v
            except (TypeError, ValueError):
                cleaned[k] = v
                
        metrics = cleaned
        
        query = text("""
                    INSERT INTO backtest_results
                        (stock_id, strategy_type, start_date, end_date,
                        total_return, annual_return, mdd, sharpe_ratio,
                        win_rate, trade_count, created_at)
                    VALUES
                        (:stock_id, :strategy_type, :start_date, :end_date,
                        :total_return, :annual_return, :mdd, :sharpe_ratio,
                        :win_rate, :trade_count, :created_at)
                    ON DUPLICATE KEY UPDATE
                        total_return  = VALUES(total_return),
                        annual_return = VALUES(annual_return),
                        mdd           = VALUES(mdd),
                        sharpe_ratio  = VALUES(sharpe_ratio),
                        win_rate      = VALUES(win_rate),
                        trade_count   = VALUES(trade_count),
                        created_at    = VALUES(created_at)
                    """)
        with self.engine.begin() as conn:
            conn.execute(query, {
                "stock_id": stock_id,
                "strategy_type": strategy_type,
                "start_date": start_date,
                "end_date": end_date,
                "created_at": datetime.now(),
                **metrics,
            })
            
    def run(self, ticker: str, start_date: str, end_date: str) -> dict | None:
        # 1. stock_id + strategy_type 조회
        info = self._get_stock_info(ticker)
        if info is None:
            return None
        stock_id, strategy_type = info
        
        # 2. 가격 + 지표 데이터 로드
        df = self._fetch_data(stock_id, start_date, end_date)
        if df is None:
            return None
        
        # 3. 전략 객체 생성 + 시그널 계산
        strategy = self.factory.get_strategy_by_name(strategy_type, df)
        if strategy is None:
            return None
        signal_df = strategy.generate_signals()
        if signal_df.empty:
            return None
        
        # 4. 매매 시뮬레이션
        trades = self._simulate_trades(signal_df)
        if not trades:
            print(f"[{ticker}] 거래 없음")
            return None
        
        # 5. 성과 계산
        metrics = self._calc_metrics(trades, start_date, end_date)
        if metrics is None:
            return None
        
        # 6. DB 저장
        self._save_result(stock_id, strategy_type, start_date, end_date, metrics)
        
        print(f"[{ticker}] {strategy_type} | "
                f"수익률 {metrics['total_return']*100:.1f}% | "
                f"MDD {metrics['mdd']*100:.1f}% | "
                f"승률 {metrics['win_rate']*100:.1f}% | "
                f"거래 {metrics['trade_count']}회")
        
        return metrics