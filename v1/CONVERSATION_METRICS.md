# Enhanced Conversation Metrics System

The V1 Voice Agent now includes a comprehensive conversation metrics system that tracks detailed performance data per session and provides real-time feedback to the frontend.

## Features

### ✅ **Per-Session Conversation Tracking**
- **Session Creation**: Automatic session creation with unique IDs
- **Conversation Exchanges**: Detailed recording of user inputs and AI responses
- **Processing Times**: Accurate timing for each conversation turn
- **Word Counts**: Tracking of response length and complexity
- **Turn Tracking**: Sequential conversation turn numbering

### ✅ **Real-Time Metrics Feedback**
- **Frontend Integration**: Metrics sent back to frontend after each conversation
- **Network Metrics**: Support for receiving network performance data
- **Live Updates**: Real-time session statistics available via API

### ✅ **Comprehensive Data Storage**
- **SQLite Database**: Persistent storage of all metrics
- **Multiple Tables**: Sessions, conversations, metrics, and errors
- **Data Retention**: Configurable cleanup of old data
- **Error Tracking**: Comprehensive error logging with context

## API Endpoints

### Session Management
```
GET /metrics/sessions?limit=10
```
Returns recent sessions with basic statistics.

### Detailed Session Data
```
GET /metrics/session/{session_id}
```
Returns complete session data including conversations, metrics, and errors.

### Real-Time Session Metrics
```
GET /metrics/session/{session_id}/realtime
```
Returns real-time statistics for active sessions including:
- Total conversations
- Average processing time
- Total words generated
- Average response length
- Network metrics
- Recent conversations

### Network Metrics Recording
```
POST /metrics/network?session_id={session_id}
Content-Type: application/json

{
  "averageLatency": 85.5,
  "jitter": 12.3,
  "packetLoss": 2.1,
  "bufferSize": 5
}
```
Records network performance metrics from the frontend.

### Aggregated Analytics
```
GET /metrics/aggregated?hours=24
```
Returns aggregated statistics for the last N hours.

### Data Cleanup
```
POST /metrics/cleanup?days=30
```
Removes data older than N days.

## WebSocket Integration

### Frontend to Backend Metrics
The frontend can send metrics data via WebSocket:

```javascript
// Send network metrics
websocket.send(JSON.stringify({
  type: "metrics",
  data: {
    averageLatency: 85.5,
    jitter: 12.3,
    packetLoss: 2.1,
    bufferSize: 5
  }
}));

// Send ping for connection health
websocket.send(JSON.stringify({
  type: "ping"
}));
```

### Backend to Frontend Metrics
The backend sends conversation metrics after each exchange:

```json
{
  "type": "processing_complete",
  "response": "Hello! How can I help you today?",
  "metrics": {
    "processing_time_ms": 1250.5,
    "response_length": 25,
    "word_count": 6,
    "conversation_turn": 1
  }
}
```

## Database Schema

### Sessions Table
```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_seconds REAL,
    total_exchanges INTEGER DEFAULT 0,
    total_errors INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Conversation Exchanges Table
```sql
CREATE TABLE conversation_exchanges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    user_input TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    processing_time_seconds REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
);
```

### Metrics Table
```sql
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    metric_data TEXT,  -- JSON for complex data
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
);
```

### Errors Table
```sql
CREATE TABLE errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    error_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    error_message TEXT NOT NULL,
    context TEXT,  -- JSON for additional context
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
);
```

## Metrics Collected

### Conversation Metrics
- **User Input Length**: Number of characters in user input
- **AI Response Length**: Number of characters in AI response
- **Processing Time**: Time from user input to AI response completion
- **Word Count**: Number of words in AI response
- **Conversation Turn**: Sequential turn number in the session

### Network Metrics
- **Average Latency**: Network latency in milliseconds
- **Jitter**: Network jitter in milliseconds
- **Packet Loss**: Packet loss percentage
- **Buffer Size**: Current audio buffer size

### Session Metrics
- **Session Duration**: Total session time
- **Total Exchanges**: Number of conversation exchanges
- **Total Errors**: Number of errors encountered
- **Error Types**: Categorized error tracking

## Usage Examples

### Frontend Integration

```javascript
// Connect to WebSocket
const websocket = new WebSocket('wss://your-backend-url/ws');

// Send network metrics periodically
setInterval(() => {
  websocket.send(JSON.stringify({
    type: "metrics",
    data: {
      averageLatency: calculateLatency(),
      jitter: calculateJitter(),
      packetLoss: calculatePacketLoss(),
      bufferSize: getBufferSize()
    }
  }));
}, 5000);

// Handle conversation metrics
websocket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === "processing_complete") {
    console.log("Conversation completed:", data.metrics);
    // Update UI with metrics
    updateMetricsDisplay(data.metrics);
  }
};
```

### Backend API Usage

```python
import requests

# Record network metrics
response = requests.post(
    "https://your-backend-url/metrics/network",
    params={"session_id": "session-123"},
    json={
        "averageLatency": 85.5,
        "jitter": 12.3,
        "packetLoss": 2.1,
        "bufferSize": 5
    }
)

# Get real-time session metrics
response = requests.get(
    "https://your-backend-url/metrics/session/session-123/realtime"
)
metrics = response.json()
print(f"Session has {metrics['total_conversations']} conversations")
```

## Monitoring and Analytics

### Real-Time Monitoring
- **Active Sessions**: Track currently active sessions
- **Performance Metrics**: Monitor processing times and response quality
- **Error Rates**: Track error frequency and types
- **Network Quality**: Monitor latency, jitter, and packet loss

### Historical Analysis
- **Session Trends**: Analyze session duration and conversation patterns
- **Performance Trends**: Track processing time improvements over time
- **Error Analysis**: Identify common error patterns and root causes
- **Usage Patterns**: Understand user interaction patterns

### Data Retention
- **Default Retention**: 30 days
- **Configurable Cleanup**: Adjust retention period via API
- **Automatic Cleanup**: Scheduled cleanup of old data
- **Storage Management**: Efficient storage with SQLite

## Benefits

1. **Performance Optimization**: Identify bottlenecks and optimize processing
2. **Quality Assurance**: Monitor conversation quality and user experience
3. **Error Prevention**: Proactive error detection and resolution
4. **User Experience**: Real-time feedback for better user interaction
5. **System Reliability**: Comprehensive monitoring for system health
6. **Data-Driven Decisions**: Historical data for informed improvements

## Implementation Notes

- **Modal Compatible**: Inline database implementation for cloud deployment
- **Error Handling**: Robust error handling with logging
- **Connection Management**: Proper WebSocket lifecycle management
- **Scalable Design**: Efficient database queries and indexing
- **Real-Time Updates**: Immediate metrics feedback to frontend
- **Backward Compatible**: Maintains existing functionality while adding features 