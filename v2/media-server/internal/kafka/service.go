package kafka

import (
	"context"
	"fmt"
	"os"
	"sync"
	"time"

	"github.com/pion/rtp"
	"github.com/pion/webrtc/v3"
	"github.com/pion/webrtc/v3/pkg/media"
	"github.com/segmentio/kafka-go"

	"voice-agent-media-server/pkg/logger"
)

// Service handles Kafka/Redpanda operations for the media server
type Service struct {
	producer *kafka.Writer
	consumer *kafka.Reader
	logger   *logger.Logger
	mu       sync.RWMutex
}

// NewService creates a new Kafka service
func NewService(logger *logger.Logger) *Service {
	return &Service{
		logger: logger,
	}
}

// Initialize sets up the Kafka producer and consumer
func (s *Service) Initialize() error {
	// Get Kafka configuration from environment variables
	redpandaHost := os.Getenv("REDPANDA_HOST")
	redpandaPort := os.Getenv("REDPANDA_PORT")

	if redpandaHost == "" {
		redpandaHost = "redpanda.voice-agent-phase5.svc.cluster.local"
	}
	if redpandaPort == "" {
		redpandaPort = "9092"
	}

	kafkaAddr := fmt.Sprintf("%s:%s", redpandaHost, redpandaPort)

	// Debug logging
	fmt.Printf("Media Server Kafka configuration - Host: %s, Port: %s, Address: %s\n", redpandaHost, redpandaPort, kafkaAddr)

	// Initialize producer for audio-in topic
	s.producer = &kafka.Writer{
		Addr:     kafka.TCP(kafkaAddr),
		Topic:    "audio-in",
		Balancer: &kafka.LeastBytes{},
	}

	// Initialize consumer for audio-out topic
	s.consumer = kafka.NewReader(kafka.ReaderConfig{
		Brokers: []string{kafkaAddr},
		Topic:   "audio-out",
		GroupID: "media-server-group",
	})

	s.logger.Info("Kafka service initialized")
	return nil
}

// Close closes the Kafka connections
func (s *Service) Close() error {
	if s.producer != nil {
		if err := s.producer.Close(); err != nil {
			s.logger.WithField("error", err).Error("Failed to close Kafka producer")
		}
	}

	if s.consumer != nil {
		if err := s.consumer.Close(); err != nil {
			s.logger.WithField("error", err).Error("Failed to close Kafka consumer")
		}
	}

	return nil
}

// PublishAudio publishes audio data to the audio-in topic
func (s *Service) PublishAudio(sessionID string, rtpPacket *rtp.Packet) error {
	if s.producer == nil {
		return fmt.Errorf("Kafka producer not initialized")
	}

	// Create message with session ID as key and RTP payload as value
	msg := kafka.Message{
		Key:   []byte(sessionID),
		Value: rtpPacket.Payload,
		Headers: []kafka.Header{
			{Key: "session-id", Value: []byte(sessionID)},
			{Key: "timestamp", Value: []byte(fmt.Sprintf("%d", time.Now().UnixNano()))},
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

	// Log successful publishing (but not too frequently to avoid log spam)
	// We'll let the handler log this instead
	return nil
}

// StartAudioConsumer starts consuming audio from the audio-out topic
func (s *Service) StartAudioConsumer(sessionID string, outboundTrack *webrtc.TrackLocalStaticSample) {
	s.logger.WithField("sessionID", sessionID).Info("Starting audio consumer")

	for {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		msg, err := s.consumer.ReadMessage(ctx)
		cancel()

		if err != nil {
			if err == context.DeadlineExceeded {
				// Timeout - continue listening
				continue
			}
			s.logger.WithFields(map[string]interface{}{
				"sessionID": sessionID,
				"error":     err,
			}).Error("Error reading from Kafka")
			break
		}

		// Check if this message is for our session
		if string(msg.Key) != sessionID {
			continue
		}

		// For now, we'll assume the audio data is already in the correct format
		// In a real implementation, you'd need to handle audio format conversion
		if err := outboundTrack.WriteSample(media.Sample{
			Data:     msg.Value,
			Duration: 20 * time.Millisecond,
		}); err != nil {
			s.logger.WithFields(map[string]interface{}{
				"sessionID": sessionID,
				"error":     err,
			}).Error("Failed to write sample to WebRTC track")
			break
		}
	}

	s.logger.WithField("sessionID", sessionID).Info("Audio consumer stopped")
}
