package audio

import (
	"math"
	"sync"
	"time"

	"voice-agent-media-server/pkg/logger"

	"github.com/pion/rtp"
)

// AudioQualityMetrics tracks audio quality statistics
type AudioQualityMetrics struct {
	TotalPackets     int64
	SilentPackets    int64
	ActivePackets    int64
	AverageEnergy    float64
	PeakEnergy       float64
	BackgroundLevel  float64
	LastActivityTime time.Time
	ProcessingTime   time.Duration
}

// AdaptiveVAD implements adaptive voice activity detection
type AdaptiveVAD struct {
	baseThreshold    float64
	currentThreshold float64
	backgroundLevel  float64
	adaptationRate   float64
	minThreshold     float64
	maxThreshold     float64
}

// Processor handles audio processing for echo functionality
type Processor struct {
	logger *logger.Logger
	mu     sync.Mutex

	// Echo processing state
	isProcessing bool
	packetCount  int64

	// Performance metrics
	startTime    time.Time
	totalLatency time.Duration

	// Audio quality and VAD
	qualityMetrics AudioQualityMetrics
	vad            *AdaptiveVAD

	// Configuration
	config AudioConfig
}

// AudioConfig holds audio processing configuration
type AudioConfig struct {
	EnableVAD          bool
	EnableFiltering    bool
	BaseThreshold      float64
	AdaptationRate     float64
	MinThreshold       float64
	MaxThreshold       float64
	SilenceTimeout     time.Duration
	QualityLogInterval int64
}

// DefaultAudioConfig returns default audio configuration
func DefaultAudioConfig() AudioConfig {
	return AudioConfig{
		EnableVAD:          false, // TEMPORARILY DISABLED for testing
		EnableFiltering:    false, // TEMPORARILY DISABLED for testing
		BaseThreshold:      0.1,   // Increased from 0.02 to 0.1 (10%) for clearer speech detection
		AdaptationRate:     0.01,
		MinThreshold:       0.05, // Increased from 0.01 to 0.05 (5%) for minimum speech threshold
		MaxThreshold:       0.15, // Higher maximum threshold to allow more audio through
		SilenceTimeout:     2 * time.Second,
		QualityLogInterval: 100,
	}
}

// NewProcessor creates a new audio processor
func NewProcessor(logger *logger.Logger) *Processor {
	config := DefaultAudioConfig()
	return &Processor{
		logger:    logger,
		startTime: time.Now(),
		config:    config,
		vad: &AdaptiveVAD{
			baseThreshold:    config.BaseThreshold,
			currentThreshold: config.BaseThreshold,
			backgroundLevel:  0.0,
			adaptationRate:   config.AdaptationRate,
			minThreshold:     config.MinThreshold,
			maxThreshold:     config.MaxThreshold,
		},
	}
}

// NewProcessorWithConfig creates a new audio processor with custom configuration
func NewProcessorWithConfig(logger *logger.Logger, config AudioConfig) *Processor {
	return &Processor{
		logger:    logger,
		startTime: time.Now(),
		config:    config,
		vad: &AdaptiveVAD{
			baseThreshold:    config.BaseThreshold,
			currentThreshold: config.BaseThreshold,
			backgroundLevel:  0.0,
			adaptationRate:   config.AdaptationRate,
			minThreshold:     config.MinThreshold,
			maxThreshold:     config.MaxThreshold,
		},
	}
}

// calculateAudioEnergy calculates the RMS energy of audio data
func (p *Processor) calculateAudioEnergy(audioData []byte) float64 {
	if len(audioData) == 0 {
		return 0.0
	}

	// Convert bytes to float samples (-1 to 1 range)
	samples := make([]float64, len(audioData))
	for i, b := range audioData {
		samples[i] = (float64(b) - 128.0) / 128.0
	}

	// Calculate RMS (Root Mean Square)
	sum := 0.0
	for _, sample := range samples {
		sum += sample * sample
	}

	rms := math.Sqrt(sum / float64(len(samples)))
	return rms
}

// updateVADThreshold updates the adaptive VAD threshold
func (p *Processor) updateVADThreshold(energy float64) {
	p.vad.backgroundLevel = p.vad.backgroundLevel*(1-p.vad.adaptationRate) + energy*p.vad.adaptationRate

	// Adjust threshold based on background level
	newThreshold := math.Max(p.vad.minThreshold, p.vad.backgroundLevel*1.5)
	newThreshold = math.Min(p.vad.maxThreshold, newThreshold)

	p.vad.currentThreshold = newThreshold
}

// isVoiceActive determines if the audio contains voice activity
func (p *Processor) isVoiceActive(energy float64) bool {
	if !p.config.EnableVAD {
		return true // If VAD is disabled, consider all audio as active
	}

	p.updateVADThreshold(energy)
	return energy > p.vad.currentThreshold
}

