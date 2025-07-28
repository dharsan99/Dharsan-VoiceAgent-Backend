package websocket

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"voice-agent-orchestrator/internal/logger"
	"voice-agent-orchestrator/internal/pipeline"
	"voice-agent-orchestrator/internal/session"
	pb "voice-agent-orchestrator/proto"

	"github.com/gorilla/websocket"
)

// GRPCWebSocketHandler handles WebSocket connections that bridge to gRPC
type GRPCWebSocketHandler struct {
	logger        *logger.Logger
	pipelineCoord pipeline.Coordinator
	sessionMgr    *session.Manager
	upgrader      websocket.Upgrader
}

// WSMessage represents a WebSocket message
type WSMessage struct {
	ID     int         `json:"id,omitempty"`
	Method string      `json:"method"`
	Params interface{} `json:"params"`
}

// Response represents a WebSocket response
type Response struct {
	ID     int         `json:"id,omitempty"`
	Result interface{} `json:"result,omitempty"`
	Error  string      `json:"error,omitempty"`
}

// NewGRPCWebSocketHandler creates a new gRPC WebSocket handler
func NewGRPCWebSocketHandler(logger *logger.Logger, pipelineCoord pipeline.Coordinator, sessionMgr *session.Manager) *GRPCWebSocketHandler {
	return &GRPCWebSocketHandler{
		logger:        logger,
		pipelineCoord: pipelineCoord,
		sessionMgr:    sessionMgr,
		upgrader: websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool {
				return true // Allow all origins for development
			},
		},
	}
}

// HandleWebSocket handles WebSocket connections
func (h *GRPCWebSocketHandler) HandleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := h.upgrader.Upgrade(w, r, nil)
	if err != nil {
		h.logger.WithField("error", err).Error("Failed to upgrade WebSocket connection")
		return
	}
	defer conn.Close()

	h.logger.Info("gRPC WebSocket client connected")

	// Handle messages
	for {
		var msg WSMessage
		err := conn.ReadJSON(&msg)
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				h.logger.WithField("error", err).Error("WebSocket read error")
			}
			break
		}

		// Handle the message
		response := h.handleMessage(msg)

		// Send response
		if err := conn.WriteJSON(response); err != nil {
			h.logger.WithField("error", err).Error("Failed to send WebSocket response")
			break
		}
	}

	h.logger.Info("gRPC WebSocket client disconnected")
}

// handleMessage processes incoming WebSocket messages
func (h *GRPCWebSocketHandler) handleMessage(msg WSMessage) Response {
	h.logger.WithField("method", msg.Method).Info("Processing WebSocket message")

	switch msg.Method {
	case "HealthCheck":
		return h.handleHealthCheck(msg)
	case "SendControlMessage":
		return h.handleControlMessage(msg)
	case "StreamAudio":
		return h.handleStreamAudio(msg)
	case "AudioChunk":
		return h.handleAudioChunk(msg)
	default:
		return Response{
			ID:    msg.ID,
			Error: fmt.Sprintf("Unknown method: %s", msg.Method),
		}
	}
}

// handleHealthCheck handles health check requests
func (h *GRPCWebSocketHandler) handleHealthCheck(msg WSMessage) Response {
	var params struct {
		ServiceName string `json:"service_name"`
		Timestamp   int64  `json:"timestamp"`
	}

	if err := h.parseParams(msg.Params, &params); err != nil {
		return Response{
			ID:    msg.ID,
			Error: fmt.Sprintf("Invalid parameters: %v", err),
		}
	}

	// Create health request
	req := &pb.HealthRequest{
		ServiceName: params.ServiceName,
		Timestamp:   params.Timestamp,
	}

	// Call gRPC health check
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// Since we don't have direct gRPC access here, we'll simulate the response
	// In a real implementation, you'd call the actual gRPC service
	response := &pb.HealthResponse{
		ServiceName: params.ServiceName,
		Healthy:     true,
		Status:      "healthy",
		Metadata: map[string]string{
			"active_sessions":  fmt.Sprintf("%d", h.sessionMgr.GetActiveSessionCount()),
			"pipeline_healthy": "true",
			"version":          "2.0.0",
			"phase":            "5",
		},
	}

	return Response{
		ID:     msg.ID,
		Result: response,
	}
}

// handleControlMessage handles control message requests
func (h *GRPCWebSocketHandler) handleControlMessage(msg WSMessage) Response {
	var params struct {
		SessionID   string            `json:"session_id"`
		ControlType string            `json:"control_type"`
		Parameters  map[string]string `json:"parameters"`
		Timestamp   int64             `json:"timestamp"`
	}

	if err := h.parseParams(msg.Params, &params); err != nil {
		return Response{
			ID:    msg.ID,
			Error: fmt.Sprintf("Invalid parameters: %v", err),
		}
	}

	// Create control message
	controlMsg := &pb.ControlMessage{
		SessionId:   params.SessionID,
		ControlType: h.parseControlType(params.ControlType),
		Parameters:  params.Parameters,
		Timestamp:   params.Timestamp,
	}

	// Process control message
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// Simulate gRPC call
	var response *pb.ControlResponse
	switch params.ControlType {
	case "CONTROL_TYPE_START_LISTENING":
		response = &pb.ControlResponse{
			SessionId: params.SessionID,
			Success:   true,
			Message:   "Started listening",
		}
	case "CONTROL_TYPE_STOP_LISTENING":
		response = &pb.ControlResponse{
			SessionId: params.SessionID,
			Success:   true,
			Message:   "Stopped listening",
		}
	case "CONTROL_TYPE_TRIGGER_LLM":
		response = &pb.ControlResponse{
			SessionId: params.SessionID,
			Success:   true,
			Message:   "LLM triggered",
		}
	default:
		response = &pb.ControlResponse{
			SessionId: params.SessionID,
			Success:   false,
			Message:   fmt.Sprintf("Unknown control type: %s", params.ControlType),
		}
	}

	return Response{
		ID:     msg.ID,
		Result: response,
	}
}

