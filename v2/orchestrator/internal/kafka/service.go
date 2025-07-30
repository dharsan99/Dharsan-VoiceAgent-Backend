package kafka

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"time"

	"voice-agent-orchestrator/internal/logger"

	"github.com/segmentio/kafka-go"
)

// AudioMessage represents an audio message from Kafka
type AudioMessage struct {
	SessionID string
	AudioData []byte
	Timestamp time.Time
}

// VoiceInteractionLog represents the data structure for logging
type VoiceInteractionLog struct {
	SessionID      string            `json:"session_id"`
	EventTimestamp time.Time         `json:"event_timestamp"`
	Stage          string            `json:"stage"`
	Data           string            `json:"data"`
	LatencyMs      int               `json:"latency_ms"`
	Metadata       map[string]string `json:"metadata"`
	CreatedAt      time.Time         `json:"created_at"`
}

// Service handles Kafka operations for the orchestrator
type Service struct {
	consumer    *kafka.Reader
	producer    *kafka.Writer
	logProducer *kafka.Writer // Producer for intermediate logging topics
	logger      *logger.Logger
}

// NewService creates a new Kafka service
func NewService(logger *logger.Logger) *Service {
	return &Service{
		logger: logger,
	}
}

// Initialize sets up the Kafka consumer and producer
func (s *Service) Initialize() error {
	// Get Kafka configuration from environment variables
	redpandaHost := os.Getenv("REDPANDA_HOST")
	redpandaPort := os.Getenv("REDPANDA_PORT")

	if redpandaHost == "" {
		redpandaHost = "redpanda.voice-agent-fresh.svc.cluster.local"
	}
	if redpandaPort == "" {
		redpandaPort = "9092"
	}

	kafkaAddr := fmt.Sprintf("%s:%s", redpandaHost, redpandaPort)

	// Debug logging
	fmt.Printf("Kafka configuration - Host: %s, Port: %s, Address: %s\n", redpandaHost, redpandaPort, kafkaAddr)

	// Initialize consumer for audio-in topic
	s.consumer = kafka.NewReader(kafka.ReaderConfig{
		Brokers: []string{kafkaAddr},
		Topic:   "audio-in",
		GroupID: "orchestrator-group-v2",
	})

	// Initialize producer for audio-out topic
	s.producer = &kafka.Writer{
		Addr:     kafka.TCP(kafkaAddr),
		Topic:    "audio-out",
		Balancer: &kafka.LeastBytes{},
	}

	// Initialize producer for intermediate logging topics
	s.logProducer = &kafka.Writer{
		Addr:     kafka.TCP(kafkaAddr),
		Balancer: &kafka.LeastBytes{},
	}

	s.logger.Info("Kafka service initialized with intermediate logging support")
	return nil
}

// Close closes the Kafka connections
func (s *Service) Close() error {
	if s.consumer != nil {
		if err := s.consumer.Close(); err != nil {
			s.logger.WithField("error", err).Error("Failed to close Kafka consumer")
		}
	}

	if s.producer != nil {
		if err := s.producer.Close(); err != nil {
			s.logger.WithField("error", err).Error("Failed to close Kafka producer")
		}
	}

	if s.logProducer != nil {
		if err := s.logProducer.Close(); err != nil {
			s.logger.WithField("error", err).Error("Failed to close Kafka log producer")
		}
	}

	return nil
}

