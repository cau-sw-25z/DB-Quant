"""
자산 배분 최적화 모듈 - Inverse Volatility 방식
이슈: DB-06 / 선행: DB-05 (annual_volatility 계산 완료)
"""

import pandas as pd
from sqlalchemy import create_engine, text
from config import DB_URL
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

engine = create_engine(DB_URL)

MIN_RISK = 1
MAX_RISK = 5
WEIGHT_SUM_TOLERANCE = 1e-6

class WeightResult:
    
    def __init__(self, weights, risk_level):
        self.weights = weights
        self.risk_level = risk_level
    
    def validate(self):
        total = sum(self.weights.values())
        if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"비중 합계 오류: {total:.8f}")
    
    def __repr__(self):
        lines = [f"risk_level={self.risk_level}"]
        for ticker, w in self.weights.items():
            lines.append(f"  {ticker}: {w:.4f} ({w*100:.2f}%)")
        return "\n".join(lines)
    
    
    
def fetch_volatilities(tickers):
    ticker_list = ", ".join(f"'{t}'" for t in tickers)
    query = f"""
        SELECT ticker, MAX(annual_volatility) as annual_volatility
        FROM  stock_metrics
        WHERE ticker IN ({ticker_list})
        AND annual_volatility IS NOT NULL
        AND annual_volatility > 0
        GROUP BY ticker
    """
    
    df = pd.read_sql(query, engine)
    
    missing = set(tickers) - set(df.ticker.tolist())
    if missing:
        raise ValueError(f"DB에 없는 티커: {missing}")
    
    return dict(zip(df['ticker'], df['annual_volatility']))

def calc_inverse_vol_weights(volatilities):
    """역비중 계산"""
    inv_vols = {t: 1.0 / v for t, v in volatilities.items()}
    total = sum(inv_vols.values())
    return {t: v / total for t, v in inv_vols.items()}

def blend_weights(w_iv, w_eq, risk_level):
    """
    역비중과 균등 배분을 성향에 따라 선형 보간
    alpha=0 (안정형) -> 완전 역비중
    alpha=1 (공격형) -> 완전 균등
    """
    alpha = (risk_level - MIN_RISK) / (MAX_RISK - MIN_RISK)
    return {t: (1 - alpha) * w_iv[t] + alpha * w_eq[t] for t in w_iv}

# 메인 함수

def optimize_weights(tickers, risk_level):
    """
    티커 목록과 투자 성향을 받아 자산 배분 비중을 반환

    Args:
        tickers:    종목 티커 목록  예: ["005930", "000660"]
        risk_level: 투자 성향 1~5  (1=안정형, 5=공격형)

    Returns:
        WeightResult 객체 (weights 합계 = 1.0 보장)
    """
    if not tickers:
        raise ValueError("티커 목록이 비어있습니다.")
    if not (MIN_RISK <= risk_level <= MAX_RISK):
        raise ValueError(f"risk_level은 1~5여야 합니다. 입력: {risk_level}")
    
    if len(tickers) == 1:
        result = WeightResult({tickers[0]: 1.0}, risk_level)
        result.validate()
        return result
    
    volatilities = fetch_volatilities(tickers)
    n = len(tickers)
    
    w_iv = calc_inverse_vol_weights(volatilities)
    w_eq = {t: 1.0 / n for t in tickers}
    final = blend_weights(w_iv, w_eq, risk_level)
    
    last = list(final.keys())[-1]
    final[last] += 1.0 - sum(final.values())
    
    result = WeightResult(final, risk_level)
    result.validate()
    
    print(f"✅ 최적화 완료\n{result}")
    return result

# DB 저장

def save_portfolio_weights(portfolio_id, result):
     """portfolio_weights 테이블에 결과 저장"""
     rows = [
         {
             "portfolio_id": portfolio_id,
             "ticker": ticker,
             "weight": round(weight, 6),
             "risk_level": result.risk_level,
             "calculated_at": datetime.now()
         }
         for ticker, weight in result.weights.items()
     ]
     df = pd.DataFrame(rows)
     df.to_sql("portfolio_weights", con=engine, if_exists="append", index=False)
     print(f"✅ portfolio_id={portfolio_id} 저장 완료 ({len(rows)}건)")