// handleStreamAudio handles audio stream requests
func (h *GRPCWebSocketHandler) handleStreamAudio(msg WSMessage) Response {
	var params struct {
		SessionID   string `json:"session_id"`
		StartStream bool   `json:"start_stream"`
	}

	if err := h.parseParams(msg.Params, &params); err != nil {
		return Response{
			ID:    msg.ID,
			Error: fmt.Sprintf("Invalid parameters: %v", err),
		}
	}

	if params.StartStream {
		// Start the pipeline for this session
		if err := h.pipelineCoord.StartSession(params.SessionID); err != nil {
			return Response{
				ID:    msg.ID,
				Error: fmt.Sprintf("Failed to start session: %v", err),
			}
		}

		h.logger.WithField("sessionID", params.SessionID).Info("Started audio stream session")
	}

	return Response{
		ID: msg.ID,
		Result: map[string]interface{}{
			"session_id": params.SessionID,
			"status":     "stream_started",
		},
	}
}

// handleAudioChunk handles audio chunk data
func (h *GRPCWebSocketHandler) handleAudioChunk(msg WSMessage) Response {
	var params struct {
		SessionID string                 `json:"session_id"`
		AudioData []byte                 `json:"audio_data"`
		Timestamp int64                  `json:"timestamp"`
		Metadata  map[string]interface{} `json:"metadata"`
	}

	if err := h.parseParams(msg.Params, &params); err != nil {
		return Response{
			Error: fmt.Sprintf("Invalid parameters: %v", err),
		}
	}

	// Process audio chunk
	audioChunk := &pb.AudioChunk{
		SessionId: params.SessionID,
		AudioData: params.AudioData,
		Timestamp: params.Timestamp,
		Metadata: &pb.AudioMetadata{
			EnergyLevel:   h.getFloat64(params.Metadata, "energy_level"),
			VoiceActivity: h.getBool(params.Metadata, "voice_activity"),
			Confidence:    h.getFloat64(params.Metadata, "confidence"),
			AudioFormat:   h.getString(params.Metadata, "audio_format"),
			SampleRate:    int32(h.getFloat64(params.Metadata, "sample_rate")),
			Channels:      int32(h.getFloat64(params.Metadata, "channels")),
		},
	}

	// Simulate processing the audio chunk
	// In a real implementation, you'd send this to the STT service
	h.logger.WithField("sessionID", params.SessionID).Info("Processing audio chunk")

	// Simulate a response
	response := &pb.AudioResponse{
		SessionId:    params.SessionID,
		ResponseType: pb.ResponseType_RESPONSE_TYPE_INTERIM,
		Transcript:   "Processing audio...",
		Confidence:   0.8,
	}

	return Response{
		Result: response,
	}
}

// parseParams parses message parameters into a struct
func (h *GRPCWebSocketHandler) parseParams(params interface{}, target interface{}) error {
	data, err := json.Marshal(params)
	if err != nil {
		return err
	}
	return json.Unmarshal(data, target)
}

// parseControlType converts string control type to protobuf enum
func (h *GRPCWebSocketHandler) parseControlType(controlType string) pb.ControlType {
	switch controlType {
	case "CONTROL_TYPE_START_LISTENING":
		return pb.ControlType_CONTROL_TYPE_START_LISTENING
	case "CONTROL_TYPE_STOP_LISTENING":
		return pb.ControlType_CONTROL_TYPE_STOP_LISTENING
	case "CONTROL_TYPE_TRIGGER_LLM":
		return pb.ControlType_CONTROL_TYPE_TRIGGER_LLM
	default:
		return pb.ControlType_CONTROL_TYPE_UNKNOWN
	}
}

// Helper functions for metadata parsing
func (h *GRPCWebSocketHandler) getFloat64(metadata map[string]interface{}, key string) float64 {
	if val, ok := metadata[key]; ok {
		if f, ok := val.(float64); ok {
			return f
		}
	}
	return 0.0
}

func (h *GRPCWebSocketHandler) getBool(metadata map[string]interface{}, key string) bool {
	if val, ok := metadata[key]; ok {
		if b, ok := val.(bool); ok {
			return b
		}
	}
	return false
}

func (h *GRPCWebSocketHandler) getString(metadata map[string]interface{}, key string) string {
	if val, ok := metadata[key]; ok {
		if s, ok := val.(string); ok {
			return s
		}
	}
	return ""
}
