# 로컬 데이터베이스 (MySQL) 세팅 가이드

본 프로젝트는 로컬 개발 환경에서 Docker를 활용하여 MySQL 데이터베이스를 구동합니다. 복잡한 설치 과정 없이 아래 명령어를 통해 즉시 DB 환경을 구축할 수 있습니다.

## 사전 요구 사항 (Prerequisites)

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)이 설치되어 있고 실행 중이어야 합니다.

## DB 구동 방법

**1. Docker Compose 실행**
프로젝트 최상단(또는 `docker-compose.yml` 파일이 있는 위치)에서 터미널을 열고 아래 명령어를 실행합니다.
```bash
docker-compose up -d
```
(💡 -d 옵션은 백그라운드 실행을 의미합니다. 터미널을 꺼도 DB는 계속 돌아갑니다!)

**2. 컨테이너 구동 확인**
```Bash
docker ps
```
목록에 quant_mysql 컨테이너가 정상적으로 실행 중인지 확인합니다.

## 데이터베이스 접속 정보

구동된 로컬 DB에 접속하기 위한 정보입니다. (MySQL Workbench, DBeaver, 또는 Spring Boot application.yml 세팅 시 활용하세요)
- Host: 127.0.0.1 (또는 localhost)
- Port: 3306 (만약 충돌로 인해 3307로 변경했다면 3307로 맞춰주세요)
- Database: quant_db
- Username: quant_user
- Password: .env 파일에 설정한 비밀번호 (보안상 Git에 올라가지 않으므로 팀장에게 문의)

## DB 종료 및 초기화

**DB 컨테이너 종료 (데이터는 유지됨)**
```Bash
docker-compose down
```
DB 컨테이너 종료 및 볼륨(데이터) 완전 삭제 (초기화 시에만 사용!)

```Bash
docker-compose down -v
```

## 주요 테이블 스키마 참고

(상세 데이터는 파이썬 수집 파이프라인을 통해 자동 적재됩니다.)
stocks: 주식 종목 기초 정보 (id, ticker, name, market)
price_histories: 일봉 주가 시계열 데이터 (date, open, close, high, low, volume, stock_id)