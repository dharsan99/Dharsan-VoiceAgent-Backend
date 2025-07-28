package pipeline

import (
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"voice-agent-orchestrator/internal/logger"
)

// ServiceState represents the state of a service
type ServiceState string

const (
	ServiceStateIdle      ServiceState = "idle"
	ServiceStateWaiting   ServiceState = "waiting"
	ServiceStateExecuting ServiceState = "executing"
	ServiceStateComplete  ServiceState = "complete"
	ServiceStateError     ServiceState = "error"
)

// PipelineState represents the overall pipeline state
type PipelineState string

const (
	PipelineStateIdle       PipelineState = "idle"
	PipelineStateListening  PipelineState = "listening"
	PipelineStateProcessing PipelineState = "processing"
	PipelineStateComplete   PipelineState = "complete"
	PipelineStateError      PipelineState = "error"
)

// PipelineFlags contains all state information for a session
type PipelineFlags struct {
	SessionID      string                  `json:"session_id"`
	ConversationID string                  `json:"conversation_id"`
	State          PipelineState           `json:"state"`
	Services       map[string]ServiceState `json:"services"`
	Timestamps     map[string]time.Time    `json:"timestamps"`
	Metadata       map[string]interface{}  `json:"metadata"`
	mu             sync.RWMutex
}

// NewPipelineFlags creates a new PipelineFlags instance
func NewPipelineFlags(sessionID string) *PipelineFlags {
	return &PipelineFlags{
		SessionID:      sessionID,
		ConversationID: fmt.Sprintf("conv_%d", time.Now().Unix()),
		State:          PipelineStateIdle,
		Services: map[string]ServiceState{
			"stt": ServiceStateIdle,
			"llm": ServiceStateIdle,
			"tts": ServiceStateIdle,
		},
		Timestamps: make(map[string]time.Time),
		Metadata:   make(map[string]interface{}),
	}
}

// UpdateState updates the pipeline state
func (pf *PipelineFlags) UpdateState(state PipelineState) {
	pf.mu.Lock()
	defer pf.mu.Unlock()

	pf.State = state
	pf.Timestamps[fmt.Sprintf("pipeline_%s", state)] = time.Now()
}

// UpdateServiceState updates a specific service state
func (pf *PipelineFlags) UpdateServiceState(service string, state ServiceState) {
	pf.mu.Lock()
	defer pf.mu.Unlock()

	pf.Services[service] = state
	pf.Timestamps[fmt.Sprintf("%s_%s", service, state)] = time.Now()
}

// GetState returns the current pipeline state
func (pf *PipelineFlags) GetState() PipelineState {
	pf.mu.RLock()
	defer pf.mu.RUnlock()
	return pf.State
}

// GetServiceState returns the current state of a service
func (pf *PipelineFlags) GetServiceState(service string) ServiceState {
	pf.mu.RLock()
	defer pf.mu.RUnlock()
	return pf.Services[service]
}

// UpdateMetadata updates metadata for the pipeline
func (pf *PipelineFlags) UpdateMetadata(key string, value interface{}) {
	pf.mu.Lock()
	defer pf.mu.Unlock()
	pf.Metadata[key] = value
}

// GetMetadata returns metadata for the pipeline
func (pf *PipelineFlags) GetMetadata(key string) interface{} {
	pf.mu.RLock()
	defer pf.mu.RUnlock()
	return pf.Metadata[key]
}

// ToJSON converts the flags to JSON for WebSocket transmission
func (pf *PipelineFlags) ToJSON() ([]byte, error) {
	pf.mu.RLock()
	defer pf.mu.RUnlock()

	// Create a copy for JSON serialization
	flagsCopy := &PipelineFlags{
		SessionID:      pf.SessionID,
		ConversationID: pf.ConversationID,
		State:          pf.State,
		Services:       make(map[string]ServiceState),
		Timestamps:     make(map[string]time.Time),
		Metadata:       make(map[string]interface{}),
	}

	// Copy maps
	for k, v := range pf.Services {
		flagsCopy.Services[k] = v
	}
	for k, v := range pf.Timestamps {
		flagsCopy.Timestamps[k] = v
	}
	for k, v := range pf.Metadata {
		flagsCopy.Metadata[k] = v
	}

	return json.Marshal(flagsCopy)
}