// ConsumeAudio consumes audio from the audio-in topic
func (s *Service) ConsumeAudio() (*AudioMessage, error) {
	if s.consumer == nil {
		return nil, fmt.Errorf("Kafka consumer not initialized")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	msg, err := s.consumer.ReadMessage(ctx)
	if err != nil {
		return nil, err
	}

	// Parse timestamp from headers
	timestamp := time.Now()
	for _, header := range msg.Headers {
		if header.Key == "timestamp" {
			if ts, err := time.Parse(time.RFC3339, string(header.Value)); err == nil {
				timestamp = ts
			}
			break
		}
	}

	return &AudioMessage{
		SessionID: string(msg.Key),
		AudioData: msg.Value,
		Timestamp: timestamp,
	}, nil
}

// PublishAudio publishes audio to the audio-out topic
func (s *Service) PublishAudio(sessionID string, audioData []byte) error {
	if s.producer == nil {
		return fmt.Errorf("Kafka producer not initialized")
	}

	msg := kafka.Message{
		Key:   []byte(sessionID),
		Value: audioData,
		Headers: []kafka.Header{
			{Key: "session-id", Value: []byte(sessionID)},
			{Key: "timestamp", Value: []byte(time.Now().Format(time.RFC3339))},
		},
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := s.producer.WriteMessages(ctx, msg); err != nil {
		s.logger.WithFields(map[string]interface{}{
			"sessionID": sessionID,
			"error":     err,
		}).Error("Failed to publish audio to Kafka")
		return err
	}

	return nil
}

// PublishLog publishes structured logs to intermediate topics
func (s *Service) PublishLog(topic string, logData VoiceInteractionLog) error {
	if s.logProducer == nil {
		return fmt.Errorf("Kafka log producer not initialized")
	}

	// Set default values if not provided
	if logData.CreatedAt.IsZero() {
		logData.CreatedAt = time.Now()
	}
	if logData.EventTimestamp.IsZero() {
		logData.EventTimestamp = time.Now()
	}
	if logData.Metadata == nil {
		logData.Metadata = make(map[string]string)
	}

	// Add service information to metadata
	logData.Metadata["service"] = "orchestrator"
	logData.Metadata["version"] = "phase3"

	// Serialize log data to JSON
	payload, err := json.Marshal(logData)
	if err != nil {
		return fmt.Errorf("failed to marshal log data: %w", err)
	}

	// Create message with topic-specific configuration
	msg := kafka.Message{
		Topic: topic,
		Key:   []byte(logData.SessionID),
		Value: payload,
		Headers: []kafka.Header{
			{Key: "session-id", Value: []byte(logData.SessionID)},
			{Key: "stage", Value: []byte(logData.Stage)},
			{Key: "timestamp", Value: []byte(time.Now().Format(time.RFC3339))},
		},
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := s.logProducer.WriteMessages(ctx, msg); err != nil {
		s.logger.WithFields(map[string]interface{}{
			"topic":     topic,
			"sessionID": logData.SessionID,
			"stage":     logData.Stage,
			"error":     err,
		}).Error("Failed to publish log to Kafka")
		return err
	}

	s.logger.WithFields(map[string]interface{}{
		"topic":     topic,
		"sessionID": logData.SessionID,
		"stage":     logData.Stage,
		"latency":   logData.LatencyMs,
	}).Debug("Published log to intermediate topic")

	return nil
}

// PublishSTTResult publishes STT results to stt-results topic
func (s *Service) PublishSTTResult(sessionID, transcript string, latencyMs int, metadata map[string]string) error {
	logData := VoiceInteractionLog{
		SessionID:      sessionID,
		EventTimestamp: time.Now(),
		Stage:          "stt",
		Data:           transcript,
		LatencyMs:      latencyMs,
		Metadata:       metadata,
		CreatedAt:      time.Now(),
	}

	return s.PublishLog("stt-results", logData)
}

// PublishLLMRequest publishes LLM requests to llm-requests topic
func (s *Service) PublishLLMRequest(sessionID, response string, latencyMs int, metadata map[string]string) error {
	logData := VoiceInteractionLog{
		SessionID:      sessionID,
		EventTimestamp: time.Now(),
		Stage:          "llm",
		Data:           response,
		LatencyMs:      latencyMs,
		Metadata:       metadata,
		CreatedAt:      time.Now(),
	}

	return s.PublishLog("llm-requests", logData)
}

// PublishTTSResult publishes TTS results to tts-results topic
func (s *Service) PublishTTSResult(sessionID string, audioSize int, latencyMs int, metadata map[string]string) error {
	logData := VoiceInteractionLog{
		SessionID:      sessionID,
		EventTimestamp: time.Now(),
		Stage:          "tts",
		Data:           fmt.Sprintf("audio_size:%d", audioSize),
		LatencyMs:      latencyMs,
		Metadata:       metadata,
		CreatedAt:      time.Now(),
	}

	return s.PublishLog("tts-results", logData)
}
