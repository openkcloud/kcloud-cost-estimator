# Collector Module - Kepler Power Data Collection

**Kepler 연동 전력 데이터 수집 모듈**

## 📋 주요 기능

### 🔌 Kepler 메트릭 수집
- **실시간 전력 데이터**: 컨테이너/노드별 전력 소비량
- **GPU/NPU 전력 모니터링**: AI 가속기 특화 메트릭
- **워크로드별 전력 프로파일링**: 작업 유형별 전력 패턴 분석

### 📊 데이터 처리 파이프라인
- **메트릭 정규화**: Kepler raw data → 표준화된 전력 메트릭
- **비용 환산**: 전력 소비량 → 운용 비용 계산
- **실시간 스트리밍**: Redis/InfluxDB를 통한 데이터 전송

## 🏗 아키텍처

```
Kepler Exporter (Prometheus) 
    ↓ HTTP/Prometheus API
KeplerClient → PowerMetrics → DataProcessor
    ↓                ↓             ↓
  수집          정규화/집계      비용환산
    ↓                ↓             ↓
Redis Queue ← InfluxDB ← analyzer/predictor 모듈
```

## 🚀 핵심 메트릭

### Kepler 메트릭 매핑
```yaml
power_metrics:
  container_power:
    - kepler_container_joules_total       # 컨테이너 총 전력
    - kepler_container_cpu_joules_total   # CPU 전력
    - kepler_container_gpu_joules_total   # GPU 전력
    - kepler_container_other_joules_total # 기타 하드웨어
  
  node_power:
    - kepler_node_platform_joules_total   # 노드 플랫폼 전력
    - kepler_node_components_joules_total # 노드 컴포넌트별
  
  workload_classification:
    - pod_name, namespace, workload_type
    - container_name, image, command
```

### 비용 환산 공식
```python
# collector/src/power_metrics/cost_calculator.py
def calculate_power_cost(power_watts, duration_hours):
    electricity_cost = power_watts * (duration_hours / 1000) * ELECTRICITY_RATE
    cooling_overhead = electricity_cost * COOLING_FACTOR
    carbon_cost = (power_watts * duration_hours / 1000) * CARBON_RATE
    return electricity_cost + cooling_overhead + carbon_cost
```

## 🔧 설정

### 환경변수
```bash
# Kepler 연동
KEPLER_PROMETHEUS_URL=http://prometheus:9090
KEPLER_METRICS_INTERVAL=30s

# 비용 계산
ELECTRICITY_RATE=0.12  # $/kWh
COOLING_FACTOR=1.3     # 냉각 오버헤드
CARBON_RATE=0.05       # $/kg CO2

# 데이터 저장
REDIS_URL=redis://localhost:6379
INFLUXDB_URL=http://influxdb:8086
INFLUXDB_BUCKET=power_metrics
```

## 📊 API 엔드포인트

```bash
# 실시간 전력 데이터
GET /power/current?workload=ml-training
GET /power/containers?namespace=kcloud-workloads

# 비용 분석 데이터
GET /cost/hourly?start=2025-01-01T00:00:00Z
GET /cost/workload/{workload_id}

# 전력 프로파일
GET /profile/workload-types
POST /profile/classify
```

## 🧪 사용 예시

```python
from collector.kepler_client import KeplerClient
from collector.power_metrics import PowerCalculator

# Kepler 클라이언트 초기화
client = KeplerClient(prometheus_url="http://prometheus:9090")

# 실시간 전력 데이터 수집
power_data = client.get_container_power_metrics(
    namespace="kcloud-workloads",
    time_range="5m"
)

# 비용 계산
calculator = PowerCalculator()
cost = calculator.calculate_total_cost(power_data)
print(f"워크로드 운용 비용: ${cost:.2f}/hour")
```

## 🚀 배포

```bash
# 로컬 개발
make install
make test
make run

# Docker 실행
make docker-build
make docker-run

# K8s 배포
kubectl apply -f deployment/collector.yaml
```