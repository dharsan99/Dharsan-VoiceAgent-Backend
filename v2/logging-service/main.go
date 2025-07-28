package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/gocql/gocql"
	"github.com/gorilla/mux"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/segmentio/kafka-go"
	"github.com/sirupsen/logrus"
)

// VoiceInteractionLog represents the data structure written to ScyllaDB
type VoiceInteractionLog struct {
	SessionID      string            `json:"session_id"`
	EventTimestamp time.Time         `json:"event_timestamp"`
	Stage          string            `json:"stage"`
	Data           string            `json:"data"`
	LatencyMs      int               `json:"latency_ms"`
	Metadata       map[string]string `json:"metadata"`
	CreatedAt      time.Time         `json:"created_at"`
}

// LoggingService manages the logging operations
type LoggingService struct {
	scyllaSession *gocql.Session
	logger        *logrus.Logger
	metrics       *Metrics
	ctx           context.Context
	cancel        context.CancelFunc
	wg            sync.WaitGroup
}

// Metrics holds Prometheus metrics
type Metrics struct {
	messagesProcessed prometheus.Counter
	messagesFailed    prometheus.Counter
	processingLatency prometheus.Histogram
	dbWriteLatency    prometheus.Histogram
}

// NewMetrics creates new Prometheus metrics
func NewMetrics() *Metrics {
	return &Metrics{
		messagesProcessed: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "logging_messages_processed_total",
			Help: "Total number of messages processed",
		}),
		messagesFailed: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "logging_messages_failed_total",
			Help: "Total number of messages that failed to process",
		}),
		processingLatency: prometheus.NewHistogram(prometheus.HistogramOpts{
			Name:    "logging_processing_latency_seconds",
			Help:    "Message processing latency in seconds",
			Buckets: prometheus.DefBuckets,
		}),
		dbWriteLatency: prometheus.NewHistogram(prometheus.HistogramOpts{
			Name:    "logging_db_write_latency_seconds",
			Help:    "Database write latency in seconds",
			Buckets: prometheus.DefBuckets,
		}),
	}
}

// RegisterMetrics registers Prometheus metrics
func (m *Metrics) RegisterMetrics() {
	prometheus.MustRegister(m.messagesProcessed)
	prometheus.MustRegister(m.messagesFailed)
	prometheus.MustRegister(m.processingLatency)
	prometheus.MustRegister(m.dbWriteLatency)
}

// NewLoggingService creates a new logging service instance
func NewLoggingService() *LoggingService {
	logger := logrus.New()
	logger.SetFormatter(&logrus.JSONFormatter{})
	logger.SetLevel(logrus.InfoLevel)

	ctx, cancel := context.WithCancel(context.Background())

	return &LoggingService{
		logger:  logger,
		metrics: NewMetrics(),
		ctx:     ctx,
		cancel:  cancel,
	}
}

// ConnectToScyllaDB establishes connection to ScyllaDB
func (ls *LoggingService) ConnectToScyllaDB() error {
	// Get ScyllaDB connection details from environment
	scyllaHost := getEnv("SCYLLADB_HOST", "scylladb.voice-agent-phase3.svc.cluster.local")
	scyllaPort := getEnv("SCYLLADB_PORT", "9042")
	scyllaKeyspace := getEnv("SCYLLADB_KEYSPACE", "voice_ai_ks")

	cluster := gocql.NewCluster(fmt.Sprintf("%s:%s", scyllaHost, scyllaPort))
	cluster.Keyspace = scyllaKeyspace
	cluster.Consistency = gocql.Quorum
	cluster.Timeout = 10 * time.Second
	cluster.ConnectTimeout = 10 * time.Second
	cluster.NumConns = 10
	cluster.MaxPreparedStmts = 1000
	cluster.MaxRoutingKeyInfo = 1000
	cluster.PageSize = 5000

	session, err := cluster.CreateSession()
	if err != nil {
		return fmt.Errorf("failed to create ScyllaDB session: %w", err)
	}

	ls.scyllaSession = session
	ls.logger.Info("Successfully connected to ScyllaDB")
	return nil
}

// Close closes the logging service connections
func (ls *LoggingService) Close() error {
	ls.cancel()
	ls.wg.Wait()

	if ls.scyllaSession != nil {
		ls.scyllaSession.Close()
	}

	ls.logger.Info("Logging service closed")
	return nil
}

// consumeAndStore consumes messages from a topic and stores them in ScyllaDB
func (ls *LoggingService) consumeAndStore(topic string) {
	defer ls.wg.Done()

	// Get Redpanda connection details from environment
	redpandaHost := getEnv("REDPANDA_HOST", "redpanda.voice-agent-phase3.svc.cluster.local")
	redpandaPort := getEnv("REDPANDA_PORT", "9092")

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  []string{fmt.Sprintf("%s:%s", redpandaHost, redpandaPort)},
		Topic:    topic,
		GroupID:  "logging-service-group",
		MinBytes: 10e3, // 10KB
		MaxBytes: 10e6, // 10MB
	})
	defer reader.Close()

	ls.logger.WithField("topic", topic).Info("Consumer started")

	for {
		select {
		case <-ls.ctx.Done():
			ls.logger.WithField("topic", topic).Info("Consumer stopped")
			return
		default:
			// Read message with timeout
			ctx, cancel := context.WithTimeout(ls.ctx, 30*time.Second)
			msg, err := reader.ReadMessage(ctx)
			cancel()

			if err != nil {
				if err == context.DeadlineExceeded {
					continue // Timeout, try again
				}
				ls.logger.WithFields(logrus.Fields{
					"topic": topic,
					"error": err,
				}).Error("Error reading message")
				ls.metrics.messagesFailed.Inc()
				continue
			}

			// Process message
			ls.processMessage(topic, msg)
		}
	}
}

