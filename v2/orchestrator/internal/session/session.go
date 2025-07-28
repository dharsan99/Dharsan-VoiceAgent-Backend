package session

import (
	"bytes"
	"math"
	"sync"
	"time"

	"voice-agent-orchestrator/internal/logger"
)

// AudioSession manages audio data for a single session
type AudioSession struct {
	SessionID    string
	logger       *logger.Logger
	audioBuffer  *bytes.Buffer
	lastActivity time.Time
	mu           sync.RWMutex

	// Enhanced buffer management
	maxBufferSize    int
	bufferTimeout    time.Duration
	qualityThreshold float64
	totalBytes       int64
	qualityMetrics   AudioQualityMetrics

	// Complete audio buffering mode
	completeMode     bool
	sessionStartTime time.Time
	isSessionActive  bool
}

// AudioQualityMetrics tracks audio quality for sessions
type AudioQualityMetrics struct {
	TotalBytes     int64
	AverageQuality float64
	LastQuality    float64
	BufferFlushes  int64
	TimeoutFlushes int64
	QualityFlushes int64
	LastFlushTime  time.Time
}

// NewAudioSession creates a new audio session
func NewAudioSession(sessionID string, logger *logger.Logger) *AudioSession {
	return &AudioSession{
		SessionID:        sessionID,
		logger:           logger,
		audioBuffer:      bytes.NewBuffer(nil),
		lastActivity:     time.Now(),
		maxBufferSize:    10 * 1024 * 1024, // 10MB max buffer for complete audio
		bufferTimeout:    30 * time.Second, // 30s timeout for complete audio
		qualityThreshold: 0.1,              // Minimum quality threshold
		totalBytes:       0,
		qualityMetrics: AudioQualityMetrics{
			LastFlushTime: time.Now(),
		},
		completeMode:     true, // Enable complete audio buffering
		sessionStartTime: time.Now(),
		isSessionActive:  true,
	}
}

// AddAudio adds audio data to the session buffer with quality management
func (s *AudioSession) AddAudio(audioData []byte) {
	s.mu.Lock()
	defer s.mu.Unlock()

	// Update session activity
	s.lastActivity = time.Now()
	s.isSessionActive = true

	// Calculate audio quality (simple energy-based)
	quality := s.calculateAudioQuality(audioData)
	s.qualityMetrics.LastQuality = quality
	s.qualityMetrics.TotalBytes += int64(len(audioData))

	// Update average quality
	if s.qualityMetrics.TotalBytes > 0 {
		s.qualityMetrics.AverageQuality = (s.qualityMetrics.AverageQuality*float64(s.qualityMetrics.TotalBytes-int64(len(audioData))) + quality*float64(len(audioData))) / float64(s.qualityMetrics.TotalBytes)
	}

	// Add audio to buffer
	s.audioBuffer.Write(audioData)
	s.totalBytes += int64(len(audioData))

	s.logger.WithFields(map[string]interface{}{
		"sessionID":    s.SessionID,
		"bufferSize":   s.audioBuffer.Len(),
		"totalBytes":   s.totalBytes,
		"quality":      quality,
		"avgQuality":   s.qualityMetrics.AverageQuality,
		"lastActivity": s.lastActivity,
		"completeMode": s.completeMode,
	}).Debug("Added audio to session buffer")
}

// GetAudioBuffer returns a copy of the current audio buffer
func (s *AudioSession) GetAudioBuffer() []byte {
	s.mu.RLock()
	defer s.mu.RUnlock()

	return s.audioBuffer.Bytes()
}

// HasEnoughAudio checks if there's enough audio data for processing
func (s *AudioSession) HasEnoughAudio() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.completeMode {
		// In complete mode, we need at least 0.125 seconds of audio (2KB at 16kHz mono)
		// and the session should be inactive (no recent activity)
		minSize := 2 * 1024 // 2KB minimum (reduced from 8KB for short phrases like "hi", "hello")
		sessionInactive := time.Since(s.lastActivity) > 3*time.Second
		return s.audioBuffer.Len() >= minSize && sessionInactive
	}

	// Legacy mode: Require at least 500 bytes for better transcription quality
	minSize := 500
	return s.audioBuffer.Len() >= minSize
}

// ClearBuffer clears the audio buffer
func (s *AudioSession) ClearBuffer() {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.audioBuffer.Reset()
	s.logger.WithField("sessionID", s.SessionID).Debug("Cleared audio buffer")
}

// IsStale checks if the session is stale (no activity for 30 seconds)
func (s *AudioSession) IsStale() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	return time.Since(s.lastActivity) > 30*time.Second
}

// calculateAudioQuality calculates a simple quality metric for audio data
func (s *AudioSession) calculateAudioQuality(audioData []byte) float64 {
	if len(audioData) == 0 {
		return 0.0
	}

	// Simple energy-based quality calculation
	sum := 0.0
	for _, b := range audioData {
		// Convert byte to float (-1 to 1 range)
		sample := (float64(b) - 128.0) / 128.0
		sum += sample * sample
	}

	// Return RMS energy
	return math.Sqrt(sum / float64(len(audioData)))
}

// flushBuffer flushes the audio buffer and logs the reason
func (s *AudioSession) flushBuffer(reason string) {
	oldSize := s.audioBuffer.Len()
	s.audioBuffer.Reset()
	s.qualityMetrics.LastFlushTime = time.Now()

	switch reason {
	case "timeout":
		s.qualityMetrics.TimeoutFlushes++
	case "size_limit":
		s.qualityMetrics.BufferFlushes++
	case "quality":
		s.qualityMetrics.QualityFlushes++
	}

	s.logger.WithFields(map[string]interface{}{
		"sessionID": s.SessionID,
		"reason":    reason,
		"oldSize":   oldSize,
		"flushes":   s.qualityMetrics.BufferFlushes + s.qualityMetrics.TimeoutFlushes + s.qualityMetrics.QualityFlushes,
	}).Info("Audio buffer flushed")
}

// GetQualityMetrics returns the session quality metrics
func (s *AudioSession) GetQualityMetrics() AudioQualityMetrics {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.qualityMetrics
}

// Cleanup cleans up the session resources
func (s *AudioSession) Cleanup() {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.audioBuffer.Reset()
	s.logger.WithFields(map[string]interface{}{
		"sessionID": s.SessionID,
		"metrics":   s.qualityMetrics,
	}).Debug("Session cleaned up")
}

// MarkSessionInactive marks the session as inactive (user stopped speaking)
func (s *AudioSession) MarkSessionInactive() {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.isSessionActive = false
	s.logger.WithField("sessionID", s.SessionID).Debug("Session marked as inactive")
}

// IsSessionActive checks if the session is currently active
func (s *AudioSession) IsSessionActive() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	return s.isSessionActive
}
