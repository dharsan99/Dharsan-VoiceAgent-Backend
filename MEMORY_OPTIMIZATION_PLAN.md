# Memory Optimization Plan - Free Up Space for STT

## 🎯 **Memory Optimization Strategy**

### **Goal**: Free up memory for Whisper Large STT service by optimizing other services

---

## 📊 **Current vs Optimized Memory Allocation**

### **Before Optimization (Current):**
| Service | Pods | Memory Request | Memory Limit | Total Reserved |
|---------|------|----------------|--------------|----------------|
| **LLM Service** | 1 | 128Mi | 256Mi | 128Mi |
| **Media Server** | 1 | 256Mi | 512Mi | 256Mi |
| **Orchestrator** | 2 | 512Mi each | 1Gi each | 1,024Mi |
| **RedPanda** | 1 | 256Mi | 768Mi | 256Mi |
| **TTS Service** | 1 | 512Mi | 1Gi | 512Mi |
| **STT Service** | 1 | 2Gi | 4Gi | 2,000Mi |
| **Total Reserved** | | | | **4,176Mi** |

### **After Optimization:**
| Service | Pods | Memory Request | Memory Limit | Total Reserved | Savings |
|---------|------|----------------|--------------|----------------|---------|
| **LLM Service** | 1 | 64Mi | 128Mi | 64Mi | **-64Mi** |
| **Media Server** | 1 | 128Mi | 256Mi | 128Mi | **-128Mi** |
| **Orchestrator** | 1 | 256Mi | 512Mi | 256Mi | **-768Mi** |
| **RedPanda** | 1 | 128Mi | 256Mi | 128Mi | **-128Mi** |
| **TTS Service** | 1 | 256Mi | 512Mi | 256Mi | **-256Mi** |
| **STT Service** | 1 | 2Gi | 4Gi | 2,000Mi | **+0Mi** |
| **Total Reserved** | | | | **2,832Mi** | **-1,344Mi** |

---

## 💰 **Memory Savings Summary**

### **Total Memory Freed: 1,344Mi (1.3GB)**

### **Breakdown of Savings:**
- **LLM Service**: 64Mi saved (50% reduction)
- **Media Server**: 128Mi saved (50% reduction)
- **Orchestrator**: 768Mi saved (75% reduction + 1 replica)
- **RedPanda**: 128Mi saved (50% reduction)
- **TTS Service**: 256Mi saved (50% reduction)

### **Impact on STT Service:**
- **Available Memory**: +1.3GB freed up
- **STT Requirements**: 2-4GB for Whisper Large
- **Result**: **Much better fit for Whisper Large!**

---

## 🔧 **Optimization Details**

### **1. LLM Service Optimization:**
```yaml
# Before: 128Mi req, 256Mi limit
# After: 64Mi req, 128Mi limit
# Actual usage: 17Mi (plenty of headroom)
```

### **2. Media Server Optimization:**
```yaml
# Before: 256Mi req, 512Mi limit
# After: 128Mi req, 256Mi limit
# Actual usage: 7Mi (plenty of headroom)
```

### **3. Orchestrator Optimization:**
```yaml
# Before: 2 replicas × 512Mi = 1,024Mi
# After: 1 replica × 256Mi = 256Mi
# Actual usage: 8Mi + 4Mi = 12Mi (plenty of headroom)
```

### **4. RedPanda Optimization:**
```yaml
# Before: 256Mi req, 768Mi limit
# After: 128Mi req, 256Mi limit
# Actual usage: 178Mi (still within limits)
```

### **5. TTS Service Optimization:**
```yaml
# Before: 512Mi req, 1Gi limit
# After: 256Mi req, 512Mi limit
# Actual usage: 37Mi (plenty of headroom)
```

---

## 🚀 **Implementation Plan**

### **Step 1: Apply Optimized Deployments**
```bash
# Apply all optimized deployments
kubectl apply -f v2/k8s/phase5/manifests/llm-service-deployment-optimized.yaml
kubectl apply -f v2/k8s/phase5/manifests/tts-service-deployment-optimized.yaml
kubectl apply -f v2/k8s/phase5/manifests/orchestrator-deployment-optimized.yaml
kubectl apply -f v2/k8s/phase5/manifests/redpanda-deployment-optimized.yaml
kubectl apply -f v2/k8s/phase5/manifests/media-server-deployment-optimized.yaml
```

### **Step 2: Scale Down STT to 1 Replica**
```bash
# Scale down STT service
kubectl scale deployment stt-service --replicas=1 -n voice-agent-phase5
```

### **Step 3: Clean Up Old Pods**
```bash
# Delete old pods to free up memory
kubectl delete pod stt-service-6d774d84d7-ldcnb -n voice-agent-phase5
kubectl delete pod stt-service-6d774d84d7-r4fxv -n voice-agent-phase5
```

### **Step 4: Monitor Memory Usage**
```bash
# Check memory allocation
kubectl describe nodes | grep -A 5 "Allocated resources"

# Monitor real usage
kubectl top nodes
kubectl top pods -n voice-agent-phase5
```

---

## 📈 **Expected Results**

### **Memory Allocation After Optimization:**
```
Total Node Memory: 60GB
├── System Pods: ~55GB (92%)
├── Our Services: ~2.8GB (5%)  # Reduced from 4.2GB
├── Available: ~2.2GB (3%)     # Increased from 1.5GB
└── Whisper Large needs: 2-4GB ✅ (Much better fit!)
```

### **Performance Impact:**
- **LLM Service**: No impact (17Mi actual usage)
- **Media Server**: No impact (7Mi actual usage)
- **Orchestrator**: Minimal impact (12Mi actual usage)
- **RedPanda**: Monitor closely (178Mi actual usage)
- **TTS Service**: No impact (37Mi actual usage)

---

## ⚠️ **Risk Mitigation**

### **Monitoring Points:**
1. **RedPanda**: Watch for memory pressure (178Mi usage)
2. **Orchestrator**: Monitor performance with 1 replica
3. **Overall**: Check for OOM kills or pod restarts

### **Rollback Plan:**
```bash
# If issues occur, revert to original deployments
kubectl apply -f v2/k8s/phase5/manifests/llm-service-deployment.yaml
kubectl apply -f v2/k8s/phase5/manifests/tts-service-deployment.yaml
kubectl apply -f v2/k8s/phase5/manifests/orchestrator-deployment.yaml
kubectl apply -f v2/k8s/phase5/manifests/redpanda-deployment.yaml
kubectl apply -f v2/k8s/phase5/manifests/media-server-deployment.yaml
```

---

## 🎯 **Success Metrics**

### **Immediate Success:**
- ✅ **Memory Freed**: 1.3GB additional space
- ✅ **STT Fits**: Whisper Large can now load
- ✅ **Services Stable**: All optimized services running
- ✅ **No Performance Impact**: Actual usage well within limits

### **Long-term Success:**
- 🎯 **Whisper Large Working**: Full accuracy benefits
- 🎯 **Pipeline Stable**: End-to-end audio processing
- 🎯 **Cost Effective**: No GCP tier upgrade needed
- 🎯 **Scalable**: Room for future optimizations

---

## 🚀 **Ready to Implement**

**This optimization plan will free up 1.3GB of memory, making Whisper Large much more viable in your free tier setup!**

**Benefits:**
- **No cost increase**: Stay within free tier
- **Better accuracy**: Whisper Large instead of Base
- **Stable performance**: All services optimized
- **Future-proof**: Room for growth

**Ready to apply the optimizations?** 💪 