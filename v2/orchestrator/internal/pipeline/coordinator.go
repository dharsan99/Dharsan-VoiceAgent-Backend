package pipeline

import (
	"encoding/base64"
	"fmt"
	"math"
	"regexp"
	"strings"
	"time"

	"voice-agent-orchestrator/internal/ai"
	"voice-agent-orchestrator/internal/logger"
)

// WebSocketBroadcaster interface for broadcasting messages
type WebSocketBroadcaster interface {
	BroadcastToSession(sessionID string, message interface{})
}

// ServiceCoordinator manages the pipeline flow with state tracking
type ServiceCoordinator struct {
	sessionID    string
	flags        *PipelineFlags
	logger       *logger.Logger
	websocket    WebSocketBroadcaster
	aiService    *ai.Service
	stateManager *PipelineStateManager
}

// NewServiceCoordinator creates a new service coordinator
func NewServiceCoordinator(sessionID string, flags *PipelineFlags, logger *logger.Logger, websocket WebSocketBroadcaster, aiService *ai.Service, stateManager *PipelineStateManager) *ServiceCoordinator {
	return &ServiceCoordinator{
		sessionID:    sessionID,
		flags:        flags,
		logger:       logger,
		websocket:    websocket,
		aiService:    aiService,
		stateManager: stateManager,
	}
}

// ProcessPipeline processes the complete AI pipeline with state tracking
func (sc *ServiceCoordinator) ProcessPipeline(audioData []byte) error {
	sc.logger.WithField("sessionID", sc.sessionID).Info("Starting AI pipeline with state tracking")

	// Update pipeline state to processing
	sc.stateManager.UpdateSessionState(sc.sessionID, PipelineStateProcessing)
	sc.broadcastStateUpdate()

	// Update metadata with buffer size
	sc.stateManager.UpdateSessionMetadata(sc.sessionID, "buffer_size", len(audioData))

	// Step 1: STT Processing
	if err := sc.processSTT(audioData); err != nil {
		sc.handlePipelineError("stt", err)
		return err
	}

	// Get the transcript from STT
	transcript := sc.flags.GetMetadata("transcript").(string)
	if transcript == "" {
		sc.logger.WithField("sessionID", sc.sessionID).Warn("Empty transcript received from STT")
		sc.stateManager.UpdateSessionState(sc.sessionID, PipelineStateComplete)
		sc.broadcastStateUpdate()
		return nil
	}

	// Step 2: LLM Processing
	if err := sc.processLLM(transcript); err != nil {
		sc.handlePipelineError("llm", err)
		return err
	}

	// Get the response from LLM
	response := sc.flags.GetMetadata("llm_response").(string)
	if response == "" {
		sc.logger.WithField("sessionID", sc.sessionID).Warn("Empty response received from LLM")
		sc.stateManager.UpdateSessionState(sc.sessionID, PipelineStateComplete)
		sc.broadcastStateUpdate()
		return nil
	}

	// Step 3: TTS Processing
	if err := sc.processTTS(response); err != nil {
		sc.handlePipelineError("tts", err)
		return err
	}

	// Pipeline complete
	sc.stateManager.UpdateSessionState(sc.sessionID, PipelineStateComplete)
	sc.broadcastStateUpdate()

	sc.logger.WithField("sessionID", sc.sessionID).Info("AI pipeline completed successfully")
	return nil
}

// generateTestAudio creates a simple test audio tone for demonstration
func generateTestAudio(text string) []byte {
	// Generate a simple 1-second sine wave at 440Hz (A4 note)
	sampleRate := 16000
	duration := 1.0    // 1 second
	frequency := 440.0 // A4 note
	amplitude := 0.3

	numSamples := int(float64(sampleRate) * duration)
	audioData := make([]byte, numSamples*2) // 16-bit samples

	for i := 0; i < numSamples; i++ {
		// Generate sine wave
		sample := amplitude * math.Sin(2*math.Pi*frequency*float64(i)/float64(sampleRate))

		// Convert to 16-bit PCM
		pcmSample := int16(sample * 32767)

		// Write as little-endian 16-bit
		audioData[i*2] = byte(pcmSample & 0xFF)
		audioData[i*2+1] = byte((pcmSample >> 8) & 0xFF)
	}

	return audioData
}

