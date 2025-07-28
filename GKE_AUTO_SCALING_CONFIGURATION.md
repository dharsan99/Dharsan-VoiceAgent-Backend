# GKE Auto-Scaling Configuration for Voice Agent Pipeline

## 🎯 **Overview**

This document outlines the auto-scaling configuration implemented for the Voice Agent pipeline on Google Kubernetes Engine (GKE) to handle dynamic workloads efficiently.

## ✅ **Current Auto-Scaling Status**

### **Node-Level Auto-Scaling: ENABLED**
- **Cluster:** `voice-agent-free`
- **Region:** `asia-south1`
- **Auto-Scaling:** ✅ **ENABLED**
- **Auto-Provisioning:** ✅ **ENABLED**
- **Max Nodes:** 1000 per node pool
- **Profile:** `OPTIMIZE_UTILIZATION`

### **Pod-Level Auto-Scaling: IMPLEMENTED**

#### **Horizontal Pod Autoscalers (HPA) Configured:**

| Service | Min Replicas | Max Replicas | CPU Threshold | Memory Threshold | Status |
|---------|-------------|--------------|---------------|------------------|---------|
| **STT Service** | 1 | 5 | 70% | 80% | ✅ **ACTIVE** |
| **Orchestrator** | 1 | 3 | 75% | 80% | ✅ **ACTIVE** |
| **Media Server** | 1 | 3 | 80% | 85% | ✅ **ACTIVE** |

## 🔧 **HPA Configuration Details**

### **STT Service HPA**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: stt-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: stt-service
  minReplicas: 1
  maxReplicas: 5
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

### **Orchestrator HPA**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: orchestrator-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: orchestrator
  minReplicas: 1
  maxReplicas: 3
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 75
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### **Media Server HPA**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: media-server-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: media-server
  minReplicas: 1
  maxReplicas: 3
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 80
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 85
```

## 📊 **Scaling Behavior**

### **Scale-Up Behavior**
- **Stabilization Window:** 30-60 seconds
- **Scale Policy:** 100% increase per 10-15 seconds
- **Trigger:** When CPU or Memory utilization exceeds thresholds

### **Scale-Down Behavior**
- **Stabilization Window:** 300 seconds (5 minutes)
- **Scale Policy:** 10% decrease per 60 seconds
- **Purpose:** Prevents rapid scaling down to avoid thrashing

## 🎯 **Resource Thresholds**

### **STT Service**
- **CPU Threshold:** 70% (triggers at 700m CPU usage)
- **Memory Threshold:** 80% (triggers at 800Mi memory usage)
- **Current Usage:** CPU: 55%, Memory: 38% (as of latest check)

### **Orchestrator**
- **CPU Threshold:** 75% (triggers at 375m CPU usage)
- **Memory Threshold:** 80% (triggers at 204Mi memory usage)
- **Current Usage:** CPU: 10%, Memory: 3% (as of latest check)

### **Media Server**
- **CPU Threshold:** 80% (triggers at 160m CPU usage)
- **Memory Threshold:** 85% (triggers at 217Mi memory usage)
- **Current Usage:** CPU: 1%, Memory: 9% (as of latest check)

## 🚀 **Benefits of Auto-Scaling**

### **1. Dynamic Workload Handling**
- Automatically scales up during high traffic periods
- Scales down during low usage to save resources
- Handles sudden spikes in audio processing demand

### **2. Resource Optimization**
- Prevents resource waste during idle periods
- Ensures adequate resources during peak usage
- Balances cost and performance

### **3. High Availability**
- Multiple replicas ensure service availability
- Automatic failover if pods become unhealthy
- Load distribution across multiple instances

### **4. Performance Improvement**
- Reduces response times during high load
- Prevents resource exhaustion
- Maintains consistent service quality

## 📈 **Monitoring and Management**

### **Check HPA Status**
```bash
kubectl get hpa -n voice-agent-phase5
kubectl describe hpa stt-service-hpa -n voice-agent-phase5
```

### **Monitor Pod Scaling**
```bash
kubectl get pods -n voice-agent-phase5 -l app=stt-service
kubectl top pods -n voice-agent-phase5
```

### **View Scaling Events**
```bash
kubectl get events -n voice-agent-phase5 --sort-by='.lastTimestamp'
```

## 🔄 **Auto-Scaling Workflow**

1. **Load Increase:** User traffic increases audio processing demand
2. **Resource Usage:** CPU/Memory utilization rises above thresholds
3. **HPA Detection:** Horizontal Pod Autoscaler detects high usage
4. **Scale Decision:** HPA calculates required replicas
5. **Pod Creation:** Kubernetes creates new pod replicas
6. **Load Distribution:** Traffic is distributed across all replicas
7. **Load Decrease:** When usage drops, HPA scales down gradually

## ⚠️ **Important Notes**

### **Scaling Considerations**
- **Warm-up Time:** New pods need time to initialize (especially STT service with model loading)
- **Resource Limits:** Ensure adequate cluster resources for scaling
- **Cost Management:** Monitor scaling patterns to optimize thresholds

### **Best Practices**
- **Gradual Scaling:** Use appropriate stabilization windows
- **Resource Monitoring:** Regularly check HPA metrics and thresholds
- **Performance Testing:** Test scaling behavior under various load conditions

## 🎉 **Implementation Status**

- ✅ **Node Auto-Scaling:** Enabled on GKE cluster
- ✅ **STT Service HPA:** Implemented and active
- ✅ **Orchestrator HPA:** Implemented and active
- ✅ **Media Server HPA:** Implemented and active
- ✅ **Resource Optimization:** Tiny Whisper model deployed
- ✅ **Health Probes:** Optimized for better reliability

**Total Auto-Scaling Coverage:** 100% of critical services 