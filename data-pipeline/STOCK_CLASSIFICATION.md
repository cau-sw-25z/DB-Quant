# 종목 성격 분류 기준 정의서

## 개요

종목별 가격 패턴과 변동성 특성을 분석하여 5가지 매매전략 유형 중 하나로 분류한다.
분류 결과는 `stock_classification` 테이블에 저장되며, 3주차 종목별 전략 매핑(DB-09)의 직접 입력값으로 사용된다.

- **분류 스크립트**: `data-pipeline/quant/classify_stocks.py`
- **출력 테이블**: `stock_classification`
- **사용 데이터**: `stock_metrics` (DB-05) + `price_histories`

---

## 분류 방식

점수를 합산하는 방식이 아닌 **순차 규칙 기반 분류**를 사용한다.
각 유형의 핵심 조건을 우선순위 순서대로 검사하여, 처음으로 조건을 만족하는 유형으로 확정한다.
어떤 조건도 만족하지 못하면 `UNCLASSIFIED`로 분류한다.

```
검사 순서: VOLATILITY_BREAKOUT → MOMENTUM → TREND_FOLLOWING → LOW_VOLATILITY → MEAN_REVERSION → UNCLASSIFIED
```

> 우선순위가 높은 유형일수록 특징이 뚜렷하고 강한 신호를 가진다.
> VOLATILITY_BREAKOUT 종목은 분류는 되지만 daily_screener.py 스캔 대상에서 제외된다. (리스크 과다)
> UNCLASSIFIED 종목은 현재 5가지 전략에 해당하지 않으며, 추후 새로운 전략 추가 시 흡수된다.

---

## 유형별 분류 기준

### 1. VOLATILITY_BREAKOUT (변동성돌파형)

> 하루 안에 크게 움직이는 종목. 이벤트성 급등락이 빈번한 테마주에 해당한다.

**분류 조건** (하나라도 만족하면 해당)

| 지표 | 조건 | 의미 |
|---|---|---|
| `annual_volatility` | ≥ 1.5 (150%) | 연간 기준 극단적 변동성 |
| `atr_ratio` | ≥ 0.07 (7%) | 일중 평균 변동폭이 종가의 7% 이상 |

**점수 계산**
```
score = annual_volatility + atr_ratio × 10
```

**해당 종목 유형**: 테마주, 급등락 소형주

> ⚠️ 이 유형은 분류만 하고 매매 시그널 스캔 대상에서는 제외한다. "전일 종가 시그널 → 다음날 시가 매수" 구조와 맞지 않고 리스크가 과다하기 때문이다.

---

### 2. MOMENTUM (모멘텀형)

> 최근 강하게 상승 중이고 거래량이 급증하는 종목. 투자자가 실제로 몰리고 있어야 한다.

**분류 조건** (아래 조건을 동시에 만족해야 함)

| 지표 | 조건 | 의미 |
|---|---|---|
| `cum_return_30d` | ≥ 0.10 (10%) | 최근 30일 수익률 10% 이상 |
| `volume_spike_freq` | ≥ 2회 | 최근 90일 내 거래량 급증(평균의 2배) 2회 이상 |

> 수익률만 높고 거래량이 없으면 모멘텀으로 보지 않는다.
> 거래량 없는 급등은 작전주 가능성이 있어 제외한다.

**점수 계산**
```
score = cum_return_30d × 10 + volume_spike_freq
```

**적용 전략**: `SmallCapMomentumStrategy`

**해당 종목 유형**: 성장주, 소형주, 단기 급등주

---

### 3. TREND_FOLLOWING (추세추종형)

> 꾸준히 한 방향으로 움직이는 종목. 장기 이동평균 위에서 오래 머무르고 중기 수익률이 양수여야 한다.

**분류 조건** (두 조건 모두 만족해야 함)

| 지표 | 조건 | 의미 |
|---|---|---|
| `above_ma60_ratio` | ≥ 0.60 (60%) | 최근 데이터의 60% 이상 기간 동안 60일 이평 위에 위치 |
| `cum_return_90d` | > 0 | 최근 90일 수익률 양수 (상승 방향성 확인) |

> 60일 이평 위에 있더라도 90일 수익률이 음수면 추세가 꺾인 것으로 판단하여 제외한다.

**점수 계산**
```
score = above_ma60_ratio × 10 + cum_return_90d × 5
```

**적용 전략**: `TrendFollowingStrategy`

**해당 종목 유형**: 대형주, ETF, 우량 성장주

---

### 4. LOW_VOLATILITY (저변동성 채널형)

> 변동성이 매우 낮고 방향성 없이 이동평균 채널 안에서 진동하는 종목. MA20을 자주 넘나들며 횡보한다.

**분류 조건** (세 조건 모두 만족해야 함)