// processMessage processes a single message and stores it in ScyllaDB
func (ls *LoggingService) processMessage(topic string, msg kafka.Message) {
	startTime := time.Now()
	defer func() {
		ls.metrics.processingLatency.Observe(time.Since(startTime).Seconds())
	}()

	var interactionLog VoiceInteractionLog
	if err := json.Unmarshal(msg.Value, &interactionLog); err != nil {
		ls.logger.WithFields(logrus.Fields{
			"topic": topic,
			"error": err,
		}).Error("Failed to unmarshal message")
		ls.metrics.messagesFailed.Inc()
		return
	}

	// Set default values if not provided
	if interactionLog.CreatedAt.IsZero() {
		interactionLog.CreatedAt = time.Now()
	}
	if interactionLog.EventTimestamp.IsZero() {
		interactionLog.EventTimestamp = time.Now()
	}
	if interactionLog.Metadata == nil {
		interactionLog.Metadata = make(map[string]string)
	}

	// Add topic information to metadata
	interactionLog.Metadata["source_topic"] = topic
	interactionLog.Metadata["processed_at"] = time.Now().Format(time.RFC3339)

	// Store in ScyllaDB
	if err := ls.storeInScyllaDB(interactionLog); err != nil {
		ls.logger.WithFields(logrus.Fields{
			"topic":      topic,
			"session_id": interactionLog.SessionID,
			"stage":      interactionLog.Stage,
			"error":      err,
		}).Error("Failed to store in ScyllaDB")
		ls.metrics.messagesFailed.Inc()
		return
	}

	ls.logger.WithFields(logrus.Fields{
		"topic":      topic,
		"session_id": interactionLog.SessionID,
		"stage":      interactionLog.Stage,
		"latency_ms": interactionLog.LatencyMs,
	}).Debug("Message processed and stored")

	ls.metrics.messagesProcessed.Inc()
}

// storeInScyllaDB stores a voice interaction log in ScyllaDB
func (ls *LoggingService) storeInScyllaDB(log VoiceInteractionLog) error {
	startTime := time.Now()
	defer func() {
		ls.metrics.dbWriteLatency.Observe(time.Since(startTime).Seconds())
	}()

	// Convert metadata map to JSON string
	metadataJSON, err := json.Marshal(log.Metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	query := `INSERT INTO voice_interactions (session_id, event_timestamp, stage, data, latency_ms, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)`

	err = ls.scyllaSession.Query(query,
		log.SessionID,
		log.EventTimestamp,
		log.Stage,
		log.Data,
		log.LatencyMs,
		string(metadataJSON),
		log.CreatedAt,
	).Exec()

	if err != nil {
		return fmt.Errorf("failed to insert into ScyllaDB: %w", err)
	}

	return nil
}

// startHTTPServer starts the HTTP server for health checks and metrics
func (ls *LoggingService) startHTTPServer() {
	defer ls.wg.Done()

	router := mux.NewRouter()

	// Health check endpoint
	router.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":    "healthy",
			"timestamp": time.Now().Format(time.RFC3339),
			"service":   "logging-service",
		})
	}).Methods("GET")

	// Metrics endpoint
	router.Handle("/metrics", promhttp.Handler()).Methods("GET")

	// Ready endpoint
	router.HandleFunc("/ready", func(w http.ResponseWriter, r *http.Request) {
		if ls.scyllaSession != nil {
			w.WriteHeader(http.StatusOK)
		} else {
			w.WriteHeader(http.StatusServiceUnavailable)
		}
	}).Methods("GET")

	port := getEnv("HTTP_PORT", "8080")
	ls.logger.WithField("port", port).Info("Starting HTTP server")

	if err := http.ListenAndServe(":"+port, router); err != nil {
		ls.logger.WithField("error", err).Fatal("HTTP server failed")
	}
}

// Start starts the logging service
func (ls *LoggingService) Start() error {
	// Register metrics
	ls.metrics.RegisterMetrics()

	// Connect to ScyllaDB
	if err := ls.ConnectToScyllaDB(); err != nil {
		return fmt.Errorf("failed to connect to ScyllaDB: %w", err)
	}

	// Start HTTP server
	ls.wg.Add(1)
	go ls.startHTTPServer()

	// Start consumers for each topic
	topics := []string{"stt-results", "llm-requests", "tts-results"}
	for _, topic := range topics {
		ls.wg.Add(1)
		go ls.consumeAndStore(topic)
	}

	ls.logger.Info("Logging service started successfully")
	return nil
}

// getEnv gets an environment variable with a default value
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func main() {
	// Create logging service
	service := NewLoggingService()
	defer service.Close()

	// Start the service
	if err := service.Start(); err != nil {
		log.Fatalf("Failed to start logging service: %v", err)
	}

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	service.logger.Info("Shutting down logging service...")
}
