package grpc

import (
	"context"
	"fmt"
	"sync"
	"time"

	"voice-agent-media-server/pkg/logger"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/keepalive"

	pb "voice-agent-media-server/proto"
)

// Client represents a gRPC client for communicating with the Orchestrator
type Client struct {
	conn             *grpc.ClientConn
	client           pb.VoiceAgentServiceClient
	logger           *logger.Logger
	mu               sync.RWMutex
	streams          map[string]pb.VoiceAgentService_StreamAudioClient
	streamsMu        sync.RWMutex
	orchestratorHost string
	orchestratorPort string
}

// NewClient creates a new gRPC client
func NewClient(logger *logger.Logger, orchestratorHost, orchestratorPort string) *Client {
	return &Client{
		logger:           logger,
		orchestratorHost: orchestratorHost,
		orchestratorPort: orchestratorPort,
		streams:          make(map[string]pb.VoiceAgentService_StreamAudioClient),
	}
}

// Connect establishes a connection to the Orchestrator
func (c *Client) Connect() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.conn != nil {
		return nil // Already connected
	}

	address := fmt.Sprintf("%s:%s", c.orchestratorHost, c.orchestratorPort)

	// Configure gRPC connection with keepalive
	conn, err := grpc.Dial(address,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithKeepaliveParams(keepalive.ClientParameters{
			Time:                30 * time.Second,
			Timeout:             5 * time.Second,
			PermitWithoutStream: true,
		}),
		grpc.WithBlock(),
		grpc.WithTimeout(10*time.Second),
	)
	if err != nil {
		return fmt.Errorf("failed to connect to orchestrator: %w", err)
	}

	c.conn = conn
	c.client = pb.NewVoiceAgentServiceClient(conn)

	c.logger.WithFields(map[string]interface{}{
		"address": address,
	}).Info("gRPC client connected to orchestrator")

	return nil
}

// Disconnect closes the gRPC connection
func (c *Client) Disconnect() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	// Close all active streams
	c.streamsMu.Lock()
	for sessionID, stream := range c.streams {
		if stream != nil {
			stream.CloseSend()
		}
		delete(c.streams, sessionID)
	}
	c.streamsMu.Unlock()

	if c.conn != nil {
		if err := c.conn.Close(); err != nil {
			c.logger.WithField("error", err).Error("Failed to close gRPC connection")
			return err
		}
		c.conn = nil
		c.client = nil
	}

	c.logger.Info("gRPC client disconnected from orchestrator")
	return nil
}

// StartAudioStream starts a bidirectional audio stream for a session
func (c *Client) StartAudioStream(sessionID string, responseHandler func(*pb.AudioResponse) error) error {
	c.mu.RLock()
	if c.client == nil {
		c.mu.RUnlock()
		return fmt.Errorf("gRPC client not connected")
	}
	client := c.client
	c.mu.RUnlock()

	// Create bidirectional stream
	stream, err := client.StreamAudio(context.Background())
	if err != nil {
		return fmt.Errorf("failed to create audio stream: %w", err)
	}

	// Store stream
	c.streamsMu.Lock()
	c.streams[sessionID] = stream
	c.streamsMu.Unlock()

	c.logger.WithField("sessionID", sessionID).Info("Started gRPC audio stream")

	// Start goroutine to receive responses
	go c.receiveResponses(sessionID, stream, responseHandler)

	return nil
}

// SendAudioChunk sends an audio chunk to the Orchestrator
func (c *Client) SendAudioChunk(sessionID string, audioData []byte, metadata *pb.AudioMetadata) error {
	c.streamsMu.RLock()
	stream, exists := c.streams[sessionID]
	c.streamsMu.RUnlock()

	if !exists {
		return fmt.Errorf("no active stream for session %s", sessionID)
	}

	chunk := &pb.AudioChunk{
		SessionId: sessionID,
		AudioData: audioData,
		Timestamp: time.Now().UnixNano(),
		Metadata:  metadata,
	}

	if err := stream.Send(chunk); err != nil {
		c.logger.WithFields(map[string]interface{}{
			"sessionID": sessionID,
			"error":     err,
		}).Error("Failed to send audio chunk")
		return err
	}

	return nil
}

