-- Phase 3: ScyllaDB Schema for Voice AI Interactions
-- This schema defines the keyspace and tables for persistent interaction logging

-- Create keyspace for voice AI data
CREATE KEYSPACE IF NOT EXISTS voice_ai_ks
WITH replication = {
    'class': 'SimpleStrategy',
    'replication_factor': 1
};

USE voice_ai_ks;

-- Main table for voice interactions with time-series optimization
-- Partition key: session_id (for session-based queries)
-- Clustering key: event_timestamp (for time-based ordering)
CREATE TABLE IF NOT EXISTS voice_interactions (
    session_id text,
    event_timestamp timestamp,
    stage text,                    -- 'stt', 'llm', 'tts'
    data text,                     -- JSON or text data for the stage
    latency_ms int,                -- Processing latency in milliseconds
    metadata map<text, text>,      -- Additional metadata (model used, confidence, etc.)
    created_at timestamp,          -- Record creation timestamp
    PRIMARY KEY (session_id, event_timestamp)
) WITH CLUSTERING ORDER BY (event_timestamp DESC)
  AND compaction = {
      'class': 'TimeWindowCompactionStrategy',
      'compaction_window_size': 1,
      'compaction_window_unit': 'DAYS'
  }
  AND default_time_to_live = 7776000; -- 90 days TTL

-- Index for stage-based queries
CREATE INDEX IF NOT EXISTS ON voice_interactions (stage);

-- Index for latency-based queries
CREATE INDEX IF NOT EXISTS ON voice_interactions (latency_ms);

-- Session summary table for quick session overview
CREATE TABLE IF NOT EXISTS session_summaries (
    session_id text,
    created_at timestamp,
    last_activity timestamp,
    total_interactions int,
    avg_latency_ms int,
    stages_completed set<text>,
    status text,                   -- 'active', 'completed', 'failed'
    metadata map<text, text>,
    PRIMARY KEY (session_id)
) WITH default_time_to_live = 7776000; -- 90 days TTL

-- Performance metrics table for aggregated statistics
CREATE TABLE IF NOT EXISTS performance_metrics (
    metric_date date,
    metric_hour int,
    stage text,
    avg_latency_ms int,
    min_latency_ms int,
    max_latency_ms int,
    total_requests int,
    successful_requests int,
    failed_requests int,
    PRIMARY KEY ((metric_date, metric_hour), stage)
) WITH compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_size': 1,
    'compaction_window_unit': 'DAYS'
};

-- Error logging table for debugging and monitoring
CREATE TABLE IF NOT EXISTS error_logs (
    session_id text,
    error_timestamp timestamp,
    stage text,
    error_type text,
    error_message text,
    stack_trace text,
    metadata map<text, text>,
    PRIMARY KEY (session_id, error_timestamp)
) WITH CLUSTERING ORDER BY (error_timestamp DESC)
  AND default_time_to_live = 2592000; -- 30 days TTL

-- System health metrics table
CREATE TABLE IF NOT EXISTS system_health (
    service_name text,
    timestamp timestamp,
    status text,                   -- 'healthy', 'degraded', 'down'
    response_time_ms int,
    error_count int,
    metadata map<text, text>,
    PRIMARY KEY (service_name, timestamp)
) WITH CLUSTERING ORDER BY (timestamp DESC)
  AND compaction = {
      'class': 'TimeWindowCompactionStrategy',
      'compaction_window_size': 1,
      'compaction_window_unit': 'HOURS'
  }
  AND default_time_to_live = 604800; -- 7 days TTL

-- Create materialized view for stage-based analytics
CREATE MATERIALIZED VIEW IF NOT EXISTS stage_analytics AS
SELECT stage, 
       session_id, 
       event_timestamp, 
       latency_ms, 
       data
FROM voice_interactions
WHERE stage IS NOT NULL 
  AND session_id IS NOT NULL 
  AND event_timestamp IS NOT NULL
PRIMARY KEY (stage, session_id, event_timestamp)
WITH CLUSTERING ORDER BY (session_id ASC, event_timestamp DESC);

-- Insert sample data for testing (optional)
-- INSERT INTO voice_interactions (session_id, event_timestamp, stage, data, latency_ms, metadata, created_at)
-- VALUES ('test-session-001', toTimestamp(now()), 'stt', 'Hello world', 150, {'confidence': '0.95', 'model': 'nova-3'}, toTimestamp(now()));

-- Grant permissions (if using authentication)
-- GRANT ALL PERMISSIONS ON KEYSPACE voice_ai_ks TO voice_ai_user;
-- GRANT ALL PERMISSIONS ON TABLE voice_ai_ks.voice_interactions TO voice_ai_user;
-- GRANT ALL PERMISSIONS ON TABLE voice_ai_ks.session_summaries TO voice_ai_user;
-- GRANT ALL PERMISSIONS ON TABLE voice_ai_ks.performance_metrics TO voice_ai_user;
-- GRANT ALL PERMISSIONS ON TABLE voice_ai_ks.error_logs TO voice_ai_user;
-- GRANT ALL PERMISSIONS ON TABLE voice_ai_ks.system_health TO voice_ai_user; 