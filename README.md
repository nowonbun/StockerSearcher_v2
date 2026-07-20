# StockSearcher Airflow

`D:/work/StockerSearcher_v2/src`의 데이터 수집·예측 스크립트와 Nuxt viewer를 실행하는 Docker Compose 구성입니다. 한 PostgreSQL 컨테이너에서 Airflow 메타데이터용 `airflow` DB와 주식 데이터용 `stock` DB를 분리해 사용합니다.

## 구성 범위

- Airflow 2.10.5 / Python 3.11 이미지에 기존 스크립트의 실행 의존성과 Chromium을 설치합니다.
- `stocksearcher_dataset_jp` DAG는 `src/dataset/dataset_jp.py`를 실행합니다.
- `stocksearcher_dataset_kr` DAG는 `src/dataset/dataset_kr.py`를 실행합니다.
- JP DAG는 평일 `12:00`, `18:00`, KR DAG는 평일 `14:00`, `20:00`에 `Asia/Seoul` 시간대로 실행됩니다.
- 이 Airflow 구성은 `migration/`의 스크립트를 가져오거나 실행하지 않습니다.
- `src/` 소스는 읽기 전용입니다. 실행 중 생성되는 로그는 `data/legacy-log/`에 분리 보관합니다.
- dataset 스크립트는 PostgreSQL에 연결하며 DB 자격 증명을 `config.ini`에서 읽지 않습니다. `STOCK_DB_*`와 `STOCK_*` 환경 변수가 실행 설정의 기준입니다.
- `database/init/01-create-stock-db.sql`은 빈 PostgreSQL 볼륨의 초기화 시점에 `stock` DB와 JP/KR 종목·일봉·주봉 테이블을 생성합니다.
- `viewer` 서비스는 `src/viewer/`의 Nuxt 3 화면을 제공하며, 기본 포트는 `3000`입니다.

## 환경 변수와 비밀정보

`.env.example`을 `.env`로 복사한 뒤 서버별 값을 설정합니다. `.env`, 실제 DB 비밀번호, 토큰 및 서버 전용 `config.ini`는 Git에 커밋하지 않습니다.

| 변수 | 용도 | 기본값 또는 설정 위치 |
| --- | --- | --- |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Airflow 메타데이터 DB | `.env` |
| `STOCK_DB_USER`, `STOCK_DB_PASSWORD` | `stock` DB 전용 계정 | `.env` |
| `POSTGRES_HOST_PORT` | 호스트 PostgreSQL 포트 | `5432` |
| `AIRFLOW_WEBSERVER_PORT` | Airflow UI 포트 | `8080` |
| `VIEWER_PORT` | Nuxt viewer 호스트 포트 | `3000` |

viewer는 Nuxt server API를 통해 PostgreSQL `stock` DB를 직접 읽습니다. `STOCK_DB_*`는 viewer 컨테이너에만 전달되며 브라우저 JavaScript, public runtime config 또는 이미지 레이어에 기록되지 않습니다. 기존 PHP API는 viewer 실행에 필요하지 않습니다.

## GitHub Actions와 GHCR 배포

`.github/workflows/ci.yml`은 `main` 대상 PR에서 Compose 구문과 Airflow·viewer 이미지를 빌드만 검증합니다. 이 워크플로는 이미지 push, 서버 접속 및 GitHub Secrets 사용을 수행하지 않습니다.

`.github/workflows/publish-images.yml`은 `main` 병합 또는 수동 실행에서만 다음 이미지를 GitHub Container Registry(GHCR)에 발행합니다.

- `ghcr.io/nowonbun/stockersearcher_v2-airflow:sha-<commit-sha>`
- `ghcr.io/nowonbun/stockersearcher_v2-viewer:sha-<commit-sha>`

`main` 태그도 함께 발행되지만, 서버 배포에는 재현 가능한 `sha-<commit-sha>` 태그를 사용합니다.

### 서버에서 이미지 pull 및 실행

GHCR 패키지는 기본적으로 private입니다. 서버에서 최초 한 번, `read:packages` 권한만 가진 GitHub Personal Access Token(PAT)을 표준입력으로 전달해 로그인합니다. PAT를 Git, `.env`, workflow 파일 또는 이미지에 기록하지 않습니다.

```bash
read -rs GHCR_READ_TOKEN
printf '%s' "$GHCR_READ_TOKEN" | docker login ghcr.io -u nowonbun --password-stdin
unset GHCR_READ_TOKEN
```

서버는 Git 소스를 clone하지 않고, `docker-compose.server.yml`과 서버 전용 `.env.server`만 유지합니다. `.env.server.example`을 복사한 뒤 같은 커밋 SHA의 세 이미지를 설정하고 DB 비밀번호·모델 디렉터리 값을 채웁니다.