// SendControlMessage sends a control message to the Orchestrator
func (c *Client) SendControlMessage(sessionID string, controlType pb.ControlType, parameters map[string]string) (*pb.ControlResponse, error) {
	c.mu.RLock()
	if c.client == nil {
		c.mu.RUnlock()
		return nil, fmt.Errorf("gRPC client not connected")
	}
	client := c.client
	c.mu.RUnlock()

	message := &pb.ControlMessage{
		SessionId:   sessionID,
		ControlType: controlType,
		Parameters:  parameters,
		Timestamp:   time.Now().UnixNano(),
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	response, err := client.SendControlMessage(ctx, message)
	if err != nil {
		c.logger.WithFields(map[string]interface{}{
			"sessionID":   sessionID,
			"controlType": controlType,
			"error":       err,
		}).Error("Failed to send control message")
		return nil, err
	}

	c.logger.WithFields(map[string]interface{}{
		"sessionID":   sessionID,
		"controlType": controlType,
		"success":     response.Success,
	}).Info("Control message sent successfully")

	return response, nil
}

// StopAudioStream stops the audio stream for a session
func (c *Client) StopAudioStream(sessionID string) error {
	c.streamsMu.Lock()
	stream, exists := c.streams[sessionID]
	if exists {
		delete(c.streams, sessionID)
	}
	c.streamsMu.Unlock()

	if stream != nil {
		if err := stream.CloseSend(); err != nil {
			c.logger.WithFields(map[string]interface{}{
				"sessionID": sessionID,
				"error":     err,
			}).Error("Failed to close audio stream")
			return err
		}
	}

	c.logger.WithField("sessionID", sessionID).Info("Stopped gRPC audio stream")
	return nil
}

// HealthCheck performs a health check on the Orchestrator
func (c *Client) HealthCheck() (*pb.HealthResponse, error) {
	c.mu.RLock()
	if c.client == nil {
		c.mu.RUnlock()
		return nil, fmt.Errorf("gRPC client not connected")
	}
	client := c.client
	c.mu.RUnlock()

	request := &pb.HealthRequest{
		ServiceName: "media-server",
		Timestamp:   time.Now().UnixNano(),
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	response, err := client.HealthCheck(ctx, request)
	if err != nil {
		c.logger.WithField("error", err).Error("Health check failed")
		return nil, err
	}

	return response, nil
}

// receiveResponses handles incoming responses from the Orchestrator
func (c *Client) receiveResponses(sessionID string, stream pb.VoiceAgentService_StreamAudioClient, handler func(*pb.AudioResponse) error) {
	defer func() {
		c.streamsMu.Lock()
		delete(c.streams, sessionID)
		c.streamsMu.Unlock()
	}()

	for {
		response, err := stream.Recv()
		if err != nil {
			c.logger.WithFields(map[string]interface{}{
				"sessionID": sessionID,
				"error":     err,
			}).Error("Failed to receive response from orchestrator")
			break
		}

		// Handle the response
		if err := handler(response); err != nil {
			c.logger.WithFields(map[string]interface{}{
				"sessionID": sessionID,
				"error":     err,
			}).Error("Failed to handle response")
		}
	}

	c.logger.WithField("sessionID", sessionID).Info("Response receiver stopped")
}

// IsConnected returns true if the client is connected
func (c *Client) IsConnected() bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.conn != nil && c.client != nil
}

// GetActiveStreams returns the number of active streams
func (c *Client) GetActiveStreams() int {
	c.streamsMu.RLock()
	defer c.streamsMu.RUnlock()
	return len(c.streams)
}