// PipelineStateManager manages pipeline state for all sessions
type PipelineStateManager struct {
	mu       sync.RWMutex
	sessions map[string]*PipelineFlags
	logger   *logger.Logger
}

// NewPipelineStateManager creates a new PipelineStateManager
func NewPipelineStateManager(logger *logger.Logger) *PipelineStateManager {
	return &PipelineStateManager{
		sessions: make(map[string]*PipelineFlags),
		logger:   logger,
	}
}

// CreateSession creates a new session with pipeline flags
func (psm *PipelineStateManager) CreateSession(sessionID string) *PipelineFlags {
	psm.mu.Lock()
	defer psm.mu.Unlock()

	flags := NewPipelineFlags(sessionID)
	psm.sessions[sessionID] = flags

	psm.logger.WithFields(map[string]interface{}{
		"sessionID": sessionID,
		"state":     flags.State,
	}).Info("Created new pipeline session")

	return flags
}

// GetSession returns the pipeline flags for a session
func (psm *PipelineStateManager) GetSession(sessionID string) *PipelineFlags {
	psm.mu.RLock()
	defer psm.mu.RUnlock()

	return psm.sessions[sessionID]
}

// UpdateSessionState updates the state for a session
func (psm *PipelineStateManager) UpdateSessionState(sessionID string, state PipelineState) {
	psm.mu.RLock()
	flags, exists := psm.sessions[sessionID]
	psm.mu.RUnlock()

	if !exists {
		psm.logger.WithField("sessionID", sessionID).Warn("Session not found for state update")
		return
	}

	flags.UpdateState(state)

	psm.logger.WithFields(map[string]interface{}{
		"sessionID": sessionID,
		"state":     state,
	}).Info("Updated pipeline state")
}

// UpdateServiceState updates the state of a service for a session
func (psm *PipelineStateManager) UpdateServiceState(sessionID, service string, state ServiceState) {
	psm.mu.RLock()
	flags, exists := psm.sessions[sessionID]
	psm.mu.RUnlock()

	if !exists {
		psm.logger.WithField("sessionID", sessionID).Warn("Session not found for service state update")
		return
	}

	flags.UpdateServiceState(service, state)

	psm.logger.WithFields(map[string]interface{}{
		"sessionID": sessionID,
		"service":   service,
		"state":     state,
	}).Info("Updated service state")
}

// UpdateSessionMetadata updates metadata for a session
func (psm *PipelineStateManager) UpdateSessionMetadata(sessionID, key string, value interface{}) {
	psm.mu.RLock()
	flags, exists := psm.sessions[sessionID]
	psm.mu.RUnlock()

	if !exists {
		psm.logger.WithField("sessionID", sessionID).Warn("Session not found for metadata update")
		return
	}

	flags.UpdateMetadata(key, value)
}

// RemoveSession removes a session from the state manager
func (psm *PipelineStateManager) RemoveSession(sessionID string) {
	psm.mu.Lock()
	defer psm.mu.Unlock()

	delete(psm.sessions, sessionID)

	psm.logger.WithField("sessionID", sessionID).Info("Removed pipeline session")
}

// GetAllSessions returns all active sessions
func (psm *PipelineStateManager) GetAllSessions() map[string]*PipelineFlags {
	psm.mu.RLock()
	defer psm.mu.RUnlock()

	sessions := make(map[string]*PipelineFlags)
	for k, v := range psm.sessions {
		sessions[k] = v
	}

	return sessions
}

// GetSessionCount returns the number of active sessions
func (psm *PipelineStateManager) GetSessionCount() int {
	psm.mu.RLock()
	defer psm.mu.RUnlock()

	return len(psm.sessions)
}
