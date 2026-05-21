import json
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
from sqlalchemy import create_engine, text
import math
from tqdm import tqdm
import time
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_URL
from strategy_factory import StrategyFactory

warnings.filterwarnings("ignore")

engine = create_engine(DB_URL)

class DailyScreener:
    def __init__(self):
        print("통합 스크리너 초기화 중...")
        self.factory = StrategyFactory()
        self.tickers = []
        self.stock_names = {}
        self.strategy_map = {}
        self.holding_map = {}
        
        self._load_all_at_once()

    def _load_all_at_once(self):
        """
        stock_classification 테이블에서 투자 가능 종목을 불러옴.
        UNCLASSIFIED 종목은 제외.
        """
        universe_query = text("""
                    SELECT s.ticker, s.name, sc.strategy_type
                    FROM stocks s
                    JOIN stock_classification sc on.stock_id = s.id
                    WHERE sc.strategy_type NOT IN ('UNCLASSIFIED', 'VOLATILITY_BREAKOUT')
                    """)
        with engine.connect() as conn:
            universe_df = pd.read_sql(universe_query, conn)
        
        for _, row in universe_df.iterrows():
            t = row['ticker']
            self.tickers.append(t)
            self.stock_names[t] = row['name']
            self.strategy_map[t] = row['strategy_type']
        
        print(f"  → 스캔 대상 종목: {len(self.tickers)}개")
        
        try:
            holding_query = text("""
                                SELECT s.ticker, sc.strategy_type
                                FROM portfolios p
                                JOIN stocks s ON p.stock_id = s.id
                                JOIN stock_classification sc ON sc.stock_id = s.id
                                WHERE p.is_active = 1
                                """)
            with engine.connect() as conn:
                holding_df = pd.read_sql(holding_query, conn)
                
            for _, row in holding_df.iterrows():
                self.holding_map[row['ticker']] = row['strategy_type']
                
            print(f"  → 현재 보유 종목: {len(self.holding_map)}개")
            
        except Exception:
            print("  → portfolios 테이블 없음. 매도 체크 없이 매수 스캔만 진행.")
        
        print(f"초기화 완료.")

    def _fetch_price_data(self, ticker: str) -> pd.DataFrame | None:
        cutoff = (datetime.today() - timedelta(days=150)).strftime('%Y-%m-%d')
        
        query = text("""
                    SELECT ph.date,
                        ph.open_price,
                        ph.high_price,
                        ph.low_price,
                        ph.close_price,
                        ph.volume
                    FROM price_histories ph
                    JOIN stocks s ON ph.stock_id = s.id
                    WHERE s.ticker = :ticker
                    AND ph.date >= :cutoff
                    ORDER BY ph.date ASC
                    """)
        
        try:
            with engine.connect() as conn:
                df = pd.read_sql(query, conn, params={"ticker": ticker, "cutoff": cutoff})

        except Exception as e:
            print(f"[{ticker}] DB 조회 실패: {e}")
            return None
        
        if df.empty or len(df) < 60:
            return None
        
        return df
    
    def _check_data_integrity(self, df: pd.DataFrame) -> bool:
        """
        액면분할 등 비정상 틱 감지.
        전일 대비 등락폭이 31% 초과이면 False 반환.
        """
        yesterday_close = df['close_price'].iloc[-2]
        today_close = df['close_price'].iloc[-1]
        daily_return = (today_close - yesterday_close) / yesterday_close
        return abs(daily_return) <= 0.31
                
    def analyze_single_ticker(self, ticker: str) -> dict | None:
        
        df = self._fetch_price_data(ticker)
        if df is None:
            return None
        
        if not self._check_data_integrity(df):
            return None

        try:
            stock_name = self.stock_names.get(ticker, '알수없음')
            is_holding = ticker in self.holding_map
            
            # 트랙 결정 + 전략 객체 생성
            if is_holding:
                strategy_type = self.holding_map[ticker]
                action_type = "SELL_CHECK"
            else:
                strategy_type = self.strategy_map.get(ticker)
                if strategy_type is None:
                    return None
                action_type = "BUY_CHECK"
                
            strategy = self.factory.get_strategy(strategy_type, df)
            if strategy is None:
                return None

            # 시그널 계산
            signal_df = strategy.generate_signals()
            if signal_df.empty or len(signal_df) < 2:
                return None
            
            current_signal = signal_df.iloc[-1]["Signal"]
            yesterday_signal = signal_df.iloc[-2]["Signal"]
            
            today_close = df['close_price'].iloc[-1]
            yesterday_close = df['close_price'].iloc[-2]
            daily_return = (today_close - yesterday_close) / yesterday_close
            
            # 결과 판정
            base = {
                "ticker": ticker,
                "name": stock_name,
                "strategy_type": strategy_type,
                "close_price": today_close,
                "signal_value": current_signal,
                "signal_date": datetime.today().date(),
            }
            
            # [매도]
            if action_type == "SELL_CHECK" and current_signal < 0:
                action_msg = "전량 매도 청산 🔵"
                if math.isclose(current_signal, -0.5):
                    action_msg = "50% 부분 익절 🔵"
                elif math.isclose(current_signal, -1.5):
                    action_msg = "과열 익절 청산 🔵"
                elif math.isclose(current_signal, -2.0):
                    action_msg = "긴급 손절 ⚫"
                return {**base, "action": action_msg}

            # [결과 2] 매수 시그널 발생
            elif action_type == "BUY_CHECK" and math.isclose(current_signal, 1.0):
                if math.isclose(yesterday_signal, 1.0):
                    return None
                if daily_return >= 0.295:
                    return{**base, "action": "상한가 도달 (매수 보류)"}
                return {**base, "action": "신규 매수 진입 🔴"}

        except Exception as e:
            print(f"[{ticker}] 분석 에러: {e}")

        return None
    
    def save_signals_to_db(self, results: list[dict]):
        if not results:
            return
        
        df = pd.DataFrame(results)
        
        placeholders = ", ".join(f"'{t}'" for t in df['ticker'].tolist())
        with engine.connect() as conn:
            id_df = pd.read_sql(
                f"SELECT id, ticker FROM stocks WHERE ticker IN ({placeholders})", conn
            )
            
        df = df.merge(id_df, on='ticker', how='inner')
        df = df.rename(columns={"id": "stock_id"})
        df['created_at'] = datetime.now()
        
        cols = ["stock_id", "ticker", "strategy_type", "action",
                "close_price", "signal_value", "signal_date", "created_at"]
        df[cols].to_sql('trading_signals', con=engine, if_exists='append', index=False)
        print(f"trading_signals 테이블에 {len(df)}건 저장 완료.")

    def run_full_scan(self, max_workers=10) -> pd.DataFrame:
        print(f"\n총 {len(self.tickers)}개 종목 스캔 시작 (스레드: {max_workers}개)")
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self.analyze_single_ticker, t): t
                for t in self.tickers
                }
            for future in tqdm(as_completed(future_map), total=len(self.tickers), desc="스캔 진행률", ncols=80):
                result = future.result()
                if result:
                    results.append(result)

        print(f"\n전 종목 스캔 완료! 액션 종목: {len(results)}개")

        if results:
            self.save_signals_to_db(results)
            result_df = pd.DataFrame(results)
            return result_df.sort_values(by=["action", "strategy_type"]).reset_index(drop=True)
        
        return pd.DataFrame()


if __name__ == "__main__":
    screener = DailyScreener()
    report = screener.run_full_scan(max_workers=10)

    if not report.empty:
        print("\n=== 내일 아침 시가 대응 리스트 ===")
        print(report.to_string(index=False))
    else:
        print("\n오늘은 매수/매도 액션 종목 없음. 관망.")