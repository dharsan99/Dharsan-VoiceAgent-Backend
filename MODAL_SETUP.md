# Modal Cloud Storage Integration Setup Guide

This guide will help you set up Modal cloud storage for your Voice Agent, including Volumes for metrics, Dicts for conversation history, and Queues for asynchronous processing.

## 📋 Prerequisites

1. **Modal Account**: Sign up at [modal.com](https://modal.com)
2. **Modal CLI**: Install the Modal CLI
3. **Python Environment**: Python 3.8+ with pip
4. **API Keys**: Deepgram, Groq, and ElevenLabs API keys

## 🚀 Installation Steps

### 1. Install Modal CLI

```bash
# Install Modal CLI
pip install modal

# Authenticate with Modal
modal token new
```

### 2. Install Dependencies

```bash
# Navigate to backend directory
cd Dharsan-VoiceAgent-Backend

# Install requirements (includes modal>=0.60.0)
pip install -r requirements.txt
```

### 3. Set Up Modal Secrets

Create a Modal secret with your API keys:

```bash
# Create a secret with your API keys
modal secret create voice-agent-secrets \
  DEEPGRAM_API_KEY=your_deepgram_key \
  GROQ_API_KEY=your_groq_key \
  ELEVENLABS_API_KEY=your_elevenlabs_key
```

### 4. Deploy Cloud Storage

```bash
# Deploy the Modal app with cloud storage
python deploy_modal.py deploy
```

## 📊 Cloud Storage Components

### 1. **Modal Volumes** - Metrics Storage
- **Purpose**: Persistent storage for session metrics and analytics
- **Location**: `/metrics` directory in cloud volume
- **Data**: JSON files with session metrics, processing times, network stats
- **Benefits**: High-performance, distributed file system for write-once, read-many workloads

### 2. **Modal Dicts** - Conversation History
- **Purpose**: Distributed key-value storage for conversations and sessions
- **Data**: Real-time conversation exchanges, session metadata
- **Benefits**: Fast access, automatic replication, no size limits

### 3. **Modal Queues** - Asynchronous Processing
- **Purpose**: Queue voice processing tasks for background analysis
- **Data**: Processing tasks, analytics jobs, cleanup operations
- **Benefits**: Decoupled processing, automatic scaling, fault tolerance

## 🔧 Configuration

### Environment Variables

Add these to your `.env` file:

```env
# Modal Configuration
MODAL_APP_ID=voice-agent-cloud
MODAL_ENVIRONMENT=main

# Cloud Storage Settings
CLOUD_STORAGE_ENABLED=true
METRICS_VOLUME_NAME=voice-agent-metrics
CONVERSATION_STORE_NAME=voice-conversations
VOICE_QUEUE_NAME=voice-processing
SESSION_STORE_NAME=voice-sessions
```

### Backend Integration

The backend automatically integrates with Modal storage when available:

```python
# Automatic cloud storage integration
if MODAL_STORAGE_AVAILABLE and cloud_storage:
    # Store session in cloud
    cloud_storage.store_session.remote(session_data)
    
    # Store conversation in cloud
    cloud_storage.store_conversation.remote(session_id, conversation_data)
    
    # Queue processing task
    cloud_storage.queue_voice_processing.remote(processing_data)
```

## 🧪 Testing Cloud Storage

### 1. Test Storage Functionality

```bash
# Test cloud storage components
python deploy_modal.py test
```

Expected output:
```
🧪 Testing Cloud Storage...
✅ Session stored: test_session_1234567890
✅ Metrics stored: /metrics/test_session_1234567890.json
✅ Conversation stored for session: test_session_1234567890
✅ Task queued: test_task_1234567890
Test Results: {'session_stored': True, 'metrics_stored': True, 'conversation_stored': True, 'queue_tested': True}
```

### 2. Check Storage Statistics

```bash
# Get storage statistics
python deploy_modal.py stats
```

Expected output:
```
📊 Getting Storage Statistics...
Storage Stats: {'sessions': 1, 'conversations': 1, 'metrics_files': 1, 'queue_items': 'dynamic'}
```

### 3. Clean Up Test Data

```bash
# Clean up test data
python deploy_modal.py cleanup
```

## 🌐 API Endpoints

### Cloud Storage Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/cloud/storage/status` | GET | Get cloud storage status and statistics |
| `/cloud/sessions` | GET | Get all sessions from cloud storage |
| `/cloud/sessions/{session_id}` | GET | Get specific session details |
| `/cloud/conversations/{session_id}` | GET | Get conversation history for session |
| `/cloud/metrics/{session_id}` | GET | Get session metrics from cloud volume |
| `/cloud/queue/status` | GET | Get voice processing queue status |
| `/cloud/queue/process` | POST | Process queued voice processing tasks |

### Example API Usage

```bash
# Check cloud storage status
curl http://localhost:8000/cloud/storage/status

# Get all sessions
curl http://localhost:8000/cloud/sessions

# Get conversation history
curl http://localhost:8000/cloud/conversations/session_1234567890

# Process queued tasks
curl -X POST http://localhost:8000/cloud/queue/process
```

## 🎯 Frontend Integration

### Cloud Storage Manager

The frontend includes a Cloud Storage Manager component that provides:

- **Real-time Statistics**: View storage usage and queue status
- **Session Management**: Browse and manage cloud sessions
- **Conversation History**: View conversation exchanges from cloud storage
- **Metrics Visualization**: Display session metrics and analytics
- **Queue Processing**: Process queued tasks manually

### Accessing Cloud Storage

1. **Open V1 Dashboard**: Navigate to the V1 Dashboard
2. **Click Cloud Button**: Click the blue "Cloud" button in the header
3. **View Data**: Browse sessions, conversations, and metrics
4. **Process Queue**: Click "Process Tasks" to handle queued items

## 🔍 Monitoring and Debugging

### 1. Check Modal Dashboard

Visit [modal.com](https://modal.com) to monitor:
- Function executions
- Volume usage
- Queue status
- Error logs

### 2. Local Logs

Monitor backend logs for cloud storage activity:

```bash
# Start backend with verbose logging
python main.py --log-level DEBUG
```

### 3. Storage Validation

Use the validation functions to check data integrity:

```python
# In Python console
from modal_storage import cloud_storage

# Check storage stats
stats = cloud_storage.get_storage_stats.remote()
print(f"Storage Stats: {stats}")

# Validate data integrity
integrity = cloud_storage.validate_data_integrity.remote()
print(f"Data Integrity: {integrity}")
```

## 🚨 Troubleshooting

### Common Issues

1. **Modal Not Available**
   ```
   Error: Modal storage not available
   ```
   **Solution**: Ensure Modal is installed and authenticated

2. **Volume Mount Issues**
   ```
   Error: Failed to mount volume
   ```
   **Solution**: Check volume permissions and network connectivity

3. **Queue Processing Failures**
   ```
   Error: Failed to process queue
   ```
   **Solution**: Check queue configuration and task format

4. **API Key Issues**
   ```
   Error: Missing API configuration
   ```
   **Solution**: Verify Modal secrets are properly configured

### Debug Commands

```bash
# Check Modal status
modal status

# List Modal apps
modal app list

# Check volume status
modal volume list

# View function logs
modal function logs voice-agent-cloud::test_cloud_storage
```

## 📈 Performance Optimization

### 1. Volume Optimization
- Use batch operations for multiple files
- Implement data compression for large metrics
- Set appropriate retention policies

### 2. Queue Optimization
- Process tasks in batches
- Implement dead letter queues for failed tasks
- Monitor queue depth and processing times

### 3. Dict Optimization
- Use appropriate key naming conventions
- Implement data serialization for complex objects
- Monitor memory usage for large datasets

## 🔐 Security Considerations

1. **API Key Management**: Store API keys in Modal secrets, not in code
2. **Access Control**: Implement proper authentication for cloud storage access
3. **Data Encryption**: Ensure sensitive data is encrypted in transit and at rest
4. **Audit Logging**: Monitor access to cloud storage resources

## 📚 Additional Resources

- [Modal Documentation](https://modal.com/docs)
- [Modal Python SDK](https://modal.com/docs/guide)
- [Modal Volumes Guide](https://modal.com/docs/guide/volumes)
- [Modal Dicts Guide](https://modal.com/docs/guide/dicts)
- [Modal Queues Guide](https://modal.com/docs/guide/queues)

## 🎉 Success Indicators

You've successfully integrated Modal cloud storage when:

✅ Modal CLI is installed and authenticated  
✅ Cloud storage components are deployed  
✅ API endpoints return valid data  
✅ Frontend Cloud Storage Manager displays data  
✅ Test commands execute successfully  
✅ No errors in backend logs  

## 🚀 Next Steps

1. **Scale Up**: Deploy to production with proper monitoring
2. **Optimize**: Implement caching and performance optimizations
3. **Extend**: Add more cloud storage features (backup, analytics)
4. **Monitor**: Set up alerts and monitoring dashboards
5. **Secure**: Implement additional security measures

---

**Need Help?** Check the Modal documentation or create an issue in the repository. 