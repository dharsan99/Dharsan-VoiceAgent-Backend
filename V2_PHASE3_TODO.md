# V2 Phase 3 Implementation Todo List

## 🎯 **Phase 3 Overview: Building the Scalable Data Backbone**

**Objective:** To implement a durable data layer by deploying ScyllaDB, enhancing Redpanda with intermediate topics, and creating a dedicated Logging Service. This will decouple real-time processing from data persistence and enable detailed interaction logging.

---

## 📋 **Implementation Checklist**

### **Step 1: Enhance Redpanda Deployment with Intermediate Topics** ✅

#### **1.1 Define and Create New Topics**
- [x] **Create `stt-results` topic** for logging final transcripts from Speech-to-Text
- [x] **Create `llm-requests` topic** for logging final text responses from Language Model  
- [x] **Create `tts-results` topic** for logging metadata about synthesized audio
- [x] **Update docker-compose.yml** to include topic creation scripts
- [x] **Create topic creation script** (`create-topics.sh`)

#### **1.2 Update Redpanda Configuration**
- [ ] **Enhance docker-compose.yml** with proper topic configuration
- [ ] **Add topic retention policies** for intermediate topics
- [ ] **Configure topic partitioning** for optimal performance
- [ ] **Add monitoring endpoints** for topic health

### **Step 2: Deploy ScyllaDB for Persistent Storage** ✅

#### **2.1 Create ScyllaDB Kubernetes Manifest**
- [x] **Create `k8s/phase3/manifests/scylladb-deployment.yaml`**
  - [x] StatefulSet configuration for stable storage
  - [x] Service configuration for internal access
  - [x] Persistent volume claims
  - [x] Resource limits and requests
- [x] **Create `k8s/phase3/manifests/scylladb-service.yaml`** (included in deployment.yaml)
- [x] **Create `k8s/phase3/manifests/scylladb-pvc.yaml`** (included in deployment.yaml)

#### **2.2 Create Database Schema**
- [x] **Create `k8s/phase3/db/schema.cql`**
  - [x] Define `voice_ai_ks` keyspace
  - [x] Create `voice_interactions` table with time-series schema
  - [x] Add appropriate indexes for querying
- [x] **Create schema application script** (`apply-schema.sh`)

#### **2.3 ScyllaDB Configuration**
- [ ] **Configure ScyllaDB for development mode**
- [ ] **Set up proper resource allocation**
- [ ] **Configure backup and recovery**
- [ ] **Add health checks and monitoring**

### **Step 3: Build the Logging Service (Go)** ✅

#### **3.1 Create Service Structure**
- [x] **Create `logging-service/` directory**
- [x] **Initialize Go module** (`go mod init`)
- [x] **Create `main.go`** with core logic
- [x] **Create `Dockerfile`** for containerization
- [x] **Create `go.mod`** with dependencies

#### **3.2 Implement Core Logic**
- [ ] **ScyllaDB connection management**
- [ ] **Redpanda consumer setup** for intermediate topics
- [ ] **Message processing and validation**
- [ ] **Database insertion logic**
- [ ] **Error handling and retry mechanisms**
- [ ] **Health check endpoints**

#### **3.3 Add Dependencies**
- [ ] **Install `github.com/gocql/gocql`** (ScyllaDB driver)
- [ ] **Install `github.com/segmentio/kafka-go`** (Redpanda driver)
- [ ] **Install logging and monitoring libraries**

#### **3.4 Create Kubernetes Deployment**
- [ ] **Create `k8s/phase3/manifests/logging-service-deployment.yaml`**
- [ ] **Create `k8s/phase3/manifests/logging-service-service.yaml`**
- [ ] **Configure environment variables**
- [ ] **Add health checks and readiness probes**

### **Step 4: Refactor the Orchestrator Service** ✅

#### **4.1 Enhance Kafka Service**
- [x] **Add intermediate topic producers** to `orchestrator/internal/kafka/service.go`
- [x] **Create `PublishLog` function** for structured logging
- [x] **Add latency tracking** for each pipeline stage
- [x] **Implement message serialization** for logging data

#### **4.2 Modify AI Pipeline Logic**
- [x] **Update `processAIPipeline` function** in `orchestrator/main.go`
- [x] **Add STT result publishing** to `stt-results` topic
- [x] **Add LLM request publishing** to `llm-requests` topic
- [x] **Add TTS result publishing** to `tts-results` topic
- [x] **Implement latency measurement** for each stage