| 지표 | 조건 | 의미 |
|---|---|---|
| `annual_volatility` | ≤ 0.25 (25%) | 연간 변동성 25% 이하 (매우 낮은 변동성) |
| `cross_ma20_freq` | ≥ 3회 | 최근 90일 내 20일 이평 교차 횟수 3회 이상 |
| `above_ma60_ratio` | 0.40 ~ 0.60 | 60일 이평 위아래를 반반씩 오가는 횡보 구간 |

> `above_ma60_ratio` 40~60% 조건은 방향성 없이 채널 안에서 진동하는 종목을 선별하기 위함이다.
> MEAN_REVERSION보다 더 낮은 변동성, 더 많은 교차 횟수, 방향성 없음 조건이 추가된 더 엄격한 기준이다.

**점수 계산**
```
score = cross_ma20_freq + (1 - annual_volatility) × 5
```

**적용 전략**: `DefensiveChannelStrategy`

**해당 종목 유형**: 저변동성 횡보주, 배당주

---

### 5. MEAN_REVERSION (평균회귀형)

> 변동성이 낮고 가격이 이동평균 주변을 진동하는 종목. 조용하게 평균으로 돌아오는 특성을 가진다.

**분류 조건** (두 조건 모두 만족해야 함)

| 지표 | 조건 | 의미 |
|---|---|---|
| `annual_volatility` | ≤ 0.30 (30%) | 연간 변동성 30% 이하 (낮은 변동성) |
| `cross_ma20_freq` | ≥ 2회 | 최근 90일 내 20일 이평 교차 횟수 2회 이상 |

> 변동성이 낮더라도 이평 교차가 없으면 단순히 거래가 없는 종목일 수 있어 제외한다.
> LOW_VOLATILITY 조건을 먼저 검사하므로, 세 조건을 동시에 만족하는 종목은 LOW_VOLATILITY로 분류된다.

**점수 계산**
```
score = cross_ma20_freq + (1 - annual_volatility) × 5
```

**적용 전략**: `MeanReversionStrategy`

**해당 종목 유형**: 우량 배당주, 저변동성 대형주

---

### 6. UNCLASSIFIED (미분류)

> 위 5가지 조건을 모두 만족하지 못하는 종목.

- 현재 전략으로 커버되지 않는 종목이다.
- 추후 새로운 매매전략 추가 시 이 종목들을 우선적으로 검토한다.
- `score = 0.0`으로 저장된다.

---

## 사용 지표 정의

| 지표명 | 출처 | 설명 |
|---|---|---|
| `annual_volatility` | `stock_metrics` | 최근 252일 일별 수익률의 표준편차 × √252 |
| `cum_return_30d` | `stock_metrics` | 최근 30 영업일 누적 수익률 |
| `cum_return_90d` | `stock_metrics` | 최근 90 영업일 누적 수익률 |
| `atr_ratio` | `price_histories` 계산 | 최근 20일 (고가-저가) 평균 ÷ 종가 |
| `above_ma60_ratio` | `price_histories` 계산 | 최근 데이터 중 60일 이평 위에 있는 날 비율 |
| `volume_spike_freq` | `price_histories` 계산 | 거래량이 20일 평균의 2배 이상인 날 수 |
| `cross_ma20_freq` | `price_histories` 계산 | 종가가 20일 이평을 교차한 횟수 |

---

## 협업 사항

### DB-09 (3주차)
이 분류 결과를 그대로 사용하므로 아래 테이블 구조를 고정한다.

```sql
CREATE TABLE IF NOT EXISTS `quant_db`.`stock_classification` (
  `id`            BIGINT       NOT NULL AUTO_INCREMENT,
  `stock_id`      BIGINT       NOT NULL,
  `ticker`        VARCHAR(50)  NOT NULL,
  `strategy_type` VARCHAR(50)  NOT NULL,
  `score`         DECIMAL(5,2) NOT NULL,
  `classified_at` DATETIME     NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `idx_stock_classification` (`stock_id` ASC),
  CONSTRAINT `fk_classification_stocks`
    FOREIGN KEY (`stock_id`) REFERENCES `quant_db`.`stocks` (`id`)
) ENGINE = InnoDB;
```

`strategy_type` 가능한 값:
- `TREND_FOLLOWING`
- `MEAN_REVERSION`
- `MOMENTUM`
- `LOW_VOLATILITY`
- `VOLATILITY_BREAKOUT` (분류만 됨, 스캔 제외)
- `UNCLASSIFIED`

### BE 팀 (BE-08)
종목 상세 API 응답에 `strategy_type` 필드 추가 여부 협의 필요.
FE 종목 상세 화면에 전략 유형 표시 시 위 6가지 값 중 하나가 내려간다.