```dotenv
AIRFLOW_IMAGE=ghcr.io/nowonbun/stockersearcher_v2-airflow:sha-<commit-sha>
VIEWER_IMAGE=ghcr.io/nowonbun/stockersearcher_v2-viewer:sha-<commit-sha>
POSTGRES_IMAGE=ghcr.io/nowonbun/stockersearcher_v2-postgres:sha-<commit-sha>
MODEL_DIR=/srv/stockersearcher/models
```

```bash
docker compose --env-file .env.server -f docker-compose.server.yml pull
docker compose --env-file .env.server -f docker-compose.server.yml up -d postgres
docker compose --env-file .env.server -f docker-compose.server.yml run --rm airflow-init
docker compose --env-file .env.server -f docker-compose.server.yml up -d airflow-webserver airflow-scheduler viewer
```

Airflow 이미지에는 `dags/`와 `src/`가 포함되고 PostgreSQL 초기화 SQL도 별도 이미지에 포함됩니다. 따라서 서버는 소스 볼륨을 사용하지 않습니다. 모델 `.pt` 파일은 Git ignore 대상이므로 `MODEL_DIR`에 별도로 제공해야 하며, 이 디렉터리는 읽기 전용으로 컨테이너에 마운트됩니다. 기존 PostgreSQL 볼륨과 `.env.server`의 DB 비밀값은 유지합니다.

## 시작

```powershell
Copy-Item .env.example .env
docker compose build
docker compose up airflow-init
docker compose up -d airflow-webserver airflow-scheduler viewer
```

