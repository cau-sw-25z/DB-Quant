# 종목 성격 분류 기준 정의서

## 개요

종목별 ADX(추세강도) 값을 기준으로 TREND_FOLLOWING / MEAN_REVERSION 두 가지 유형으로 분류한다.
분류 결과는 `stock_classification` 테이블에 저장되며, `daily_screener.py`가 이 결과를 읽어
종목별로 어떤 전략을 적용할지 결정한다.

- **분류 스크립트**: `data-pipeline/quant/classify_stocks.py`
- **출력 테이블**: `stock_classification`
- **사용 데이터**: `technical_indicators`의 최신 `adx_14` 값

> 📌 예전엔 VOLATILITY_BREAKOUT/MOMENTUM/LOW_VOLATILITY 등을 포함한 8가지 정적 분류 체계였으나,
> ADX 기반 동적 분류로 아키텍처를 변경하면서 폐기했다. TRB/VMA/FMA/MOMENTUM/LOW_VOLATILITY
> 전략 코드는 `strategies/` 폴더에 남아있지만 분류·스캔 파이프라인에서는 더 이상 쓰이지 않는다.
> (MOMENTUM만 예외 — 별도 코드로 STRATEGY_MAP에 남아 있으나, 백테스트 성과 저조로
> daily_screener.py 스캔 대상에서는 제외됨. 상세는 아래 참고.)

---

## 분류 방식
ADX > 25 → TREND_FOLLOWING
ADX ≤ 25 → MEAN_REVERSION
ADX NaN → UNCLASSIFIED
`ADX_THRESHOLD`는 `classify_stocks.py` 상단 상수 하나로 관리되며, 이 값만 바꾸면
전체 분류 기준이 바뀐다.

**적용 전략**:
- `TREND_FOLLOWING` → `TrendFollowingStrategy`
- `MEAN_REVERSION` → `MeanReversionStrategy`

---

## MOMENTUM 관련 참고사항

`SmallCapMomentumStrategy`는 `strategy_factory.py`의 `STRATEGY_MAP`에 여전히 등록되어 있어
백테스트는 가능하지만, `stock_classification`을 통한 정식 분류 카테고리는 아니다.

> ⚠️ 백테스트 결과(평균수익률 6.35%, 샤프 -0.043)가 DYNAMIC/TURTLE 대비 유의미하게 저조하여
> `daily_screener.py` 스캔 대상에서 제외한다. (`WHERE sc.strategy_type NOT IN (..., 'MOMENTUM')`)

---

## UNCLASSIFIED (미분류)

ADX 값이 NULL인 종목(데이터 부족 등)이 여기 해당한다. `daily_screener.py` 스캔 대상에서 제외된다.

---

## 협업 사항

### DB-09
```sql
CREATE TABLE IF NOT EXISTS `quant_db`.`stock_classification` (
  `id`            BIGINT       NOT NULL AUTO_INCREMENT,
  `stock_id`      BIGINT       NOT NULL,
  `strategy_type` VARCHAR(50)  NOT NULL,   -- TREND_FOLLOWING / MEAN_REVERSION / UNCLASSIFIED
  `score`         DECIMAL(5,2) NOT NULL,   -- 해당 종목의 ADX 값
  `classified_at` DATETIME     NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `idx_stock_classification` (`stock_id` ASC),
  CONSTRAINT `fk_classification_stocks`
    FOREIGN KEY (`stock_id`) REFERENCES `quant_db`.`stocks` (`id`)
) ENGINE = InnoDB;
```

### BE 팀 (BE-08)
종목 상세 API 응답에 `strategy_type` 필드 추가 여부 협의 필요.
FE 종목 상세 화면에 전략 유형 표시 시 `TREND_FOLLOWING` / `MEAN_REVERSION` / `UNCLASSIFIED` 중 하나가 내려간다.