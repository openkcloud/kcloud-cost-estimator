# Logger Module - Scheduling Decision Tracking & Event Logging

**스케줄링 결정 과정 추적 및 최적화 이벤트 로깅 모듈**

## 📋 주요 기능

### 📊 스케줄링 결정 과정 로깅
- **의사결정 추적**: 스케줄러가 내린 모든 결정 과정 기록
- **비용 계산 로그**: 전력 기반 비용 계산 과정 상세 기록
- **워크로드 배치**: 어떤 워크로드가 왜 특정 클러스터에 배치되었는지 추적
- **성능 메트릭**: 스케줄링 지연시간, 처리량 등 KPI 측정

### 🔄 최적화 이벤트 추적  
- **재배치 이벤트**: 워크로드 재배치 시점, 이유, 결과 기록
- **클러스터 재구성**: Magnum 클러스터 생성/삭제/스케일링 이벤트
- **정책 변경**: 운용 정책 적용 및 변경 이력
- **비효율 감지**: 자원 사용 비효율 상태 감지 및 알람

### 📈 감사 및 분석
- **운용 비용 변화**: 정책 전환 전후 비용 변화 추적
- **효율성 분석**: 최적화 효과 측정 및 보고서 생성
- **SLA 준수**: 응답시간, 가용성 등 SLA 지표 모니터링
- **규정 준수**: 감사 로그 및 컴플라이언스 보고서

## 🏗 아키텍처

```
모든 kcloud 모듈 → logger → 구조화된 로그 → 분석/대시보드
    ↓                ↓           ↓              ↓
스케줄링 이벤트   이벤트 추적   InfluxDB     Grafana 대시보드
재배치 결정      로그 처리     PostgreSQL   감사 보고서
비용 계산        감사 관리     Elasticsearch 알람 시스템
```

## 🎯 추적 대상 이벤트

### **1. 스케줄링 이벤트**
```json
{
  "event_type": "scheduling_decision",
  "timestamp": "2025-01-15T10:30:00Z",
  "scheduler": "kcloud-meta-scheduler",
  "workload": {
    "id": "ml-training-job-123",
    "type": "ml_training",
    "requirements": {
      "cpu": 8,
      "memory": "32Gi", 
      "gpu": 2,
      "power_budget": 1500
    }
  },
  "decision": {
    "selected_cluster": "gpu-cluster-01",
    "reason": "최적 전력 효율성",
    "cost_calculation": {
      "estimated_power_watts": 1200,
      "estimated_cost_per_hour": 15.60,
      "alternatives": [
        {"cluster": "gpu-cluster-02", "cost": 18.20},
        {"cluster": "hybrid-cluster-01", "cost": 22.40}
      ]
    }
  },
  "execution_time_ms": 245
}
```

### **2. 재배치 이벤트**
```json
{
  "event_type": "workload_relocation",
  "timestamp": "2025-01-15T14:45:00Z",
  "trigger": "power_efficiency_optimization",
  "workload": "inference-service-456",
  "migration": {
    "from_cluster": "gpu-cluster-02",
    "to_cluster": "npu-cluster-01",
    "reason": "NPU가 추론 작업에 더 효율적",
    "power_saving_watts": 300,
    "cost_saving_per_hour": 4.20
  },
  "migration_time_seconds": 45,
  "downtime_seconds": 2
}
```

### **3. 클러스터 재구성 이벤트**
```json
{
  "event_type": "cluster_reconfiguration",
  "timestamp": "2025-01-15T16:00:00Z",
  "action": "cluster_created",
  "cluster": {
    "id": "magnum-cluster-789",
    "name": "npu-inference-cluster",
    "type": "npu_optimized",
    "node_count": 3,
    "estimated_cost_per_hour": 12.50
  },
  "trigger": {
    "workload_queue_length": 15,
    "existing_cluster_utilization": 95,
    "expected_efficiency_gain": "25%"
  }
}
```

### **4. 비효율 감지 이벤트**
```json
{
  "event_type": "inefficiency_detected",
  "timestamp": "2025-01-15T18:20:00Z",
  "severity": "medium",
  "inefficiency": {
    "type": "idle_cluster",
    "cluster": "cpu-cluster-03",
    "utilization": 8,
    "idle_duration_hours": 6,
    "wasted_cost_estimate": 75.60
  },
  "recommended_action": "cluster_consolidation",
  "auto_action_taken": false
}
```

## 🔧 로그 수집 방법

### **구조화된 로깅**
- **JSON 형식**: 모든 로그를 JSON으로 구조화
- **표준화된 스키마**: 이벤트 타입별 일관된 스키마
- **메타데이터 태깅**: 검색 및 분석을 위한 태그 자동 추가