// processSTT handles STT processing with state tracking
func (sc *ServiceCoordinator) processSTT(audioData []byte) error {
	// Update STT to waiting
	sc.stateManager.UpdateServiceState(sc.sessionID, "stt", ServiceStateWaiting)
	sc.broadcastServiceStatus("stt", ServiceStateWaiting, 0.0, "Waiting to start transcription...")

	// Update STT to executing
	sc.stateManager.UpdateServiceState(sc.sessionID, "stt", ServiceStateExecuting)
	sc.broadcastServiceStatus("stt", ServiceStateExecuting, 0.25, "Transcribing audio...")

	// Process STT
	startTime := time.Now()
	sttResp, err := sc.aiService.SpeechToTextWithInterim(audioData)
	if err != nil {
		sc.stateManager.UpdateServiceState(sc.sessionID, "stt", ServiceStateError)
		sc.broadcastServiceStatus("stt", ServiceStateError, 0.0, fmt.Sprintf("STT error: %v", err))
		return fmt.Errorf("STT processing failed: %v", err)
	}

	// Update STT to complete
	sc.stateManager.UpdateServiceState(sc.sessionID, "stt", ServiceStateComplete)
	sc.broadcastServiceStatus("stt", ServiceStateComplete, 1.0, "Transcription complete")

	// Store transcript and timing
	processingTime := time.Since(startTime).Milliseconds()
	sc.stateManager.UpdateSessionMetadata(sc.sessionID, "transcript", sttResp.Transcription)
	sc.stateManager.UpdateSessionMetadata(sc.sessionID, "stt_processing_time", processingTime)
	sc.stateManager.UpdateSessionMetadata(sc.sessionID, "stt_confidence", sttResp.Confidence)

	sc.logger.WithFields(map[string]interface{}{
		"sessionID":      sc.sessionID,
		"transcript":     sttResp.Transcription,
		"processingTime": processingTime,
		"confidence":     sttResp.Confidence,
	}).Info("STT processing completed")

	return nil
}

// processLLM handles LLM processing with state tracking
func (sc *ServiceCoordinator) processLLM(transcript string) error {
	// Update LLM to waiting
	sc.stateManager.UpdateServiceState(sc.sessionID, "llm", ServiceStateWaiting)
	sc.broadcastServiceStatus("llm", ServiceStateWaiting, 0.0, "Waiting to generate response...")

	// Update LLM to executing
	sc.stateManager.UpdateServiceState(sc.sessionID, "llm", ServiceStateExecuting)
	sc.broadcastServiceStatus("llm", ServiceStateExecuting, 0.25, "Generating AI response...")

	// Process LLM
	startTime := time.Now()
	response, err := sc.aiService.GenerateResponse(transcript)
	if err != nil {
		sc.stateManager.UpdateServiceState(sc.sessionID, "llm", ServiceStateError)
		sc.broadcastServiceStatus("llm", ServiceStateError, 0.0, fmt.Sprintf("LLM error: %v", err))
		return fmt.Errorf("LLM processing failed: %v", err)
	}

	// Update LLM to complete
	sc.stateManager.UpdateServiceState(sc.sessionID, "llm", ServiceStateComplete)
	sc.broadcastServiceStatus("llm", ServiceStateComplete, 1.0, "Response generated")

	// Clean the LLM response for TTS by removing think tags and extracting only the actual response
	cleanResponse := sc.cleanLLMResponseForTTS(response)
	sc.logger.WithFields(map[string]interface{}{
		"sessionID":   sc.sessionID,
		"llm_raw":     response,
		"llm_cleaned": cleanResponse,
	}).Info("Storing cleaned LLM response in session metadata")

	// Store response and timing
	processingTime := time.Since(startTime).Milliseconds()
	sc.stateManager.UpdateSessionMetadata(sc.sessionID, "llm_response", cleanResponse)
	sc.stateManager.UpdateSessionMetadata(sc.sessionID, "llm_processing_time", processingTime)

	// Send LLM response text to frontend
	llmResponseMsg := map[string]interface{}{
		"event":      "llm_response_text",
		"text":       cleanResponse,
		"session_id": sc.sessionID,
		"timestamp":  time.Now(),
	}
	sc.websocket.BroadcastToSession(sc.sessionID, llmResponseMsg)

	sc.logger.WithFields(map[string]interface{}{
		"sessionID":      sc.sessionID,
		"response":       cleanResponse,
		"processingTime": processingTime,
	}).Info("LLM processing completed")

	return nil
}