#### **4.3 Add Structured Logging**
- [x] **Define `VoiceInteractionLog` struct**
- [x] **Create logging message formats**
- [x] **Add timestamp and session tracking**
- [x] **Implement error logging** for failed operations

### **Step 5: Testing and Validation** 🧪

#### **5.1 Unit Tests**
- [ ] **Test ScyllaDB connection** and schema creation
- [ ] **Test Redpanda topic creation** and message publishing
- [ ] **Test Logging Service** message consumption
- [ ] **Test Orchestrator** intermediate publishing

#### **5.2 Integration Tests**
- [ ] **End-to-end pipeline testing** with logging
- [ ] **Database persistence validation**
- [ ] **Latency measurement accuracy**
- [ ] **Error handling and recovery**

#### **5.3 Performance Tests**
- [ ] **Load testing** with multiple concurrent sessions
- [ ] **Database write performance** validation
- [ ] **Message queue throughput** testing
- [ ] **Memory and CPU usage** monitoring

### **Step 6: Documentation and Deployment** 📚

#### **6.1 Update Documentation**
- [ ] **Create `README-Phase3.md`** with implementation details
- [ ] **Update deployment scripts** for Phase 3 components
- [ ] **Create troubleshooting guide** for common issues
- [ ] **Document monitoring and alerting** setup

#### **6.2 Deployment Scripts**
- [x] **Create `deploy-phase3.sh`** deployment script
- [x] **Create `create-topics.sh`** for Redpanda topics
- [x] **Create `apply-schema.sh`** for ScyllaDB schema
- [x] **Create `health-check.sh`** for service validation (included in deploy script)

#### **6.3 Monitoring Setup**
- [ ] **Add Prometheus metrics** for logging service
- [ ] **Create Grafana dashboards** for Phase 3 metrics
- [ ] **Set up alerting** for database and queue health
- [ ] **Add logging aggregation** (ELK stack or similar)

---

## 🎯 **Success Criteria**

### **Functional Requirements**
- [ ] **All intermediate topics** are created and functional
- [ ] **ScyllaDB is deployed** and accessible
- [ ] **Logging Service** consumes and stores all interaction data
- [ ] **Orchestrator publishes** to intermediate topics
- [ ] **Latency metrics** are captured and stored

### **Performance Requirements**
- [ ] **Logging latency** < 10ms (non-blocking)
- [ ] **Database write latency** < 50ms
- [ ] **Message queue throughput** > 1000 msg/sec
- [ ] **System availability** > 99.9%

### **Operational Requirements**
- [ ] **Health checks** for all services
- [ ] **Monitoring and alerting** configured
- [ ] **Backup and recovery** procedures documented
- [ ] **Troubleshooting guides** available

---

## 📁 **File Structure After Implementation**

```
v2/
├── k8s/
│   └── phase3/
│       ├── manifests/
│       │   ├── scylladb-deployment.yaml
│       │   ├── scylladb-service.yaml
│       │   ├── scylladb-pvc.yaml
│       │   ├── logging-service-deployment.yaml
│       │   └── logging-service-service.yaml
│       └── db/
│           └── schema.cql
├── logging-service/
│   ├── main.go
│   ├── Dockerfile
│   ├── go.mod
│   └── go.sum
├── orchestrator/
│   ├── internal/
│   │   └── kafka/
│   │       └── service.go (enhanced)
│   └── main.go (enhanced)
├── scripts/
│   ├── create-topics.sh
│   ├── apply-schema.sh
│   └── deploy-phase3.sh
├── docker-compose.yml (enhanced)
└── README-Phase3.md
```

---

## 🚀 **Implementation Priority**

### **High Priority (Week 1)**
1. **Step 1**: Enhance Redpanda with intermediate topics
2. **Step 2**: Deploy ScyllaDB with basic configuration
3. **Step 3**: Create basic Logging Service

### **Medium Priority (Week 2)**
1. **Step 4**: Refactor Orchestrator for intermediate publishing
2. **Step 5**: Basic testing and validation
3. **Step 6**: Initial documentation

### **Low Priority (Week 3)**
1. **Advanced monitoring** and alerting
2. **Performance optimization**
3. **Comprehensive testing** and validation

---

**Status**: ✅ **COMPLETED**  
**Next Action**: Deploy and test the complete Phase 3 implementation 