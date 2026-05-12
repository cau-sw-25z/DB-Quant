# Quant Data Pipeline

대한민국 증시(KOSPI, KOSDAQ) 전체 종목의 주가 데이터를 수집하고, 수익률/변동성 지표를 계산하여 전략 유형을 분류하는 파이썬 데이터 파이프라인입니다.

## 기술 스택

- **Language**: Python 3.13
- **Database**: MySQL 8.0 (Docker)
- **Libraries**: `finance-datareader`, `pandas`, `SQLAlchemy`, `PyMySQL`

---

## 개발 환경 세팅 (최초 1회)

**1. 가상환경 생성 및 활성화**

```bash
# Windows
py -m venv venv
.\venv\Scripts\activate

# Mac / Linux
python3 -m venv venv
source venv/bin/activate
```

**2. 필수 패키지 설치**

```bash
pip install -r requirements.txt
```

**3. DB 연결 설정**

config.py파일의 `DB_URL`을 본인 비밀번호로 수정해주세요.

```python
DB_URL = "mysql+pymysql://quant_user:본인비밀번호@localhost:3306/quant_db?charset=utf8mb4"
```

**4. Docker로 MySQL 실행**

```bash
docker-compose up -d

# 정상 실행 확인
docker ps  # quant_mysql 컨테이너가 보이면 OK
```

---

## 스크립트 목록

| 파일 | 역할 | 실행 빈도 |
|---|---|---|
| `sync_stocks.py` | KRX 전체 종목 목록 동기화 | 주 1회 (신규 상장 대응) |
| `fetch_price_history.py` | 종목별 일봉 주가 수집 | 매일 (장 마감 후) |
| `calculate_returns.py` | 수익률 / 변동성 / 샤프지수 계산 | 매일 (fetch 실행 후) |
| `classify_stock.py` | 4가지 전략 유형 분류 | 필요시 (주 1회 권장) |
| `validate_data.py` | 데이터 정합성 검증 | 필요시 (이상 징후 확인) |

---

## 실행 순서

### 🔵 최초 실행 (DB가 완전히 비어있을 때)

테이블 간 외래키 제약이 있어서 **반드시 아래 순서대로** 실행해야 해요.

```
1. sync_stocks.py          → stocks 테이블 채우기
2. fetch_price_history.py  → price_histories 테이블 채우기  (10분 이상 소요)
3. calculate_returns.py    → stock_metrics 테이블 채우기    (30초 이상 소요)
4. classify_stock.py       → stock_classification 테이블 채우기
```

```bash
py sync_stocks.py
py fetch_price_history.py
py calculate_returns.py
py classify_stock.py
```

---

### 🟢 정기 업데이트 (매일 장 마감 후)

이미 데이터가 있는 상태에서 **새로운 날짜 데이터만 추가**합니다.
각 스크립트가 DB의 마지막 날짜를 확인하고 없는 것만 처리하므로 안전하게 반복 실행할 수 있어요.

```
1. fetch_price_history.py  → 새 날짜 주가만 추가
2. calculate_returns.py    → 새 날짜 지표만 계산 후 추가
```

```bash
py fetch_price_history.py
py calculate_returns.py
```

> 💡 `sync_stocks.py`는 매일 실행할 필요는 없어요. 신규 상장 종목이 생겼을 때만 실행하면 됩니다.

---

### 🟡 신규 상장 종목이 생겼을 때 (주 1회 권장)

`sync_stocks.py`는 이미 있는 종목은 건너뛰고, **새로 추가된 종목만 INSERT**합니다.

```
1. sync_stocks.py          → 신규 상장 종목만 추가 (기존 종목 스킵)
2. fetch_price_history.py  → 신규 종목의 과거 데이터 수집
3. calculate_returns.py    → 신규 종목 지표 계산
```

```bash
py sync_stocks.py
py fetch_price_history.py
py calculate_returns.py
```

---

### 🔴 전략 유형 재분류가 필요할 때

분류 기준을 바꿨거나 데이터가 많이 쌓인 경우 재실행하면 됩니다.
`stock_classification` 테이블 전체를 덮어씁니다.

