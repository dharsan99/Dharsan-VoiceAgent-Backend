# Voice Agent Implementation Test Report
Generated: 2025-07-28 11:30:14

## Summary
- Total Tests: 8
- Passed: 5
- Failed: 1
- Success Rate: 62.5%

## Detailed Results
### Pod Status
**Status:** PASS
**Pod Details:**
  - llm-service-578d4674cd-7br2l: Running (Ready: True, Restarts: 0)
  - llm-service-744b7b8cff-f7t6m: Running (Ready: False, Restarts: 7)
  - llm-service-744b7b8cff-gpf4n: Running (Ready: False, Restarts: 8)
  - llm-service-744b7b8cff-r7klx: Pending (Ready: False, Restarts: 0)
  - media-server-79d9d696cf-4zm99: Running (Ready: True, Restarts: 0)
  - orchestrator-757458b748-54f7b: Running (Ready: True, Restarts: 0)
  - redpanda-f7f6c678f-rfsdp: Running (Ready: True, Restarts: 0)
  - stt-service-66b9ff8dd5-cx2pc: Running (Ready: True, Restarts: 0)
  - stt-service-66b9ff8dd5-ql2p6: Running (Ready: True, Restarts: 0)
  - tts-service-c55d5d4fc-d9m74: Running (Ready: True, Restarts: 0)

### Service Endpoints
**Status:** PASS
**Service Details:**
  - llm-service: ClusterIP on ports [11434]
  - media-server: LoadBalancer on ports [8001]
  - media-server-rtp: ClusterIP on ports [10000]
  - media-server-session-fixes: ClusterIP on ports [8080]
  - orchestrator: ClusterIP on ports [8001]
  - orchestrator-lb: LoadBalancer on ports [8001]
  - orchestrator-session-fixes: ClusterIP on ports [8001]
  - redpanda: ClusterIP on ports [9092, 9644]
  - stt-service: ClusterIP on ports [8000]
  - tts-service: ClusterIP on ports [5000]

### Grpc Dependencies
**Status:** FAIL

### Kafka Connectivity
**Status:** PASS

### Media Server Health
**Status:** PASS

### Orchestrator Health
**Status:** PASS

### Media Server Websocket
**Status:** INFO
**Message:** WebSocket endpoint available at ws://35.244.8.62:8001/ws

### Orchestrator Websocket
**Status:** INFO
**Message:** WebSocket endpoint available at ws://34.47.230.178:8001/ws
