SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

CREATE SCHEMA IF NOT EXISTS `quant_db` DEFAULT CHARACTER SET utf8;
USE `quant_db`;

-- -----------------------------------------------------
-- users
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `quant_db`.`users` (
  `id`            BIGINT       NOT NULL AUTO_INCREMENT,
  `email`         VARCHAR(255) NOT NULL,
  `nickname`      VARCHAR(255) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `created_at`    DATETIME     NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `email_UNIQUE` (`email` ASC)
) ENGINE = InnoDB;

-- -----------------------------------------------------
-- stocks
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `quant_db`.`stocks` (
  `id`     BIGINT       NOT NULL AUTO_INCREMENT,
  `ticker` VARCHAR(50)  NOT NULL,
  `name`   VARCHAR(255) NOT NULL,
  `market` VARCHAR(50)  NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `ticker_UNIQUE` (`ticker` ASC)
) ENGINE = InnoDB;

-- -----------------------------------------------------
-- watch_lists
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `quant_db`.`watch_lists` (
  `id`       BIGINT NOT NULL AUTO_INCREMENT,
  `user_id`  BIGINT NOT NULL,
  `stock_id` BIGINT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uq_watch_list_user_stock` (`user_id` ASC, `stock_id` ASC),
  CONSTRAINT `fk_watch_list_users`
    FOREIGN KEY (`user_id`)  REFERENCES `quant_db`.`users`  (`id`),
  CONSTRAINT `fk_watch_list_stocks`
    FOREIGN KEY (`stock_id`) REFERENCES `quant_db`.`stocks` (`id`)
) ENGINE = InnoDB;

-- -----------------------------------------------------
-- portfolios
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `quant_db`.`portfolios` (
  `id`      BIGINT       NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT       NOT NULL,
  `name`    VARCHAR(255) NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_portfolios_users`
    FOREIGN KEY (`user_id`) REFERENCES `quant_db`.`users` (`id`)
) ENGINE = InnoDB;

-- -----------------------------------------------------
-- portfolio_items
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `quant_db`.`portfolio_items` (
  `id`           BIGINT         NOT NULL AUTO_INCREMENT,
  `portfolio_id` BIGINT         NOT NULL,
  `stock_id`     BIGINT         NOT NULL,
  `avg_price`    DECIMAL(15,2)  NOT NULL,
  `quantity`     INT            NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_portfolio_items_portfolios`
    FOREIGN KEY (`portfolio_id`) REFERENCES `quant_db`.`portfolios`    (`id`),
  CONSTRAINT `fk_portfolio_items_stocks`
    FOREIGN KEY (`stock_id`)     REFERENCES `quant_db`.`stocks` (`id`)
) ENGINE = InnoDB;

-- -----------------------------------------------------
-- price_histories
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `quant_db`.`price_histories` (
  `id`          BIGINT        NOT NULL AUTO_INCREMENT,
  `stock_id`    BIGINT        NOT NULL,
  `date`        DATE          NOT NULL,
  `open_price`  DECIMAL(15,2) NOT NULL,
  `close_price` DECIMAL(15,2) NOT NULL,
  `high_price`  DECIMAL(15,2) NOT NULL,
  `low_price`   DECIMAL(15,2) NOT NULL,
  `volume`      BIGINT        NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `idx_stock_date` (`stock_id` ASC, `date` ASC),
  CONSTRAINT `fk_price_histories_stocks`
    FOREIGN KEY (`stock_id`) REFERENCES `quant_db`.`stocks` (`id`)
) ENGINE = InnoDB;

-- -----------------------------------------------------
-- trades
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `quant_db`.`trades` (
  `id`                BIGINT        NOT NULL AUTO_INCREMENT,
  `portfolio_item_id` BIGINT        NOT NULL,
  `trade_type`        VARCHAR(20)   NOT NULL,   -- '매수' or '매도'
  `price`             DECIMAL(15,2) NOT NULL,
  `quantity`          INT           NOT NULL,
  `trade_date`        DATETIME      NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_trades_portfolio_item` (`portfolio_item_id` ASC),
  CONSTRAINT `fk_trades_portfolio_items`
    FOREIGN KEY (`portfolio_item_id`) REFERENCES `quant_db`.`portfolio_items` (`id`)
) ENGINE = InnoDB;

-- -----------------------------------------------------
-- stock_metrics   (calculate_returns.py 결과)
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `quant_db`.`stock_metrics` (
  `id`                BIGINT NOT NULL AUTO_INCREMENT,
  `stock_id`          BIGINT NOT NULL,
  `date`              DATE   NOT NULL,
  `daily_return`      DOUBLE,
  `cum_return_30d`    DOUBLE,
  `cum_return_90d`    DOUBLE,
  `cum_return_1y`     DOUBLE,
  `annual_volatility` DOUBLE,
  `sharpe_ratio`      DOUBLE,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `idx_stock_metrics` (`stock_id` ASC, `date` ASC),
  CONSTRAINT `fk_stock_metrics_stocks`
    FOREIGN KEY (`stock_id`) REFERENCES `quant_db`.`stocks` (`id`)
) ENGINE = InnoDB;

