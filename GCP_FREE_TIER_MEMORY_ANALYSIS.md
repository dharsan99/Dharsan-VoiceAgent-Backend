# GCP Free Tier Memory Analysis & Whisper Large Constraints

## 🎯 **GCP Free Tier Memory Limits**

### **Node Specifications:**
- **Node Type**: `ek-standard-16` (GCP Free Tier)
- **Total Memory per Node**: ~60GB (59,815,884 KiB)
- **Allocatable Memory per Node**: ~58GB (59,815,884 KiB)
- **Number of Nodes**: 2 nodes
- **Total Cluster Memory**: ~116GB

---

## 📊 **Current Memory Usage Analysis**

### **Node 1 Memory Status:**
```
Node: gk3-voice-agent-free-nap-18evcoob-8e0b2873-fthz
- Total Memory: 60GB
- Allocated: 98% (60,177,031,424 bytes)
- Actual Usage: 2,163Mi (3%)
- Available: ~2GB
```

### **Node 2 Memory Status:**
```
Node: gk3-voice-agent-free-nap-18evcoob-a09f4813-69vv
- Total Memory: 60GB
- Allocated: 99% (61,183,449,984 bytes)
- Actual Usage: 2,728Mi (4%)
- Available: ~1GB
```

---

## 🔍 **Current Pipeline Memory Allocation**

### **Service Memory Requests (Reserved):**
| Service | Pods | Memory Request | Memory Limit | Total Reserved |
|---------|------|----------------|--------------|----------------|
| **LLM Service** | 1 | 128Mi | 256Mi | 128Mi |
| **Media Server** | 1 | 256Mi | 512Mi | 256Mi |
| **Orchestrator** | 2 | 512Mi each | 1Gi each | 1,024Mi |
| **RedPanda** | 1 | 256Mi | 768Mi | 256Mi |
| **STT Service** | 3 | 1-2Gi each | 2-4Gi each | 3,500Mi |
| **TTS Service** | 1 | 512Mi | 1Gi | 512Mi |
| **System Pods** | ~19 | Various | Various | ~55GB |
| **Total Reserved** | | | | **~60GB** |

### **Actual Memory Usage (Real-time):**
| Service | Current Usage | Peak Usage |
|---------|---------------|------------|
| **LLM Service** | 17Mi | ~50Mi |
| **Media Server** | 7Mi | ~100Mi |
| **Orchestrator** | 8Mi + 4Mi | ~200Mi |
| **RedPanda** | 178Mi | ~300Mi |
| **STT Service** | 210Mi + 208Mi | ~2GB (when loaded) |
| **TTS Service** | 37Mi | ~500Mi |
| **Total Actual** | **669Mi** | **~3GB** |

---

## ⚠️ **Critical Memory Constraints**

### **The Problem:**
1. **Over-Allocation**: 98-99% of memory is already reserved
2. **Whisper Large Requirement**: Needs 2-4GB for model loading
3. **No Available Memory**: Only ~1-2GB actually available
4. **System Overhead**: GKE system pods consume ~55GB

### **Memory Allocation Breakdown:**
```
Total Node Memory: 60GB
├── System Pods: ~55GB (92%)
├── Our Services: ~3.5GB (6%)
├── Available: ~1.5GB (2%)
└── Whisper Large needs: 2-4GB ❌
```

---

## 🚨 **Whisper Large Memory Challenge**

### **Whisper Large Requirements:**
- **Model Size**: ~1.5GB (1550MB)
- **Loading Memory**: ~2-3GB (model + processing)
- **Runtime Memory**: ~1.5-2GB (loaded model)
- **Total Needed**: 2-4GB

### **Current STT Service Status:**
```
Current STT Pods:
- stt-service-6d774d84d7-ldcnb: 1Gi req, 2Gi limit (crashed)
- stt-service-d868b7df9-hf5wv: 2Gi req, 4Gi limit (new)
- Actual Usage: ~210Mi each (without model loaded)
```

---

## 💡 **Solutions for GCP Free Tier**

### **Option 1: Optimize Current Services (Recommended)**
```yaml
# Reduce memory requests across all services
llm-service: 64Mi req, 128Mi limit
media-server: 128Mi req, 256Mi limit  
orchestrator: 256Mi req, 512Mi limit
redpanda: 128Mi req, 256Mi limit
tts-service: 256Mi req, 512Mi limit
stt-service: 1Gi req, 2Gi limit (Whisper Large)
```

### **Option 2: Use Whisper Base Instead**
```yaml
# Keep current memory allocation
stt-service: 256Mi req, 512Mi limit (Whisper Base)
# Saves ~1.5GB per node
```

### **Option 3: Single STT Instance**
```yaml
# Scale down to 1 STT pod
stt-service: replicas: 1
# Reduces memory pressure
```

### **Option 4: Upgrade GCP Tier**
- **e2-standard-4**: 16GB RAM, $0.134/hour
- **e2-standard-8**: 32GB RAM, $0.268/hour
- **Cost**: ~$100-200/month

---

## 🎯 **Recommended Action Plan**

### **Immediate (Free Tier):**
1. **Scale down STT**: `replicas: 1`
2. **Optimize memory**: Reduce requests across services
3. **Use Whisper Base**: Accept lower accuracy for now
4. **Monitor usage**: Keep actual usage under 80%

### **Medium Term (Consider Upgrade):**
1. **Upgrade to e2-standard-4**: 16GB RAM per node
2. **Deploy Whisper Large**: Full accuracy benefits
3. **Scale up services**: Better performance

### **Long Term (Production):**
1. **e2-standard-8 or higher**: 32GB+ RAM
2. **Multiple STT instances**: Load balancing
3. **GPU acceleration**: Faster processing

---

## 📈 **Memory Optimization Commands**

### **Current Optimization:**
```bash
# Scale down STT to 1 replica
kubectl scale deployment stt-service --replicas=1 -n voice-agent-phase5

# Check available memory
kubectl describe nodes | grep -A 5 "Allocated resources"

# Monitor real usage
kubectl top nodes
kubectl top pods -n voice-agent-phase5
```

### **Memory Cleanup:**
```bash
# Delete old pods
kubectl delete pod stt-service-6d774d84d7-ldcnb -n voice-agent-phase5
kubectl delete pod stt-service-6d774d84d7-r4fxv -n voice-agent-phase5

# Check for stuck pods
kubectl get pods -n voice-agent-phase5 | grep -E "(Error|CrashLoopBackOff)"
```

---

## 🎯 **Conclusion**

### **Current Situation:**
- **Memory Constraint**: 98-99% allocated, only 1-2GB available
- **Whisper Large**: Needs 2-4GB, won't fit in free tier
- **Recommendation**: Use Whisper Base or upgrade GCP tier

### **Immediate Action:**
1. **Scale STT to 1 replica**
2. **Use Whisper Base** (256Mi vs 2Gi)
3. **Monitor memory usage**
4. **Consider GCP tier upgrade** for Whisper Large

### **Cost-Benefit Analysis:**
- **Whisper Base**: Free, 85% accuracy
- **Whisper Large**: $100-200/month, 95% accuracy
- **Decision**: Start with Base, upgrade when budget allows

---

## 🚀 **Next Steps**

1. **Immediate**: Scale down and optimize memory
2. **Test**: Verify Whisper Base works in current setup
3. **Evaluate**: Compare accuracy vs cost for upgrade
4. **Plan**: Budget for GCP tier upgrade if needed

**The free tier is memory-constrained, but we can make it work with optimizations!** 💪 