// shouldPublishAudio determines if audio should be published based on quality and VAD
func (p *Processor) shouldPublishAudio(energy float64) bool {
	if !p.config.EnableFiltering {
		return true // If filtering is disabled, publish all audio
	}

	return p.isVoiceActive(energy)
}

// ProcessEcho processes an RTP packet for echo functionality
func (p *Processor) ProcessEcho(packet *rtp.Packet) *rtp.Packet {
	p.mu.Lock()
	defer p.mu.Unlock()

	startTime := time.Now()

	// Increment packet counter
	p.packetCount++
	p.qualityMetrics.TotalPackets++

	// Calculate audio energy
	energy := p.calculateAudioEnergy(packet.Payload)

	// Update quality metrics
	p.qualityMetrics.AverageEnergy = (p.qualityMetrics.AverageEnergy*float64(p.qualityMetrics.TotalPackets-1) + energy) / float64(p.qualityMetrics.TotalPackets)
	if energy > p.qualityMetrics.PeakEnergy {
		p.qualityMetrics.PeakEnergy = energy
	}

	// Determine if this is voice activity
	isActive := p.isVoiceActive(energy)
	if isActive {
		p.qualityMetrics.ActivePackets++
		p.qualityMetrics.LastActivityTime = time.Now()
	} else {
		p.qualityMetrics.SilentPackets++
	}

	// Log quality metrics periodically
	if p.packetCount%p.config.QualityLogInterval == 0 {
		p.logQualityMetrics()
	}

	// Create a new packet for echo (avoid modifying original)
	echoPacket := &rtp.Packet{
		Header: rtp.Header{
			Version:        packet.Header.Version,
			Padding:        packet.Header.Padding,
			Extension:      packet.Header.Extension,
			Marker:         packet.Header.Marker,
			PayloadType:    packet.Header.PayloadType,
			SequenceNumber: packet.Header.SequenceNumber,
			Timestamp:      packet.Header.Timestamp,
			SSRC:           packet.Header.SSRC,
			CSRC:           packet.Header.CSRC,
		},
		Payload: make([]byte, len(packet.Payload)),
	}

	// Copy payload data
	copy(echoPacket.Payload, packet.Payload)

	// Copy extension data if present
	if packet.Header.Extension {
		echoPacket.Header.Extension = true
		// Note: Extension payload handling would need to be implemented based on specific requirements
	}

	p.qualityMetrics.ProcessingTime = time.Since(startTime)
	p.totalLatency += p.qualityMetrics.ProcessingTime

	return echoPacket
}

// ProcessAudioForPipeline processes audio for AI pipeline with filtering
func (p *Processor) ProcessAudioForPipeline(packet *rtp.Packet) (*rtp.Packet, bool) {
	p.mu.Lock()
	defer p.mu.Unlock()

	startTime := time.Now()

	// Increment packet counter
	p.packetCount++
	p.qualityMetrics.TotalPackets++

	// Calculate audio energy
	energy := p.calculateAudioEnergy(packet.Payload)

	// Update quality metrics
	p.qualityMetrics.AverageEnergy = (p.qualityMetrics.AverageEnergy*float64(p.qualityMetrics.TotalPackets-1) + energy) / float64(p.qualityMetrics.TotalPackets)
	if energy > p.qualityMetrics.PeakEnergy {
		p.qualityMetrics.PeakEnergy = energy
	}

	// Determine if this packet should be published
	shouldPublish := p.shouldPublishAudio(energy)

	// Update activity metrics
	if shouldPublish {
		p.qualityMetrics.ActivePackets++
		p.qualityMetrics.LastActivityTime = time.Now()
	} else {
		p.qualityMetrics.SilentPackets++
	}

	// Log quality metrics periodically
	if p.packetCount%p.config.QualityLogInterval == 0 {
		p.logQualityMetrics()
	}

	if !shouldPublish {
		p.qualityMetrics.ProcessingTime = time.Since(startTime)
		return nil, false // Don't publish silent audio
	}

	// Create a new packet for publishing
	processedPacket := &rtp.Packet{
		Header: rtp.Header{
			Version:        packet.Header.Version,
			Padding:        packet.Header.Padding,
			Extension:      packet.Header.Extension,
			Marker:         packet.Header.Marker,
			PayloadType:    packet.Header.PayloadType,
			SequenceNumber: packet.Header.SequenceNumber,
			Timestamp:      packet.Header.Timestamp,
			SSRC:           packet.Header.SSRC,
			CSRC:           packet.Header.CSRC,
		},
		Payload: make([]byte, len(packet.Payload)),
	}

	// Copy payload data
	copy(processedPacket.Payload, packet.Payload)

	// Copy extension data if present
	if packet.Header.Extension {
		processedPacket.Header.Extension = true
	}

	p.qualityMetrics.ProcessingTime = time.Since(startTime)
	p.totalLatency += p.qualityMetrics.ProcessingTime

	return processedPacket, true
}

