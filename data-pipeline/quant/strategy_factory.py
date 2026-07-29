import pandas as pd
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies import (
    MeanReversionStrategy,
    TrendFollowingStrategy,
)


class StrategyFactory:
    STRATEGY_MAP = {
        "TREND_FOLLOWING": TrendFollowingStrategy,
        "MEAN_REVERSION":  MeanReversionStrategy,
    }

    def get_strategy_by_name(self, strategy_type: str, df: pd.DataFrame):
        strategy_class = self.STRATEGY_MAP.get(strategy_type)
        if strategy_class is None:
            return None

        if strategy_type == "TREND_FOLLOWING":
            return strategy_class(df, breakout_window=20, atr_multiplier=1.5)

        return strategy_class(df)
