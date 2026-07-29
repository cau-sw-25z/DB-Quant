import pandas as pd
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies import (
    MeanReversionStrategy,
    TrendFollowingStrategy,
    TurtleStrategy,
    SmallCapMomentumStrategy,
)


class StrategyFactory:
    STRATEGY_MAP = {
        "TREND_FOLLOWING": TrendFollowingStrategy,
        "MEAN_REVERSION":  MeanReversionStrategy,
        "TURTLE": TurtleStrategy,
        "MOMENTUM": SmallCapMomentumStrategy,
    }

    DEFAULT_PARAMS = {
        "TREND_FOLLOWING": {"breakout_window": 20, "atr_multiplier": 1.5},
        "TURTLE": {"entry_window": 20, "exit_window": 10, "atr_multiplier": 2.5},
        "MOMENTUM": {"breakout_window": 10, "vol_multiplier": 2.0, "atr_multiplier": 2.0},
    }

    def get_strategy_by_name(self, strategy_type: str, df: pd.DataFrame, params: dict = None):
        strategy_class = self.STRATEGY_MAP.get(strategy_type)
        if strategy_class is None:
            return None

        final_params = dict(self.DEFAULT_PARAMS.get(strategy_type, {}))
        if params:
            final_params.update(params)

        return strategy_class(df, **final_params)