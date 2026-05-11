import os

DB_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://quant_user:0615@localhost:3306/quant_db?charset=utf8mb4"
)