### **다양한 수집 방법**
```python
# 1. 직접 API 호출
logger_client.log_scheduling_decision(
    workload_id="ml-job-123",
    cluster_id="gpu-cluster-01", 
    cost_calculation=cost_data,
    execution_time=245
)

# 2. 이벤트 스트리밍 (Redis/Kafka)
event_publisher.publish("scheduling_events", event_data)

# 3. HTTP 웹훅
requests.post("http://logger:8007/events/scheduling", json=event_data)

# 4. 파일 기반 로그 수집 (Fluent Bit/Filebeat)
# 표준 로그 파일을 logger가 수집
```

## 📊 API 엔드포인트

```bash
# 이벤트 로깅
POST /events/scheduling          # 스케줄링 결정 로그
POST /events/relocation         # 재배치 이벤트 로그  
POST /events/cluster            # 클러스터 재구성 로그
POST /events/inefficiency       # 비효율성 감지 로그

# 이벤트 조회
GET /events                     # 전체 이벤트 목록
GET /events/{event_type}        # 타입별 이벤트 조회
GET /events/workload/{workload_id} # 워크로드별 이벤트 추적

# 분석 및 보고서
GET /analytics/scheduling-performance  # 스케줄링 성능 분석
GET /analytics/cost-efficiency         # 비용 효율성 분석  
GET /analytics/sla-compliance          # SLA 준수 현황
GET /reports/audit                     # 감사 보고서 생성

# 실시간 모니터링
GET /stream/events               # 실시간 이벤트 스트리밍 (SSE)
GET /alerts/active               # 활성 알람 목록
POST /alerts/rules               # 알람 규칙 설정
```

## 🧪 사용 예시

### **스케줄링 결정 로깅**
```python
from logger.event_tracker import EventTracker

tracker = EventTracker()

# 스케줄링 결정 시
await tracker.log_scheduling_decision(
    workload_id="ml-training-job-456",
    selected_cluster="gpu-cluster-02",
    alternatives=[
        {"cluster": "gpu-cluster-01", "cost": 18.50},
        {"cluster": "hybrid-cluster", "cost": 22.30}
    ],
    cost_calculation={
        "power_watts": 1400,
        "cost_per_hour": 16.80,
        "efficiency_score": 0.85
    },
    execution_time_ms=180
)
```

### **재배치 이벤트 추적**
```python
# 워크로드 재배치 시
await tracker.log_workload_relocation(
    workload_id="inference-service-789",
    from_cluster="gpu-cluster-01",
    to_cluster="npu-cluster-01", 
    trigger="power_optimization",
    metrics={
        "power_saving_watts": 250,
        "cost_saving_per_hour": 3.75,
        "migration_time_seconds": 35,
        "downtime_seconds": 1
    }
)
```

### **비효율성 감지 및 알람**
```python
# 비효율 상태 감지 시
await tracker.log_inefficiency(
    inefficiency_type="idle_cluster",
    resource_id="cpu-cluster-05",
    severity="high",
    metrics={
        "utilization_percentage": 5,
        "idle_duration_hours": 12,
        "wasted_cost_estimate": 150.40
    },
    recommended_action="cluster_shutdown"
)
```

### **분석 쿼리**
```python
from logger.log_processor import LogAnalyzer

analyzer = LogAnalyzer()

# 스케줄링 성능 분석
performance = await analyzer.analyze_scheduling_performance(
    time_range="7d",
    metrics=["avg_latency", "success_rate", "cost_efficiency"]
)

# 비용 절감 효과 분석
cost_analysis = await analyzer.analyze_cost_efficiency(
    time_range="30d",
    compare_baseline=True
)

print(f"평균 스케줄링 지연시간: {performance['avg_latency_ms']}ms")
print(f"월간 비용 절감액: ${cost_analysis['monthly_savings']}")
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
kubectl apply -f deployment/logger.yaml

# 로그 수집 확인
curl http://localhost:8007/health
curl http://localhost:8007/events?limit=10
```

## 📈 성능 목표

- **SFR.OPT.013**: 스케줄링 결정 과정 로그 저장 및 제공 ✅
- **SFR.OPT.014**: 재배치/재구성 최적화 이벤트 이력 제공 ✅  
- **SNR.PF.010**: 스케줄링 지연시간 30% 감소 모니터링 ✅
- **로그 처리 성능**: 초당 1000개 이벤트 처리 가능
- **쿼리 응답시간**: 복잡한 분석 쿼리도 5초 이내 응답