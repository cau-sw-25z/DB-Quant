import pytest
import pandas as pd
from sqlalchemy import create_engine
from quant.optimize_weight import (
    optimize_weights,
    WeightResult,
    fetch_volatilities,
)
from config import DB_URL

engine = create_engine(DB_URL)

TICKERS_3 = ["005930", "000660", "005935"]
TICKERS_5 = ["005930", "000660", "005935", "005380", "373220"]
SINGLE_TICKER = ["005930"]

# 1. 비중 합계 = 1.0
class TestWeightSum:
    
    def test_모든_성향에서_합계는_1(self):
        for risk_level in range(1, 6):
            result = optimize_weights(TICKERS_3, risk_level)
            total = sum(result.weights.values())
            assert abs(total - 1.0) < 1e-6, (
                f"risk_level={risk_level} 합계={total}"
            )
    def test_종목_많아도_합계는_1(self):
        result = optimize_weights(TICKERS_5, risk_level=3)
        assert abs(sum(result.weights.values()) - 1.0) < 1e-6
        
# 2. 단일 종목 -> 100%
class TestSingleTicker:
    def test_단일_종목_100퍼센트(self):
        result = optimize_weights(SINGLE_TICKER, risk_level=3)
        assert result.weights[SINGLE_TICKER[0]] == pytest.approx(1.0)
        
    def test_단일_종목은_성향_무관(self):
        for risk in [1, 3, 5]:
            result = optimize_weights(SINGLE_TICKER, risk_level=risk)
            assert result.weights[SINGLE_TICKER[0]] == pytest.approx(1.0)
            
            
# 3. 성향 등급 경계값
class TestRiskLevel:
    def test_안정형은_저변동성_비중이_높다(self):
        """
        변동성 가장 낮은 종목이 risk_level=1일 때
        변동성 가장 높은 종목보다 비중이 커야 함
        """
        vols = fetch_volatilities(TICKERS_5)
        
        low_vol_ticker = min(vols, key=vols.get)
        high_vol_ticker = max(vols, key=vols.get)
        
        result = optimize_weights(TICKERS_5, risk_level=1)
        assert result.weights[low_vol_ticker] > result.weights[high_vol_ticker]
        
    def test_공격형은_균등_배분(self):
        result = optimize_weights(TICKERS_3, risk_level=5)
        expected = 1.0 / len(TICKERS_3)
        for w in result.weights.values():
            assert w == pytest.approx(expected, abs=1e-6)
    
    def test_공격형이_안정형보다_비중_차이_작다(self):
        vols = fetch_volatilities(TICKERS_5)
        
        low_vol_ticker = min(vols, key=vols.get)
        high_vol_ticker = max(vols, key=vols.get)
        
        r1 = optimize_weights(TICKERS_5, risk_level=1)
        r5 = optimize_weights(TICKERS_5, risk_level=5)
        
        diff_r1 = abs(r1.weights[low_vol_ticker] - r1.weights[high_vol_ticker])
        diff_r5 = abs(r5.weights[low_vol_ticker] - r5.weights[high_vol_ticker])
        assert diff_r5 < diff_r1
        
    @pytest.mark.parametrize("bad", [0, 6, -1, 100])
    def test_범위_밖_성향은_에러(self, bad):
        with pytest.raises(ValueError, match="1~5"):
            optimize_weights(TICKERS_3, risk_level=bad)
            
    def test_빈_티커_에러(self):
        with pytest.raises(ValueError, match="비어있습니다"):
            optimize_weights([], risk_level=3)
            
    def test_없는_티커_에러(self):
        with pytest.raises(ValueError, match="DB에 없는 티커"):
            optimize_weights(["FAKE999", "FAKE998"], risk_level=3)
            
# 4. WeightResult 클래스 검증
class TestWeightResult:
    def test_반환값이_WeightResult_타입(self):
        result = optimize_weights(TICKERS_3, risk_level=3)
        assert isinstance(result, WeightResult)
        
    def test_weights에_요청한_티커_모두_있음(self):
        result = optimize_weights(TICKERS_3, risk_level=3)
        assert set(result.weights.keys()) == set(TICKERS_3)
        
    def test_모든_비중은_양수(self):
        result = optimize_weights(TICKERS_3, risk_level=3)
        for ticker, w in result.weights.items():
            assert w > 0, f"{ticker} 비중이 0 이하: {w}"
            
