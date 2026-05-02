# Quant Data Pipeline

본 프로젝트는 대한민국 증시(KOSPI, KOSDAQ)에 상장된 전체 종목 정보와 일봉 주가 데이터를 수집하여 로컬 MySQL 데이터베이스에 적재하는 파이썬 데이터 파이프라인입니다.

## 기술 스택
- **Language**: Python 3.13
- **Database**: MySQL 8.0 (Docker)
- **Libraries**: `finance-datareader`, `pandas`, `SQLAlchemy`, `PyMySQL`

## 개발 환경 세팅

**1. 가상환경 생성 및 활성화 (Windows 기준)**
```bash
py -m venv venv
.\venv\Scripts\activate
```
(Mac/Linux의 경우: python3 -m venv venv 후 source venv/bin/activate 실행)

**2. 필수 패키지 설치**
```bash
pip install -r requirements.txt
```

**3. DB 연결 설정**
각 파이썬 스크립트(sync_stocks.py, fetch_price_history.py) 상단에 있는 DB_URL 변수를 본인의 로컬 환경(비밀번호 등)에 맞게 수정해주세요.
# 수정 예시
```python
DB_URL = "mysql+pymysql://quant_user:본인비밀번호@localhost:3306/quant_db?charset=utf8mb4"
```

## 실행 순서
테이블 간의 외래키(Foreign Key) 제약조건이 존재하므로, 반드시 아래의 순서대로 스크립트를 실행해야 합니다.

**Step 1. 기초 종목 데이터 적재(sync_stocks.py)
KRX(한국거래소) 전체 상장 종목 리스트를 긁어와 stocks 테이블에 INSERT 합니다.
- **실행 명령어**
```bash
python sync_stocks.py
```
(안되면 python을 py로 바꾼 후 실행)
- **결과**: 약 2,800여 개의 종목 데이터 적재

**Step 2. 일봉 주가 데이터 적재(fetch_price_history.py)
stocks 테이블에 등록된 전체 종목의 과거 주가 데이터(일봉)를 순차적으로 수집하여 price_histories 테이블에 INSERT 합니다.
- **실행 명령어**
```bash
python fetch_price_history.py
```
(안되면 python을 py로 바꾼 후 실행)
- **주의사항**: 대상 종목이 많아 실행 시 10분 이상 소요될 수 있습니다.(진행률이 콘솔에 출력됩니다.)

## 데이터베이스 스키마 참고 (BE/FE 팀용)
**1. stocks 테이블**
- id (PK, Auto Increment)
- ticker (종목코드, 예: '005930')
- name (종목명, 예: '삼성전자')
- market (시장, 예: 'KOSPI')
**2. price_histories 테이블**
- date (거래일자)
- open_price (시가)
- high_price (고가)
- low_price (저가)
- close_price (종가)
- volume (거래량)
- stock_id (FK, stocks 테이블의 id 참조)