// processTTS handles TTS processing with state tracking
func (sc *ServiceCoordinator) processTTS(response string) error {
	// Debug log: show text being sent to TTS
	sc.logger.WithFields(map[string]interface{}{
		"sessionID": sc.sessionID,
		"tts_input": response,
	}).Info("Text sent to TTS service")
	// Update TTS to waiting
	sc.stateManager.UpdateServiceState(sc.sessionID, "tts", ServiceStateWaiting)
	sc.broadcastServiceStatus("tts", ServiceStateWaiting, 0.0, "Waiting to generate audio...")

	// Update TTS to executing
	sc.stateManager.UpdateServiceState(sc.sessionID, "tts", ServiceStateExecuting)
	sc.broadcastServiceStatus("tts", ServiceStateExecuting, 0.25, "Generating audio response...")

	// Process TTS
	startTime := time.Now()
	audioData, err := sc.aiService.TextToSpeech(response)
	if err != nil {
		sc.stateManager.UpdateServiceState(sc.sessionID, "tts", ServiceStateError)
		sc.broadcastServiceStatus("tts", ServiceStateError, 0.0, fmt.Sprintf("TTS error: %v", err))
		return fmt.Errorf("TTS processing failed: %v", err)
	}

	// If TTS returns empty audio, generate a simple test tone
	if len(audioData) == 0 {
		sc.logger.WithField("sessionID", sc.sessionID).Warn("TTS returned empty audio, generating test tone")
		audioData = generateTestAudio(response)
	}

	// Update TTS to complete
	sc.stateManager.UpdateServiceState(sc.sessionID, "tts", ServiceStateComplete)
	sc.broadcastServiceStatus("tts", ServiceStateComplete, 1.0, "Audio generated")

	// Store audio and timing
	processingTime := time.Since(startTime).Milliseconds()
	sc.stateManager.UpdateSessionMetadata(sc.sessionID, "tts_audio", audioData)
	sc.stateManager.UpdateSessionMetadata(sc.sessionID, "tts_processing_time", processingTime)
	sc.stateManager.UpdateSessionMetadata(sc.sessionID, "tts_audio_size", len(audioData))

	// Send audio data to frontend (base64 encoded)
	audioBase64 := base64.StdEncoding.EncodeToString(audioData)
	audioMsg := map[string]interface{}{
		"event":      "tts_audio_chunk",
		"audio_data": audioBase64,
		"session_id": sc.sessionID,
		"timestamp":  time.Now(),
	}
	sc.websocket.BroadcastToSession(sc.sessionID, audioMsg)

	sc.logger.WithFields(map[string]interface{}{
		"sessionID":      sc.sessionID,
		"audioSize":      len(audioData),
		"processingTime": processingTime,
	}).Info("TTS processing completed")

	return nil
}

