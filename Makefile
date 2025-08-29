# Collector Module Makefile
.PHONY: install test run docker-build docker-run clean lint format

# Python 가상환경 설정
VENV_DIR = venv
PYTHON = $(VENV_DIR)/bin/python
PIP = $(VENV_DIR)/bin/pip

# Docker 설정
IMAGE_NAME = kcloud-collector
TAG = latest

# 가상환경 생성 및 의존성 설치
install: $(VENV_DIR)/bin/activate
$(VENV_DIR)/bin/activate: requirements.txt
	python3 -m venv $(VENV_DIR)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	touch $(VENV_DIR)/bin/activate

# 개발 의존성 설치
install-dev: install
	$(PIP) install -e .
	$(PIP) install pytest pytest-cov pytest-asyncio black flake8 mypy

# 테스트 실행
test: install-dev
	$(PYTHON) -m pytest tests/ -v --cov=src --cov-report=html

# 로컬 서버 실행
run: install
	$(PYTHON) -m uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload

# 백그라운드 워커 실행 (Celery)
run-worker: install
	$(PYTHON) -m celery worker -A src.worker:celery_app --loglevel=info

# 코드 포맷팅
format: install-dev
	$(PYTHON) -m black src/ tests/
	$(PYTHON) -m isort src/ tests/

# 린트 검사
lint: install-dev
	$(PYTHON) -m flake8 src/ tests/
	$(PYTHON) -m mypy src/

# Docker 이미지 빌드
docker-build:
	docker build -t $(IMAGE_NAME):$(TAG) .

# Docker 컨테이너 실행
docker-run:
	docker run -d \
		--name kcloud-collector \
		-p 8001:8001 \
		-e KEPLER_PROMETHEUS_URL=http://prometheus:9090 \
		-e REDIS_URL=redis://localhost:6379 \
		-e INFLUXDB_URL=http://influxdb:8086 \
		$(IMAGE_NAME):$(TAG)

# Docker 컨테이너 중지 및 제거
docker-clean:
	docker stop kcloud-collector || true
	docker rm kcloud-collector || true

# Health Check
health-check:
	curl -f http://localhost:8001/health || exit 1

# 정리
clean:
	rm -rf $(VENV_DIR)
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf htmlcov
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete

# 로그 확인
logs:
	docker logs -f kcloud-collector

# 개발 모드 전체 실행
dev-up: install
	# Prometheus와 Redis가 실행 중이어야 함
	$(PYTHON) -m uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload &
	$(PYTHON) -m celery worker -A src.worker:celery_app --loglevel=info &

# 개발 환경 정리
dev-down:
	pkill -f uvicorn || true
	pkill -f celery || true