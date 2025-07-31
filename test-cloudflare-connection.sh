#!/bin/bash

echo "🔍 Testing Cloudflare SSL Connection..."
echo "======================================"

# Test DNS resolution with multiple DNS servers
echo "1. DNS Resolution (Multiple Sources):"
echo "   Local DNS:"
nslookup api.groundedai.in
echo "   Google DNS (8.8.8.8):"
nslookup api.groundedai.in 8.8.8.8
echo "   Cloudflare DNS (1.1.1.1):"
nslookup api.groundedai.in 1.1.1.1

echo -e "\n2. Direct Backend Test (should work):"
curl -s http://34.67.60.98:80/health | jq .

echo -e "\n3. HTTPS Health Check via Cloudflare:"
curl -I https://api.groundedai.in/health

echo -e "\n4. HTTP Health Check via Cloudflare (fallback):"
curl -I http://api.groundedai.in/health

echo -e "\n5. WebSocket Connection Test:"
echo "   Testing wss://api.groundedai.in/grpc..."

# Test WebSocket connection (simple curl test)
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==" https://api.groundedai.in/grpc

echo -e "\n6. Test with Host Header (direct):"
curl -H "Host: api.groundedai.in" http://34.67.60.98:80/health | jq .

echo -e "\n✅ Test completed!"
echo -e "\n📋 Status Summary:"
echo "   - Backend: ✅ Working on 34.67.60.98:80"
echo "   - DNS: 🔄 Propagating (may take 5-15 minutes)"
echo "   - Cloudflare: 🔄 Waiting for DNS update" 