```bash
py classify_stock.py
```

---

## 각 스크립트 동작 상세

### sync_stocks.py

- KRX 전체 상장 종목 리스트를 가져와 `stocks` 테이블에 저장
- `INSERT IGNORE` 방식 → 이미 있는 ticker는 조용히 건너뜀, 에러 없음
- 실행 후 신규 추가 / 스킵 종목 수를 출력

```
✅ 처리 완료!
   → 전체 KRX 종목: 2834개
   → 신규 추가:     3개
   → 이미 존재(스킵): 2831개
```

### fetch_price_history.py

- `stocks` 테이블의 종목별로 **DB에 없는 날짜부터** 주가를 수집
- 종목별 마지막 저장 날짜를 확인하고 그 다음 날부터만 요청
- 이미 최신 상태인 종목은 자동으로 건너뜀

```
[1/2834] 삼성전자(005930) | 2025-05-09 부터 수집
[2/2834] SK하이닉스(000660) | 이미 최신 데이터. 건너뜀.
```

### calculate_returns.py

- `price_histories`를 읽어 수익률 / 연간화 변동성 / 샤프지수를 계산
- 이미 계산된 날짜 이후분만 계산하여 `stock_metrics`에 **append**
- rolling(252) 계산을 위해 내부적으로 앞 380일치를 버퍼로 읽지만, 저장은 새 날짜 행만 함

### classify_stock.py

- `stock_metrics` + `price_histories`를 조합해 4가지 전략 유형으로 분류
- 실행할 때마다 `stock_classification` 전체를 새로 덮어씀
- 실행 후 유형별 분포 출력 (편중 여부 확인용)

```
=== 유형별 종목 분포 ===
TREND_FOLLOWING           712개   25.1%  ████████
MEAN_REVERSION            689개   24.3%  ████████
MOMENTUM                  748개   26.4%  ████████
VOLATILITY_BREAKOUT       687개   24.2%  ████████
합계                     2836개
```

### validate_data.py

- 데이터 이상 여부를 읽기 전용으로 검증 (DB 데이터 변경 없음)
- NULL 값, 고가 < 저가 이상치, 거래량 0 건수 등을 체크
- 의심스러운 상황이 생겼을 때 실행해서 확인

---

## DB 스키마

```
stocks
├── id          BIGINT PK
├── ticker      VARCHAR(50) UNIQUE   예: '005930'
├── name        VARCHAR(255)         예: '삼성전자'
└── market      VARCHAR(50)          예: 'KOSPI'

price_histories
├── id          BIGINT PK
├── stock_id    BIGINT FK → stocks.id
├── date        DATE
├── open_price  DECIMAL(15,2)
├── high_price  DECIMAL(15,2)
├── low_price   DECIMAL(15,2)
├── close_price DECIMAL(15,2)
└── volume      BIGINT

stock_metrics
├── stock_id         BIGINT FK → stocks.id
├── ticker           VARCHAR(50)
├── date             DATE
├── daily_return     DOUBLE
├── cum_return_30d   DOUBLE
├── cum_return_90d   DOUBLE
├── cum_return_1y    DOUBLE
├── annual_volatility DOUBLE
└── sharpe_ratio     DOUBLE

stock_classification
├── id             BIGINT PK
├── stock_id       BIGINT FK → stocks.id
├── ticker         VARCHAR(50)
├── strategy_type  VARCHAR(50)   TREND_FOLLOWING / MEAN_REVERSION / MOMENTUM / VOLATILITY_BREAKOUT
├── score          DECIMAL(5,2)
└── classified_at  DATETIME
```

---

## DB 접속 정보

| 항목 | 값 |
|---|---|
| Host | 127.0.0.1 |
| Port | 3306 |
| Database | quant_db |
| Username | quant_user |
| Password | `.env` 파일 참고 (팀장에게 문의) |

---

## DB 종료 / 초기화

```bash
# 컨테이너 종료 (데이터 유지)
docker-compose down

# 컨테이너 + 데이터 완전 삭제 (초기화할 때만!)
docker-compose down -v
```