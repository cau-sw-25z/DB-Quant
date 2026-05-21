import pandas as pd
from sqlalchemy import create_engine, text
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_URL

from strategies import (
    MeanReversionStrategy,
    TrendFollowingStrategy,
    SmallCapMomentumStrategy,
    DefensiveChannelStrategy,
)

engine = create_engine(DB_URL)

class StrategyFactory:
    STRATEGY_MAP = {
        "MEAN_REVERSION": MeanReversionStrategy,
        "TREND_FOLLOWING": TrendFollowingStrategy,
        "MOMENTUM": SmallCapMomentumStrategy,
        "LOW_VOLATILITY": DefensiveChannelStrategy,
    }

    def get_strategy_by_name(self, strategy_type: str, df: pd.DataFrame):
        strategy_class = self.STRATEGY_MAP.get(strategy_type)
        if strategy_class is None:
            return None
        
        if strategy_type == "MEAN_REVERSION":
            return strategy_class(df, bb_window=20, bb_std=2.0)
        elif strategy_type == "TREND_FOLLOWING":
            return strategy_class(df, breakout_window=20, ma_exit=20, ma_trend=60)
        elif strategy_type == "LOW_VOLATILITY":
            return strategy_class(df, ma_window=20, envelope_pct=0.05)
        else:
            return strategy_class(df)
    
    def get_strategy_type_from_db(self, ticker: str) -> str | None:
        query = text("""
                    SELECT strategy_type
                    FROM stock_classification
                    WHERE ticker = :ticker
                    """)
        with engine.connect() as conn:
            result = conn.execute(query, {"ticker": ticker}).fetchone()
        
        if result is None:
            return None
        strategy_type = result[0]
        if strategy_type in ("UNCLASSIFIED", "VOLATILITY_BREAKOUT"):
            return None
        return strategy_type