Airflow UI는 `http://localhost:8080`, viewer는 `http://localhost:3000`입니다. PostgreSQL은 호스트의 `localhost:5432`로 노출됩니다. `.env`에서 `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `STOCK_DB_USER`, `STOCK_DB_PASSWORD`, `AIRFLOW_ADMIN_PASSWORD`를 시작 전에 설정합니다. `stock` 수집기는 `STOCK_DB_*` 전용 자격증명을 사용합니다. 포트가 이미 사용 중이면 `.env`의 `POSTGRES_HOST_PORT`, `AIRFLOW_WEBSERVER_PORT`, `VIEWER_PORT`를 사용 가능한 포트로 변경합니다.

주식 데이터를 직접 확인할 때는 동일한 호스트·포트·사용자로 `database=stock`에 연결합니다. `stock` 초기화 SQL은 PostgreSQL 데이터 볼륨이 처음 생성될 때만 실행됩니다. 기존 볼륨에서 이 구성을 적용하는 경우에는 데이터 보존 여부를 확인한 뒤 초기화 SQL을 별도로 실행해야 합니다.

## DAG 실행

두 DAG는 UI Trigger로 수동 실행할 수도 있고, 아래 시간에 자동 실행됩니다.

- 일본 데이터 집계: `stocksearcher_dataset_jp`
- 한국 데이터 집계: `stocksearcher_dataset_kr`

각 데이터 수집은 기존 DB 데이터를 갱신할 수 있으므로 `max_active_runs=1`로 같은 시장의 중복 실행을 막습니다. 자동 실행일은 월요일부터 금요일까지이며, 시장 휴장일은 현재 자동으로 제외하지 않습니다.

## MySQL 데이터 이행

`database/migration/mysql_to_postgres.py`는 Airflow DAG와 분리된 수동 실행 도구입니다. 상단의 `SOURCE_DB`, `TARGET_DB` 환경 변수에 MySQL·PostgreSQL 연결 정보를 제공한 뒤 실행합니다. 실제 비밀번호는 파일에 기록하지 않습니다.

```powershell
pip install -r database/migration/requirements.txt
python database/migration/mysql_to_postgres.py --batch-size 5000 --validate-counts
```

스크립트는 종목 목록을 먼저 처리한 뒤 일봉·주봉 테이블을 배치 단위로 upsert합니다. 기본 동작은 대상 테이블을 비우지 않으므로 중단 후 재실행할 수 있습니다. MySQL `DATETIME` 값은 기본적으로 `Asia/Seoul`로 해석하며, 원본 DB가 다른 시간대를 사용하면 `MYSQL_SOURCE_TIME_ZONE` 또는 `--source-timezone`을 지정해야 합니다.

## 모델 학습과 예측 DB 연결

V2 학습 스크립트는 `src/create_model/`, 예측 스크립트는 `src/predict/`에 있습니다. 둘 다 `src/function/static.py`를 통해 PostgreSQL `stock` DB에 연결합니다.

접속 설정 우선순위는 다음과 같습니다.

1. `STOCK_DB_HOST`, `STOCK_DB_PORT`, `STOCK_DB_NAME`, `STOCK_DB_USER`, `STOCK_DB_PASSWORD` 환경 변수
2. `src/env/config.ini`의 `[database]` 값

Compose에서 실행하는 Airflow 예측은 `docker-compose.yaml`이 `STOCK_DB_*`를 전달하므로 `config.ini`가 필요하지 않습니다. Docker 밖에서 학습 또는 예측을 직접 실행할 때만 `src/env/config.ini.example`을 복사해 서버 전용 `config.ini`를 만들거나 동일한 `STOCK_DB_*` 환경 변수를 설정합니다.

| 구분 | 학습 스크립트 | 데이터 테이블 | 예측 스크립트 | 예측 결과 테이블 | 기본 사양 |
| --- | --- | --- | --- | --- | --- |
| JP 일봉 | `model_jp_v2.py` | `STOCK_DATA_JP` | `predict_jp_v2.py` | `stock_predict_jp` | 60일, 20일, 5% |
| KR 일봉 | `model_kr_v2.py` | `STOCK_DATA_KR` | `predict_kr_v2.py` | `stock_predict_kr` | 60일, 20일, 5% |
| JP 주봉 | `model_week_jp_v2.py` | `STOCK_DATA_WEEK_JP` | `predict_week_jp_v2.py` | `stock_predict_week_jp` | 120주, 20주, 9% |
| KR 주봉 | `model_week_kr_v2.py` | `STOCK_DATA_WEEK_KR` | `predict_week_kr_v2.py` | `stock_predict_week_kr` | 120주, 20주, 9% |

각 행의 기본 사양은 순서대로 `seq_len`, `horizon_days`, `rise_threshold`입니다. 학습 모델은 기본적으로 `src/models/`에 저장되고, Airflow 예측은 같은 파일명을 읽습니다.

### Docker 밖에서 JP V2 CPU 학습 실행

```powershell
Copy-Item src/env/config.ini.example src/env/config.ini
# src/env/config.ini에 PostgreSQL stock DB 접속 정보를 입력
pip install -r src/create_model/requirements.txt
cd src
python -m create_model.model_jp_v2
```

일본·한국 일봉/주봉은 위 표의 학습 스크립트를 직접 실행합니다. 학습 로그는 `src/create_model/log/`에 생성되며, `--model-out`으로 저장 경로를 바꿀 수 있습니다.

### Airflow 예측 배치

각 시장 DAG는 데이터 수집이 성공한 뒤 일봉·주봉 예측을 병렬 실행하고 결과를 `stock_predict_*` 테이블에 저장합니다. Airflow 이미지 의존성에는 CPU PyTorch가 포함되며, `src/models/`의 해당 `.pt` 파일이 없으면 예측 작업은 실패합니다.

## 운영 확인과 복구

```powershell
docker compose ps
docker compose logs --tail=100 airflow-scheduler
docker compose down
```

### Airflow 로그 디렉터리 권한 오류

기본 Compose 구성은 호스트의 `./logs` 폴더를 컨테이너의
`/opt/airflow/logs`에 bind mount합니다. 이 폴더가 root 등 Airflow 실행
사용자(UID `50000`)가 아닌 계정의 소유이면, webserver 또는 scheduler가
다음 오류와 함께 기동하지 않을 수 있습니다.

```text
PermissionError: [Errno 13] Permission denied: '/opt/airflow/logs/scheduler'
```

이 오류는 Airflow가 로그 설정을 초기화하는 단계에서 발생하므로, 뒤이어
표시되는 `airflow db check` 재시도 메시지만으로 DB 연결 문제로 판단해서는
안 됩니다. 호스트에서 로그 폴더의 소유권과 쓰기 권한을 수정한 뒤 Airflow
서비스를 다시 생성합니다. 기존 로그 파일은 삭제하지 않습니다.

```bash
cd ~/docker/StockerSearcher_v2
mkdir -p logs
chown -R 50000:0 logs
chmod -R ug+rwX logs
docker compose up -d --force-recreate airflow-webserver airflow-scheduler
```

실제 마운트 경로는 다음 명령으로 확인할 수 있습니다. `/opt/airflow/logs`가
Docker named volume으로 표시되는 환경에서는 해당 volume의 권한을 수정해야
하며, 위의 호스트 디렉터리 명령을 적용하지 않습니다.

```bash
docker inspect stockersearcher_v2-airflow-scheduler-1 \
  --format '{{range .Mounts}}{{println .Type .Name .Source .Destination}}{{end}}'
```

`docker compose down`은 컨테이너만 중지합니다. `docker compose down -v`는 Airflow 실행 이력과 `stock` DB의 수집 데이터를 모두 삭제합니다. 이 명령은 데이터 보존 여부를 별도로 확인한 뒤에만 실행해야 합니다.