-- -----------------------------------------------------
-- stock_classification   (DB-06 분류 결과 / DB-09 전략 매핑에 사용)
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `quant_db`.`stock_classification` (
  `id`            BIGINT       NOT NULL AUTO_INCREMENT,
  `stock_id`      BIGINT       NOT NULL,
  `strategy_type` VARCHAR(50)  NOT NULL,
  -- TREND_FOLLOWING / MEAN_REVERSION / MOMENTUM / LOW_VOLATILITY / VOLATILITY_BREAKOUT / UNCLASSIFIED
  `score`         DECIMAL(5,2) NOT NULL,
  `classified_at` DATETIME     NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `idx_stock_classification` (`stock_id` ASC),
  CONSTRAINT `fk_classification_stocks`
    FOREIGN KEY (`stock_id`) REFERENCES `quant_db`.`stocks` (`id`)
) ENGINE = InnoDB;

-- -----------------------------------------------------
-- technical_indicators   (DB-10 매매 시그널에서 직접 조회)
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `quant_db`.`technical_indicators` (
  `id`             BIGINT    NOT NULL AUTO_INCREMENT,
  `stock_id`       BIGINT    NOT NULL,
  `date`           DATE      NOT NULL,
  `ma_5`           DOUBLE,
  `ma_20`          DOUBLE,
  `ma_60`          DOUBLE,
  `ma_120`         DOUBLE,
  `rsi_14`         DOUBLE,
  `rsi_overbought` TINYINT(1),
  `rsi_oversold`   TINYINT(1),
  `macd`           DOUBLE,
  `macd_signal`    DOUBLE,
  `macd_hist`      DOUBLE,
  `bb_upper`       DOUBLE,
  `bb_mid`         DOUBLE,
  `bb_lower`       DOUBLE,
  `bb_width`       DOUBLE,
  `bb_pct_b`       DOUBLE,
  `atr_14`         DOUBLE,
  `adx_14`         DOUBLE,
  `vol_ma_20`      DOUBLE,
  `vwap_20`        DOUBLE,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `idx_technical_indicators` (`stock_id` ASC, `date` ASC),
  CONSTRAINT `fk_technical_indicators_stocks`
    FOREIGN KEY (`stock_id`) REFERENCES `quant_db`.`stocks` (`id`)
) ENGINE = InnoDB;

-- -----------------------------------------------------
-- trading_signals   (daily_screener.py 결과 / BE팀이 읽어서 API 제공)
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `quant_db`.`trading_signals` (
  `id`            BIGINT        NOT NULL AUTO_INCREMENT,
  `stock_id`      BIGINT        NOT NULL,
  `ticker`        VARCHAR(50)   NOT NULL,   -- 비정규화 유지 (BE 조회 성능)
  `strategy_type` VARCHAR(50)   NOT NULL,
  `action`        VARCHAR(50)   NOT NULL,
  -- '신규 매수 진입' / '상한가 도달 (매수 보류)' / '전량 매도 청산'
  -- '50% 부분 익절' / '과열 익절 청산' / '긴급 손절'
  `signal_value`  DOUBLE        NOT NULL,   -- 1.0 / -0.5 / -1.0 / -1.5 / -2.0
  `close_price`   DECIMAL(15,2) NOT NULL,
  `signal_date`   DATE          NOT NULL,
  `created_at`    DATETIME      NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_trading_signals_date`   (`signal_date` ASC),
  INDEX `idx_trading_signals_ticker` (`ticker` ASC),
  CONSTRAINT `fk_trading_signals_stocks`
    FOREIGN KEY (`stock_id`) REFERENCES `quant_db`.`stocks` (`id`)
) ENGINE = InnoDB;

-- -----------------------------------------------------
-- portfolio_weights   (optimize_weight.py 결과)
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `quant_db`.`portfolio_weights` (
  `id`                BIGINT        NOT NULL AUTO_INCREMENT,
  `portfolio_item_id` BIGINT        NOT NULL,
  `weight`            DECIMAL(10,6) NOT NULL,   -- 비중 합계 = 1.0
  `risk_level`        INT           NOT NULL,   -- 1(공격형) ~ 5(안정형)
  `calculated_at`     DATETIME      NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_portfolio_weights_item` (`portfolio_item_id` ASC),
  CONSTRAINT `fk_portfolio_weights_items`
    FOREIGN KEY (`portfolio_item_id`) REFERENCES `quant_db`.`portfolio_items` (`id`)
) ENGINE = InnoDB;

-- -----------------------------------------------------
-- backtest_results
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `quant_db`.`backtest_results` (
  `id`            BIGINT      NOT NULL AUTO_INCREMENT,
  `stock_id`      BIGINT      NOT NULL,
  `strategy_type` VARCHAR(50) NOT NULL,
  `start_date`    DATE        NOT NULL,
  `end_date`      DATE        NOT NULL,
  `total_return`  DOUBLE      NOT NULL,
  `buy_hold_return`  DOUBLE,
  `buy_hold_mdd`     DOUBLE,
  `buy_hold_sharpe`  DOUBLE,
  `excess_return`    DOUBLE,
  `annual_return` DOUBLE      NOT NULL,
  `mdd`           DOUBLE      NOT NULL,
  `sharpe_ratio`  DOUBLE,
  `win_rate`      DOUBLE,
  `trade_count`   INT         NOT NULL,
  `created_at`    DATETIME    NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `idx_backtest_stock` (`stock_id`, `strategy_type`, `start_date`, `end_date`),
  CONSTRAINT `fk_backtest_results_stocks`
    FOREIGN KEY (`stock_id`) REFERENCES `quant_db`.`stocks` (`id`)
) ENGINE = InnoDB;

SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;