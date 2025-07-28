# Production Deployment Security Guide

## Overview
This guide addresses critical security and production deployment issues identified in the Voice Agent codebase.

## Critical Issues Fixed

### 1. CORS Configuration
**Issue**: Wildcard CORS (`allow_origins=["*"]`) in all backend services
**Fix**: Environment-specific CORS configuration

#### Backend CORS Updates
- **Media Server**: Updated to use environment-specific allowed origins
- **Orchestrator**: Updated to use environment-specific allowed origins
- **Security Headers**: Added production security headers

#### Production CORS Configuration
```bash
# Environment Variables
ENVIRONMENT=production
CORS_ALLOWED_ORIGINS=https://dharsan-voice-agent-frontend.vercel.app,https://voice-agent-frontend.vercel.app,https://voice-agent.com,https://www.voice-agent.com
```

### 2. Hardcoded Secrets
**Issue**: TURN server credentials hardcoded in frontend
**Fix**: Environment variable configuration

#### Frontend Environment Variables
```bash
# Vercel Environment Variables
VITE_TURN_USERNAME=your_turn_username
VITE_TURN_CREDENTIAL=your_turn_credential
```

### 3. SSL/TLS Configuration
**Issue**: Backend services not configured for HTTPS/WSS
**Fix**: SSL certificate configuration

#### SSL Certificate Setup
```bash
# Generate SSL certificates
openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt -days 365 -nodes

# Update Kubernetes secrets
kubectl create secret tls voice-agent-tls --cert=server.crt --key=server.key -n voice-agent-phase5
```

## Production Deployment Checklist

### Frontend (Vercel)
- [ ] Set environment variables for TURN server credentials
- [ ] Configure custom domain with SSL
- [ ] Enable security headers
- [ ] Set up monitoring and logging

### Backend (GKE)
- [ ] Configure SSL certificates
- [ ] Set production environment variables
- [ ] Configure CORS allowed origins
- [ ] Enable security headers
- [ ] Set up monitoring and alerting

### Environment Variables

#### Frontend (Vercel)
```env
VITE_TURN_USERNAME=your_turn_username
VITE_TURN_CREDENTIAL=your_turn_credential
VITE_BACKEND_URL=https://your-backend-domain.com
VITE_WEBSOCKET_URL=wss://your-backend-domain.com/ws
```

#### Backend (GKE)
```env
ENVIRONMENT=production
CORS_ALLOWED_ORIGINS=https://dharsan-voice-agent-frontend.vercel.app,https://voice-agent-frontend.vercel.app
ENABLE_HTTPS=true
SSL_CERT_PATH=/etc/ssl/certs/server.crt
SSL_KEY_PATH=/etc/ssl/private/server.key
```

## Security Headers

### Production Security Headers
```go
// Added to all production responses
w.Header().Set("X-Content-Type-Options", "nosniff")
w.Header().Set("X-Frame-Options", "DENY")
w.Header().Set("X-XSS-Protection", "1; mode=block")
w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
```

### Nginx Security Headers
```nginx
# Add to nginx.conf
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "no-referrer-when-downgrade" always;
add_header Content-Security-Policy "default-src 'self' https: data: blob: 'unsafe-inline'" always;
```

## Kubernetes Deployment

### SSL Configuration
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: voice-agent-ingress
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - your-domain.com
    secretName: voice-agent-tls
```

### Environment Variables in Deployment
```yaml
env:
- name: ENVIRONMENT
  value: "production"
- name: CORS_ALLOWED_ORIGINS
  value: "https://dharsan-voice-agent-frontend.vercel.app,https://voice-agent-frontend.vercel.app"
```

## Monitoring and Logging

### Health Checks
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 30
readinessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 10
```

### Logging Configuration
```yaml
env:
- name: LOG_LEVEL
  value: "info"
- name: LOG_FORMAT
  value: "json"
```

## Rate Limiting

### Backend Rate Limiting
```go
// Rate limiting configuration
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60s
```

### Nginx Rate Limiting
```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req zone=api burst=20 nodelay;
```

## Backup and Recovery

### Database Backup
```bash
# Backup ScyllaDB
kubectl exec -n voice-agent-phase5 scylladb-0 -- nodetool snapshot voice_agent
```

### Configuration Backup
```bash
# Backup Kubernetes configurations
kubectl get all -n voice-agent-phase5 -o yaml > backup.yaml
```

## Testing Production Deployment

### 1. SSL Certificate Test
```bash
# Test SSL certificate
openssl s_client -connect your-domain.com:443 -servername your-domain.com
```

### 2. CORS Test
```bash
# Test CORS headers
curl -H "Origin: https://dharsan-voice-agent-frontend.vercel.app" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS https://your-backend-domain.com/ws
```

### 3. Security Headers Test
```bash
# Test security headers
curl -I https://your-backend-domain.com/health
```

## Troubleshooting

### Common Issues

1. **CORS Errors**
   - Check CORS_ALLOWED_ORIGINS environment variable
   - Verify frontend domain is in allowed origins list

2. **SSL Certificate Issues**
   - Check certificate validity
   - Verify certificate is properly mounted in pods

3. **WebSocket Connection Issues**
   - Check if WSS is properly configured
   - Verify firewall rules allow WebSocket traffic

### Debug Commands
```bash
# Check pod logs
kubectl logs -n voice-agent-phase5 deployment/orchestrator

# Check environment variables
kubectl exec -n voice-agent-phase5 deployment/orchestrator -- env | grep CORS

# Check SSL certificate
kubectl get secret voice-agent-tls -n voice-agent-phase5 -o yaml
```

## Performance Optimization

### Resource Limits
```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

### Auto Scaling
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## Conclusion

This guide addresses the critical security and production deployment issues identified in the codebase. Follow these steps to ensure a secure and reliable production deployment.

### Next Steps
1. Deploy the updated configurations
2. Test all security measures
3. Monitor performance and logs
4. Set up alerting for security events 