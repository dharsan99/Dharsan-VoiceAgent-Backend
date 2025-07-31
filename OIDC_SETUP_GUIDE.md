# 🔐 OIDC Federation Setup for Secure Backend Access

This guide explains the OpenID Connect (OIDC) federation setup between Vercel and Google Cloud Platform for secure backend access.

## 📋 Overview

The setup enables secure communication between your Vercel frontend and GKE backend using OIDC tokens, eliminating the need for API keys or service account credentials in your frontend code.

## 🏗️ Architecture

```
Vercel Frontend (HTTPS) 
    ↓ OIDC Token
Google Cloud IAM
    ↓ Workload Identity
GKE Backend (HTTP)
```

## 🔧 Setup Steps

### 1. OIDC Identity Pool Created ✅
```bash
gcloud iam workload-identity-pools create "vercel-pool" \
  --location="global" \
  --display-name="Vercel OIDC Pool" \
  --description="OIDC pool for Vercel deployments"
```

### 2. OIDC Provider Created ✅
```bash
gcloud iam workload-identity-pools providers create-oidc "vercel-provider" \
  --location="global" \
  --workload-identity-pool="vercel-pool" \
  --issuer-uri="https://oidc.vercel.com/dharsan-kumars-projects" \
  --attribute-mapping="google.subject=assertion.sub,attribute.aud=assertion.aud,attribute.project=assertion.sub" \
  --attribute-condition="assertion.aud=='https://vercel.com/dharsan-kumars-projects'"
```

### 3. Service Account Created ✅
```bash
gcloud iam service-accounts create "vercel-backend-access" \
  --display-name="Vercel Backend Access" \
  --description="Service account for Vercel to access backend services"
```

### 4. IAM Binding Created ✅
```bash
gcloud iam service-accounts add-iam-policy-binding \
  "vercel-backend-access@speechtotext-466820.iam.gserviceaccount.com" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/373522835279/locations/global/workloadIdentityPools/vercel-pool/attribute.project/owner:dharsan-kumars-projects:project:dharsan-voice-agent-frontend:environment:production"
```

### 5. Kubernetes Service Account Created ✅
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: vercel-backend-access
  namespace: voice-agent-fresh
  annotations:
    iam.gke.io/gcp-service-account: vercel-backend-access@speechtotext-466820.iam.gserviceaccount.com
```

## 🔑 OIDC Token Details

### Token Claims
- **Issuer (iss)**: `https://oidc.vercel.com/dharsan-kumars-projects`
- **Audience (aud)**: `https://vercel.com/dharsan-kumars-projects`
- **Subject (sub)**: `owner:dharsan-kumars-projects:project:dharsan-voice-agent-frontend:environment:production`
- **Scope**: `owner:dharsan-kumars-projects:project:dharsan-voice-agent-frontend:environment:production`
- **Issued At (iat)**: `1753939525`
- **Not Before (nbf)**: `1753939525`
- **Expiration (exp)**: `1753943125`

## 🚀 Implementation

### Frontend API Routes
- **HTTP Proxy**: `/api/backend/[...path]/route.ts`
- **WebSocket Proxy**: `/api/backend/ws/route.ts` (placeholder)
- **Secure WebSocket**: `src/utils/secureWebSocket.ts`

### Configuration
- **Production URLs**: Updated to use secure proxy endpoints
- **CSP Headers**: Allow specific backend endpoints
- **OIDC Verification**: JWT token validation

## 🔒 Security Features

### 1. Token Verification
- ✅ Issuer validation
- ✅ Audience validation
- ✅ Expiration checking
- ✅ Not-before validation

### 2. CORS Configuration
- ✅ Secure origins only
- ✅ Proper headers
- ✅ Credentials support

### 3. Workload Identity
- ✅ No long-lived credentials
- ✅ Automatic token rotation
- ✅ Principle of least privilege

## 🧪 Testing

### 1. Test OIDC Token
```bash
# Get token from Vercel
curl -H "Authorization: Bearer $OIDC_TOKEN" \
  https://dharsan-voice-agent-frontend.vercel.app/api/backend/health
```

### 2. Test WebSocket Connection
```javascript
const ws = new SecureWebSocket('wss://dharsan-voice-agent-frontend.vercel.app/api/backend/ws');
await ws.connect();
```

## 🔄 Next Steps

### 1. Enable HTTPS on Backend
```bash
# Generate SSL certificates
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Update orchestrator deployment
kubectl set env deployment/orchestrator -n voice-agent-fresh ENABLE_HTTPS=true
kubectl set env deployment/orchestrator -n voice-agent-fresh SSL_CERT_PATH=/etc/ssl/certs/server.crt
kubectl set env deployment/orchestrator -n voice-agent-fresh SSL_KEY_PATH=/etc/ssl/private/server.key
```

### 2. WebSocket Proxy Implementation
- Consider using a WebSocket proxy service
- Or implement WebSocket support in the backend with HTTPS

### 3. Environment Variables
```bash
# Add to Vercel environment variables
OIDC_ISSUER=https://oidc.vercel.com/dharsan-kumars-projects
OIDC_AUDIENCE=https://vercel.com/dharsan-kumars-projects
BACKEND_BASE_URL=https://34.70.216.41:8001
```

## 📊 Benefits

1. **Security**: No credentials in frontend code
2. **Compliance**: Follows security best practices
3. **Scalability**: Automatic token management
4. **Auditability**: Full request tracing
5. **Zero Trust**: Verify every request

## 🚨 Troubleshooting

### Common Issues
1. **Token Expired**: Check expiration time
2. **CORS Errors**: Verify CSP configuration
3. **Connection Failed**: Check backend availability
4. **Authentication Failed**: Verify OIDC configuration

### Debug Commands
```bash
# Check OIDC pool status
gcloud iam workload-identity-pools describe vercel-pool --location=global

# Check service account permissions
gcloud iam service-accounts get-iam-policy vercel-backend-access@speechtotext-466820.iam.gserviceaccount.com

# Check Kubernetes service account
kubectl get serviceaccount vercel-backend-access -n voice-agent-fresh -o yaml
```

## 📚 Resources

- [Google Cloud Workload Identity](https://cloud.google.com/iam/docs/workload-identity-federation)
- [Vercel OIDC Documentation](https://vercel.com/docs/deployments/oidc)
- [OpenID Connect Specification](https://openid.net/connect/)
- [JWT Token Validation](https://jwt.io/)

---

**Status**: ✅ OIDC Federation Setup Complete
**Next**: Implement WebSocket proxy and enable HTTPS backend 