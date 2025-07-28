# V1 Metrics Database

A simple SQLite-based database system for storing historic metrics and conversation data for the V1 Voice Agent. The database is implemented inline within the main application to ensure compatibility with Modal deployment.

## Features

- **Session Tracking**: Automatic session creation and duration tracking
- **Network Metrics**: Store latency, jitter, packet loss, and buffer statistics
- **Conversation History**: Record user inputs and AI responses with processing times
- **Error Logging**: Comprehensive error tracking with severity levels
- **Aggregated Analytics**: Get summary statistics for monitoring and analysis
- **Data Cleanup**: Automatic cleanup of old data to manage storage

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

## API Endpoints

### Get Recent Sessions
```
GET /metrics/sessions?limit=10
```
Returns recent sessions with basic statistics.

### Get Session Details
```
GET /metrics/session/{session_id}
```
Returns detailed metrics, conversations, and errors for a specific session.

### Get Aggregated Metrics
```
GET /metrics/aggregated?hours=24
```
Returns aggregated statistics for the last N hours.

### Cleanup Old Data
```
POST /metrics/cleanup?days=30
```
Removes data older than N days to manage storage.

## Implementation Details

The database is implemented inline within `main.py` to ensure:
- **Modal Compatibility**: No external file dependencies
- **Automatic Initialization**: Database tables are created on first use
- **Error Handling**: Robust error handling with logging
- **Connection Management**: Proper connection lifecycle management

## Usage Example

```python
# Get database instance
db = get_metrics_db()

# Create a session
session_id = str(uuid.uuid4())
db.create_session(session_id)

# Record metrics
metrics = {
    "averageLatency": 85.5,
    "jitter": 12.3,
    "packetLoss": 2.1,
    "bufferSize": 5
}
db.record_metrics(session_id, metrics)

# Record conversation
db.record_conversation_exchange(
    session_id, 
    "Hello", 
    "Hi there! How can I help you?", 
    1.2
)

# End session
db.end_session(session_id, 120.5, 5, 0)
```

## Data Retention

- **Default Retention**: 30 days
- **Cleanup**: Automatic cleanup via API endpoint
- **Storage**: SQLite database file (`v1_metrics.db`)

## Monitoring

The database automatically logs:
- Session creation/termination
- Metric recording success/failure
- Error occurrences
- Cleanup operations

All operations include proper error handling and logging for monitoring and debugging. 