// cleanLLMResponseForTTS cleans the LLM response by removing think tags and extracting only the actual response
func (sc *ServiceCoordinator) cleanLLMResponseForTTS(response string) string {
	// Remove <think> tags and their content
	// This regex pattern matches <think>...</think> tags and removes them
	thinkPattern := regexp.MustCompile(`(?s)<think>.*?</think>`)
	cleaned := thinkPattern.ReplaceAllString(response, "")

	// Remove any remaining XML-like tags
	tagPattern := regexp.MustCompile(`<[^>]*>`)
	cleaned = tagPattern.ReplaceAllString(cleaned, "")

	// Clean up extra whitespace and newlines
	cleaned = strings.TrimSpace(cleaned)

	// Replace multiple newlines with single newlines
	newlinePattern := regexp.MustCompile(`\n+`)
	cleaned = newlinePattern.ReplaceAllString(cleaned, "\n")

	// Replace multiple spaces with single spaces
	spacePattern := regexp.MustCompile(` +`)
	cleaned = spacePattern.ReplaceAllString(cleaned, " ")

	// If the cleaned response is empty, return a fallback message
	if cleaned == "" {
		cleaned = "I understand. How can I help you?"
	}

	return cleaned
}

// handlePipelineError handles pipeline errors with state tracking
func (sc *ServiceCoordinator) handlePipelineError(service string, err error) {
	sc.stateManager.UpdateServiceState(sc.sessionID, service, ServiceStateError)
	sc.stateManager.UpdateSessionState(sc.sessionID, PipelineStateError)

	errorMsg := map[string]interface{}{
		"type":       "error",
		"error":      err.Error(),
		"code":       "pipeline_error",
		"session_id": sc.sessionID,
		"timestamp":  time.Now(),
	}
	sc.websocket.BroadcastToSession(sc.sessionID, errorMsg)

	sc.logger.WithFields(map[string]interface{}{
		"sessionID": sc.sessionID,
		"service":   service,
		"error":     err.Error(),
	}).Error("Pipeline error occurred")
}

// broadcastStateUpdate broadcasts the current pipeline state
func (sc *ServiceCoordinator) broadcastStateUpdate() {
	stateMsg := map[string]interface{}{
		"type":       "pipeline_state_update",
		"session_id": sc.sessionID,
		"state":      sc.flags.GetState(),
		"services": map[string]string{
			"stt": string(sc.flags.GetServiceState("stt")),
			"llm": string(sc.flags.GetServiceState("llm")),
			"tts": string(sc.flags.GetServiceState("tts")),
		},
		"timestamp": time.Now(),
		"metadata": map[string]interface{}{
			"buffer_size":   sc.flags.GetMetadata("buffer_size"),
			"audio_quality": sc.flags.GetMetadata("audio_quality"),
		},
	}
	sc.websocket.BroadcastToSession(sc.sessionID, stateMsg)
}

// broadcastServiceStatus broadcasts service status updates
func (sc *ServiceCoordinator) broadcastServiceStatus(service string, state ServiceState, progress float64, message string) {
	statusMsg := map[string]interface{}{
		"type":      "service_status",
		"service":   service,
		"state":     string(state),
		"progress":  progress,
		"message":   message,
		"timestamp": time.Now(),
	}
	sc.websocket.BroadcastToSession(sc.sessionID, statusMsg)
}

// StartListening updates the pipeline state to listening
func (sc *ServiceCoordinator) StartListening() {
	sc.stateManager.UpdateSessionState(sc.sessionID, PipelineStateListening)
	sc.broadcastStateUpdate()

	infoMsg := map[string]interface{}{
		"type":       "info",
		"message":    "Started listening for audio input",
		"session_id": sc.sessionID,
		"timestamp":  time.Now(),
	}
	sc.websocket.BroadcastToSession(sc.sessionID, infoMsg)

	sc.logger.WithField("sessionID", sc.sessionID).Info("Started listening")
}

