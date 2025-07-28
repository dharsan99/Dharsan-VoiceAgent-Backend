package pipeline

import "voice-agent-orchestrator/internal/logger"

// Coordinator interface for pipeline management
type Coordinator interface {
	StartSession(sessionID string) error
	StopSession(sessionID string) error
	TriggerLLM(sessionID string) error
	ProcessFinalTranscript(transcript string) error
	ResetSession(sessionID string) error
	PauseSession(sessionID string) error
	ResumeSession(sessionID string) error
	IsHealthy() bool
}

// DefaultCoordinator implements the Coordinator interface
type DefaultCoordinator struct {
	stateManager *PipelineStateManager
	logger       *logger.Logger
}

// NewDefaultCoordinator creates a new default coordinator
func NewDefaultCoordinator(stateManager *PipelineStateManager, logger *logger.Logger) *DefaultCoordinator {
	return &DefaultCoordinator{
		stateManager: stateManager,
		logger:       logger,
	}
}

// StartSession starts a pipeline session
func (dc *DefaultCoordinator) StartSession(sessionID string) error {
	dc.logger.WithField("sessionID", sessionID).Info("Starting pipeline session")
	dc.stateManager.UpdateSessionState(sessionID, PipelineStateListening)
	return nil
}

// StopSession stops a pipeline session
func (dc *DefaultCoordinator) StopSession(sessionID string) error {
	dc.logger.WithField("sessionID", sessionID).Info("Stopping pipeline session")
	dc.stateManager.UpdateSessionState(sessionID, PipelineStateComplete)
	return nil
}

// TriggerLLM triggers LLM processing for a session
func (dc *DefaultCoordinator) TriggerLLM(sessionID string) error {
	dc.logger.WithField("sessionID", sessionID).Info("Triggering LLM for session")
	dc.stateManager.UpdateServiceState(sessionID, "llm", ServiceStateExecuting)
	return nil
}

// ProcessFinalTranscript is the definitive trigger for the LLM and TTS pipeline.
// It is called by the WebSocket handler upon receiving a 'trigger_llm' event.
func (dc *DefaultCoordinator) ProcessFinalTranscript(transcript string) error {
	dc.logger.WithField("transcript", transcript).Info("Processing final transcript to trigger AI pipeline")

	// Update pipeline state to processing
	dc.stateManager.UpdateSessionState("", PipelineStateProcessing)

	// For now, just log the transcript and update state
	// In a full implementation, this would trigger the actual LLM and TTS pipeline
	dc.logger.WithField("transcript", transcript).Info("Final transcript received, would trigger LLM and TTS pipeline")

	// Update pipeline state to complete
	dc.stateManager.UpdateSessionState("", PipelineStateComplete)

	return nil
}

// ResetSession resets a pipeline session
func (dc *DefaultCoordinator) ResetSession(sessionID string) error {
	dc.logger.WithField("sessionID", sessionID).Info("Resetting pipeline session")
	dc.stateManager.UpdateSessionState(sessionID, PipelineStateIdle)
	return nil
}

// PauseSession pauses a pipeline session
func (dc *DefaultCoordinator) PauseSession(sessionID string) error {
	dc.logger.WithField("sessionID", sessionID).Info("Pausing pipeline session")
	dc.stateManager.UpdateSessionState(sessionID, PipelineStateIdle)
	return nil
}

// ResumeSession resumes a pipeline session
func (dc *DefaultCoordinator) ResumeSession(sessionID string) error {
	dc.logger.WithField("sessionID", sessionID).Info("Resuming pipeline session")
	dc.stateManager.UpdateSessionState(sessionID, PipelineStateListening)
	return nil
}

// IsHealthy checks if the pipeline is healthy
func (dc *DefaultCoordinator) IsHealthy() bool {
	return true // For now, always return healthy
}