// logQualityMetrics logs processing metrics
func (p *Processor) logQualityMetrics() {
	duration := time.Since(p.startTime)
	packetsPerSecond := float64(p.packetCount) / duration.Seconds()

	// Calculate quality ratios
	activeRatio := float64(0)
	if p.qualityMetrics.TotalPackets > 0 {
		activeRatio = float64(p.qualityMetrics.ActivePackets) / float64(p.qualityMetrics.TotalPackets) * 100
	}

	silentRatio := float64(0)
	if p.qualityMetrics.TotalPackets > 0 {
		silentRatio = float64(p.qualityMetrics.SilentPackets) / float64(p.qualityMetrics.TotalPackets) * 100
	}

	p.logger.WithFields(map[string]interface{}{
		"packetsProcessed":      p.packetCount,
		"duration":              duration.String(),
		"packetsPerSecond":      packetsPerSecond,
		"activePackets":         p.qualityMetrics.ActivePackets,
		"silentPackets":         p.qualityMetrics.SilentPackets,
		"activeRatio":           activeRatio,
		"silentRatio":           silentRatio,
		"averageEnergy":         p.qualityMetrics.AverageEnergy,
		"peakEnergy":            p.qualityMetrics.PeakEnergy,
		"currentThreshold":      p.vad.currentThreshold,
		"backgroundLevel":       p.vad.backgroundLevel,
		"lastActivityTime":      p.qualityMetrics.LastActivityTime,
		"averageProcessingTime": p.totalLatency.Microseconds() / p.packetCount,
	}).Debug("Audio processing metrics")
}

// GetStats returns processing statistics
func (p *Processor) GetStats() map[string]interface{} {
	p.mu.Lock()
	defer p.mu.Unlock()

	duration := time.Since(p.startTime)
	packetsPerSecond := float64(0)
	if duration > 0 {
		packetsPerSecond = float64(p.packetCount) / duration.Seconds()
	}

	activeRatio := float64(0)
	if p.qualityMetrics.TotalPackets > 0 {
		activeRatio = float64(p.qualityMetrics.ActivePackets) / float64(p.qualityMetrics.TotalPackets) * 100
	}

	return map[string]interface{}{
		"packetsProcessed":      p.packetCount,
		"duration":              duration.String(),
		"packetsPerSecond":      packetsPerSecond,
		"isProcessing":          p.isProcessing,
		"activePackets":         p.qualityMetrics.ActivePackets,
		"silentPackets":         p.qualityMetrics.SilentPackets,
		"activeRatio":           activeRatio,
		"averageEnergy":         p.qualityMetrics.AverageEnergy,
		"peakEnergy":            p.qualityMetrics.PeakEnergy,
		"currentThreshold":      p.vad.currentThreshold,
		"backgroundLevel":       p.vad.backgroundLevel,
		"lastActivityTime":      p.qualityMetrics.LastActivityTime,
		"averageProcessingTime": p.totalLatency.Microseconds() / p.packetCount,
		"vadEnabled":            p.config.EnableVAD,
		"filteringEnabled":      p.config.EnableFiltering,
	}
}

// GetQualityMetrics returns detailed quality metrics
func (p *Processor) GetQualityMetrics() AudioQualityMetrics {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.qualityMetrics
}

// GetVADStats returns VAD statistics
func (p *Processor) GetVADStats() map[string]interface{} {
	p.mu.Lock()
	defer p.mu.Unlock()

	return map[string]interface{}{
		"baseThreshold":    p.vad.baseThreshold,
		"currentThreshold": p.vad.currentThreshold,
		"backgroundLevel":  p.vad.backgroundLevel,
		"adaptationRate":   p.vad.adaptationRate,
		"minThreshold":     p.vad.minThreshold,
		"maxThreshold":     p.vad.maxThreshold,
	}
}

// StartProcessing starts the processing
func (p *Processor) StartProcessing() {
	p.mu.Lock()
	defer p.mu.Unlock()

	p.isProcessing = true
	p.startTime = time.Now()
	p.packetCount = 0
	p.qualityMetrics = AudioQualityMetrics{
		LastActivityTime: time.Now(),
	}

	p.logger.Info("Audio processing started with VAD and filtering")
}

// StopProcessing stops the processing
func (p *Processor) StopProcessing() {
	p.mu.Lock()
	defer p.mu.Unlock()

	p.isProcessing = false

	p.logger.WithFields(map[string]interface{}{
		"totalPackets": p.packetCount,
		"duration":     time.Since(p.startTime).String(),
		"activeRatio":  float64(p.qualityMetrics.ActivePackets) / float64(p.qualityMetrics.TotalPackets) * 100,
	}).Info("Audio processing stopped")
}
