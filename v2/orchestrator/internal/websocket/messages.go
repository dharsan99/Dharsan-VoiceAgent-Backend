package websocket

import (
	"time"

	"voice-agent-orchestrator/internal/pipeline"
)

// MessageType represents the type of WebSocket message
type MessageType string

const (
	MessageTypePipelineStateUpdate MessageType = "pipeline_state_update"
	MessageTypeServiceStatus       MessageType = "service_status"
	MessageTypeConversationControl MessageType = "conversation_control"
	MessageTypeError               MessageType = "error"
	MessageTypeInfo                MessageType = "info"
)

// PipelineStateMessage represents a pipeline state update message
type PipelineStateMessage struct {
	Type      MessageType                      `json:"type"`
	SessionID string                           `json:"session_id"`
	State     pipeline.PipelineState           `json:"state"`
	Services  map[string]pipeline.ServiceState `json:"services"`
	Timestamp time.Time                        `json:"timestamp"`
	Metadata  map[string]interface{}           `json:"metadata"`
}

// NewPipelineStateMessage creates a new pipeline state message
func NewPipelineStateMessage(sessionID string, flags *pipeline.PipelineFlags) *PipelineStateMessage {
	return &PipelineStateMessage{
		Type:      MessageTypePipelineStateUpdate,
		SessionID: sessionID,
		State:     flags.GetState(),
		Services: map[string]pipeline.ServiceState{
			"stt": flags.GetServiceState("stt"),
			"llm": flags.GetServiceState("llm"),
			"tts": flags.GetServiceState("tts"),
		},
		Timestamp: time.Now(),
		Metadata: map[string]interface{}{
			"buffer_size":   flags.GetMetadata("buffer_size"),
			"audio_quality": flags.GetMetadata("audio_quality"),
		},
	}
}

// ServiceStatusMessage represents a service status update message
type ServiceStatusMessage struct {
	Type      MessageType            `json:"type"`
	Service   string                 `json:"service"`
	State     pipeline.ServiceState  `json:"state"`
	Progress  float64                `json:"progress"`
	Message   string                 `json:"message"`
	Timestamp time.Time              `json:"timestamp"`
	Metadata  map[string]interface{} `json:"metadata"`
}

// NewServiceStatusMessage creates a new service status message
func NewServiceStatusMessage(service string, state pipeline.ServiceState, progress float64, message string) *ServiceStatusMessage {
	return &ServiceStatusMessage{
		Type:      MessageTypeServiceStatus,
		Service:   service,
		State:     state,
		Progress:  progress,
		Message:   message,
		Timestamp: time.Now(),
		Metadata:  make(map[string]interface{}),
	}
}

// ConversationControlMessage represents a conversation control message
type ConversationControlMessage struct {
	Type      MessageType            `json:"type"`
	Action    string                 `json:"action"`
	SessionID string                 `json:"session_id"`
	Timestamp time.Time              `json:"timestamp"`
	Metadata  map[string]interface{} `json:"metadata"`
}

// NewConversationControlMessage creates a new conversation control message
func NewConversationControlMessage(action, sessionID string) *ConversationControlMessage {
	return &ConversationControlMessage{
		Type:      MessageTypeConversationControl,
		Action:    action,
		SessionID: sessionID,
		Timestamp: time.Now(),
		Metadata:  make(map[string]interface{}),
	}
}

// ErrorMessage represents an error message
type ErrorMessage struct {
	Type      MessageType `json:"type"`
	Error     string      `json:"error"`
	Code      string      `json:"code"`
	SessionID string      `json:"session_id,omitempty"`
	Timestamp time.Time   `json:"timestamp"`
}

// NewErrorMessage creates a new error message
func NewErrorMessage(err, code, sessionID string) *ErrorMessage {
	return &ErrorMessage{
		Type:      MessageTypeError,
		Error:     err,
		Code:      code,
		SessionID: sessionID,
		Timestamp: time.Now(),
	}
}

// InfoMessage represents an informational message
type InfoMessage struct {
	Type      MessageType            `json:"type"`
	Message   string                 `json:"message"`
	SessionID string                 `json:"session_id,omitempty"`
	Timestamp time.Time              `json:"timestamp"`
	Metadata  map[string]interface{} `json:"metadata"`
}

// NewInfoMessage creates a new info message
func NewInfoMessage(message, sessionID string) *InfoMessage {
	return &InfoMessage{
		Type:      MessageTypeInfo,
		Message:   message,
		SessionID: sessionID,
		Timestamp: time.Now(),
		Metadata:  make(map[string]interface{}),
	}
}

// Message represents a generic WebSocket message
type Message struct {
	Type      MessageType `json:"type"`
	Data      interface{} `json:"data"`
	Timestamp time.Time   `json:"timestamp"`
}

// NewMessage creates a new generic message
func NewMessage(messageType MessageType, data interface{}) *Message {
	return &Message{
		Type:      messageType,
		Data:      data,
		Timestamp: time.Now(),
	}
}