// StopConversation stops the conversation and resets states
func (sc *ServiceCoordinator) StopConversation() {
	// Reset all service states to idle
	sc.stateManager.UpdateServiceState(sc.sessionID, "stt", ServiceStateIdle)
	sc.stateManager.UpdateServiceState(sc.sessionID, "llm", ServiceStateIdle)
	sc.stateManager.UpdateServiceState(sc.sessionID, "tts", ServiceStateIdle)

	// Update pipeline state to idle
	sc.stateManager.UpdateSessionState(sc.sessionID, PipelineStateIdle)
	sc.broadcastStateUpdate()

	controlMsg := map[string]interface{}{
		"type":       "conversation_control",
		"action":     "stop",
		"session_id": sc.sessionID,
		"timestamp":  time.Now(),
	}
	sc.websocket.BroadcastToSession(sc.sessionID, controlMsg)

	sc.logger.WithField("sessionID", sc.sessionID).Info("Stopped conversation")
}

// PauseConversation pauses the conversation
func (sc *ServiceCoordinator) PauseConversation() {
	controlMsg := map[string]interface{}{
		"type":       "conversation_control",
		"action":     "pause",
		"session_id": sc.sessionID,
		"timestamp":  time.Now(),
	}
	sc.websocket.BroadcastToSession(sc.sessionID, controlMsg)

	sc.logger.WithField("sessionID", sc.sessionID).Info("Paused conversation")
}

// GetPipelineStatus returns the current pipeline status as JSON
func (sc *ServiceCoordinator) GetPipelineStatus() ([]byte, error) {
	return sc.flags.ToJSON()
}

// ProcessFinalTranscript is the definitive trigger for the LLM and TTS pipeline.
// It is called by the WebSocket handler upon receiving a 'trigger_llm' event.
func (sc *ServiceCoordinator) ProcessFinalTranscript(transcript string) error {
	sc.logger.WithField("sessionID", sc.sessionID).WithField("transcript", transcript).Info("Processing final transcript to trigger AI pipeline")

	// Update pipeline state to processing
	sc.stateManager.UpdateSessionState(sc.sessionID, PipelineStateProcessing)
	sc.broadcastStateUpdate()

	// Store the final transcript in metadata
	sc.flags.UpdateMetadata("transcript", transcript)

	// Step 1: LLM Processing (using the final transcript)
	if err := sc.processLLM(transcript); err != nil {
		sc.handlePipelineError("llm", err)
		return err
	}

	// Step 2: TTS Processing
	sessionFlags := sc.stateManager.GetSession(sc.sessionID)
	if sessionFlags == nil {
		sc.logger.WithField("sessionID", sc.sessionID).Error("Session flags not found, cannot process TTS")
		sc.handlePipelineError("tts", fmt.Errorf("Session flags not found"))
		return fmt.Errorf("Session flags not found")
	}

	responseInterface := sessionFlags.GetMetadata("llm_response")
	if responseInterface == nil {
		sc.logger.WithField("sessionID", sc.sessionID).Error("LLM response is nil, cannot process TTS")
		sc.handlePipelineError("tts", fmt.Errorf("LLM response is nil"))
		return fmt.Errorf("LLM response is nil")
	}

	response, ok := responseInterface.(string)
	if !ok {
		sc.logger.WithField("sessionID", sc.sessionID).Error("LLM response is not a string")
		sc.handlePipelineError("tts", fmt.Errorf("LLM response is not a string"))
		return fmt.Errorf("LLM response is not a string")
	}

	// Ensure the response is cleaned before sending to TTS
	cleanResponse := sc.cleanLLMResponseForTTS(response)

	if err := sc.processTTS(cleanResponse); err != nil {
		sc.handlePipelineError("tts", err)
		return err
	}

	// Pipeline complete
	sc.stateManager.UpdateSessionState(sc.sessionID, PipelineStateComplete)
	sc.broadcastStateUpdate()

	sc.logger.WithField("sessionID", sc.sessionID).Info("AI pipeline completed successfully")
	return nil
}
