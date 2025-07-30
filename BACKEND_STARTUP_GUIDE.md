# Voice Agent Backend Services - Unified Startup Guide

This guide explains how to use the unified backend startup system for the Voice Agent application.

## Overview

The Voice Agent backend consists of multiple services that need to be started together:

- **STT Service** (Port 8000): Speech-to-Text service
- **TTS Service** (Port 5001): Text-to-Speech service  
- **Media Server** (Port 8001): WebRTC and audio processing
- **Orchestrator** (Port 8004): Main coordination service

## Quick Start

### 1. Start All Services

```bash
# Make sure you're in the backend directory
cd /path/to/Dharsan-VoiceAgent-Backend

# Start all services with virtual environment activation
./start_backend_services.sh
```

This script will:
- Activate the Python virtual environment
- Check and install dependencies
- Kill any existing processes on required ports
- Start all services in the correct order
- Perform health checks
- Test log endpoints
- Display service information

### 2. Check Service Status

```bash
# Check if all services are running and healthy
./check_backend_status.sh
```

### 3. Stop All Services

```bash
# Stop all services cleanly
./stop_backend_services.sh
```

## Service Ports

| Service | Port | Description |
|---------|------|-------------|
| STT Service | 8000 | Speech-to-Text API |
| TTS Service | 5001 | Text-to-Speech API |
| Media Server | 8001 | WebRTC and audio processing |
| Orchestrator | 8004 | Main coordination service |
| gRPC Server | 8002 | gRPC communication |

## Script Details

### start_backend_services.sh

**Features:**
- Automatic virtual environment activation
- Port conflict resolution
- Service health monitoring
- Log endpoint testing
- Process management with PID tracking
- Colored output for better visibility
- Graceful shutdown on Ctrl+C

**What it does:**
1. Checks for virtual environment
2. Activates virtual environment
3. Installs missing dependencies
4. Kills existing processes on required ports
5. Starts services in background with logging
6. Performs health checks
7. Tests log endpoints
8. Saves process PIDs for cleanup
9. Keeps running to maintain environment

### stop_backend_services.sh

**Features:**
- Uses saved PIDs for clean shutdown
- Falls back to port-based process killing
- Verifies all ports are freed
- Shows log file locations

### check_backend_status.sh

**Features:**
- Checks port usage
- Performs health checks
- Tests log endpoints
- Shows service summary
- Lists available log files

## Log Files

All service logs are saved to the `logs/` directory:

- `logs/stt-service.log` - STT Service logs
- `logs/tts-service.log` - TTS Service logs  
- `logs/media-server.log` - Media Server logs
- `logs/orchestrator.log` - Orchestrator logs

## Log Endpoints

Each service exposes a `/logs` endpoint for retrieving logs:

- **Individual Service Logs:**
  - `http://localhost:8000/logs` - STT Service logs
  - `http://localhost:5001/logs` - TTS Service logs
  - `http://localhost:8001/logs` - Media Server logs

- **Aggregated Logs:**
  - `http://localhost:8004/logs` - All service logs (via Orchestrator)

## Testing

### Test Log Endpoints

```bash
# Test all log endpoints
python test_backend_logs.py
```

### Manual Testing

```bash
# Test individual service logs
curl http://localhost:8000/logs
curl http://localhost:5001/logs
curl http://localhost:8001/logs

# Test aggregated logs
curl http://localhost:8004/logs
```

## Troubleshooting

### Port Conflicts

If you see "address already in use" errors:

```bash
# Check what's using the ports
lsof -i :8000 -i :5001 -i :8001 -i :8004

# Kill processes manually if needed
kill -9 <PID>
```

### Virtual Environment Issues

If the virtual environment is missing:

```bash
# Create virtual environment
python3 -m venv venv

# Activate manually
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Service Not Starting

1. Check if the service binary exists:
   ```bash
   ls -la v2/orchestrator/orchestrator
   ls -la v2/media-server/media-server
   ```

2. Check if Python services have dependencies:
   ```bash
   source venv/bin/activate
   python -c "import fastapi, uvicorn, structlog"
   ```

### Health Check Failures

If health checks fail:

1. Check service logs:
   ```bash
   tail -f logs/stt-service.log
   tail -f logs/tts-service.log
   tail -f logs/media-server.log
   tail -f logs/orchestrator.log
   ```

2. Check if services are listening on correct ports:
   ```bash
   netstat -an | grep -E "8000|5001|8001|8004"
   ```

## Development Workflow

### Typical Development Session

1. **Start services:**
   ```bash
   ./start_backend_services.sh
   ```

2. **Check status:**
   ```bash
   ./check_backend_status.sh
   ```

3. **Make changes to code**

4. **Restart specific service if needed:**
   ```bash
   # Stop all services
   ./stop_backend_services.sh
   
   # Start again
   ./start_backend_services.sh
   ```

5. **Test changes:**
   ```bash
   python test_backend_logs.py
   ```

6. **Stop services when done:**
   ```bash
   ./stop_backend_services.sh
   ```

## Environment Variables

The services use environment variables for configuration. Key files:

- `v2/orchestrator/env.local` - Orchestrator configuration
- `v2/stt-service/.env` - STT Service configuration  
- `v2/tts-service/.env` - TTS Service configuration
- `v2/media-server/.env` - Media Server configuration

## Integration with Frontend

The frontend can now access backend logs through:

1. **Individual service logs** for detailed debugging
2. **Aggregated logs** via the orchestrator for unified view
3. **Real-time log updates** through the frontend's `useBackendLogs` hook

The frontend automatically detects the environment (development vs production) and fetches logs from the appropriate endpoints.

## Production Deployment

For production deployment:

1. Services run in Kubernetes pods
2. Logs are aggregated through the logging-service
3. Frontend connects to production service URLs
4. Health checks and monitoring are handled by Kubernetes

## Support

If you encounter issues:

1. Check the service logs in the `logs/` directory
2. Run `./check_backend_status.sh` to diagnose issues
3. Ensure all dependencies are installed
4. Verify port availability
5. Check virtual environment activation 