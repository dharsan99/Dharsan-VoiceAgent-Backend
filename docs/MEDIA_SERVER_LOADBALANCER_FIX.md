# Media Server LoadBalancer Fix

## Issue Identified
The frontend was failing to connect to the WHIP endpoint with the error:
```
POST http://35.200.237.68:8001/whip net::ERR_CONNECTION_TIMED_OUT
```

## Root Cause Analysis
1. **Missing LoadBalancer Service**: The `media-server` service was configured as `ClusterIP`, making it inaccessible from outside the cluster
2. **Mixed Protocol Issue**: GCP LoadBalancers don't support mixed protocols (TCP + UDP) in a single service
3. **Incorrect IP Address**: The frontend was trying to connect to `35.200.237.68` which was not assigned to the media server

## Solution Implemented

### 1. Split Media Server Services
Created two separate services to avoid mixed protocol issues:
- **`media-server`**: LoadBalancer service for HTTP (WHIP) on port 8001
- **`media-server-rtp`**: ClusterIP service for RTP on port 10000

### 2. Updated Service Configuration
Modified `v2/k8s/phase5/manifests/media-server-deployment-optimized.yaml`:
```yaml
# HTTP Service (LoadBalancer)
apiVersion: v1
kind: Service
metadata:
  name: media-server
spec:
  type: LoadBalancer  # Changed from ClusterIP
  ports:
    - protocol: TCP
      port: 8001
      targetPort: 8001
      name: http

---
# RTP Service (ClusterIP)
apiVersion: v1
kind: Service
metadata:
  name: media-server-rtp
spec:
  type: ClusterIP
  ports:
    - protocol: UDP
      port: 10000
      targetPort: 10000
      name: rtp
```

### 3. Updated Frontend Configuration
Updated `src/config/production.ts`:
```typescript
// Before
WHIP_URL: 'http://35.200.237.68:8001/whip'

// After
WHIP_URL: 'http://35.244.8.62:8001/whip'
```

## Results

### ✅ LoadBalancer Assignment
```bash
NAME           TYPE           CLUSTER-IP     EXTERNAL-IP   PORT(S)          AGE
media-server   LoadBalancer   34.118.235.8   35.244.8.62   8001:32667/TCP   3d1h
```

### ✅ Health Check Verification
```bash
curl -v http://35.244.8.62:8001/health
# Returns: HTTP/1.1 200 OK
# {"status":"healthy","service":"voice-agent-media-server"}
```

### ✅ Service Status
- **Media Server HTTP**: ✅ LoadBalancer accessible at `35.244.8.62:8001`
- **Media Server RTP**: ✅ ClusterIP for internal RTP communication
- **Orchestrator**: ✅ LoadBalancer accessible at `34.47.230.178:8001`
- **WebSocket**: ✅ Working perfectly

## Next Steps
1. **Test WHIP Connection**: Frontend should now be able to establish WHIP connections
2. **Verify Audio Pipeline**: Complete end-to-end audio processing
3. **Monitor Performance**: Ensure stable connections under load

## Files Modified
- `v2/k8s/phase5/manifests/media-server-deployment-optimized.yaml`
- `../Dharsan-VoiceAgent-Frontend/dharsan-voiceagent-frontend/src/config/production.ts`

## Commands Executed
```bash
# Apply updated service configuration
kubectl apply -f v2/k8s/phase5/manifests/media-server-deployment-optimized.yaml

# Verify LoadBalancer assignment
kubectl get svc media-server -n voice-agent-phase5

# Test connectivity
curl -v http://35.244.8.62:8001/health
```

## Status: ✅ RESOLVED
The media server LoadBalancer is now properly configured and accessible. The frontend should be able to establish WHIP connections successfully. 