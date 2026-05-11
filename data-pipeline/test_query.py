import pandas as pd
from sqlalchemy import create_engine
from config import DB_URL

e = create_engine(DB_URL)
df = pd.read_sql(
    "SELECT ticker, annual_volatility FROM stock_metrics WHERE ticker IN ('FAKE999') ORDER BY date DESC LIMIT 1",
    e
)
print(df)
print(len(df))