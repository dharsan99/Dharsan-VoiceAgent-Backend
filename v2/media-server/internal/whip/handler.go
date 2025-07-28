package whip

import (
	"crypto/rand"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"

	"voice-agent-media-server/internal/audio"
	"voice-agent-media-server/internal/kafka"
	webrtcpkg "voice-agent-media-server/internal/webrtc"
	"voice-agent-media-server/pkg/logger"

	"github.com/pion/webrtc/v3"
	"github.com/pion/webrtc/v3/pkg/media"
)

// Handler handles WHIP protocol requests
type Handler struct {
	webrtcConfig *webrtcpkg.Config
	logger       *logger.Logger
	kafkaService *kafka.Service
	connections  sync.Map
}

// ConnectionInfo holds information about a WebRTC connection
type ConnectionInfo struct {
	PeerConnection *webrtc.PeerConnection
	SessionID      string
	CreatedAt      time.Time
	AudioProcessor *audio.Processor
	IsListening    bool         // Control whether audio should be processed
	mu             sync.RWMutex // Protect IsListening state
}

// NewHandler creates a new WHIP handler
func NewHandler(webrtcConfig *webrtcpkg.Config, logger *logger.Logger, kafkaService *kafka.Service) *Handler {
	return &Handler{
		webrtcConfig: webrtcConfig,
		logger:       logger,
		kafkaService: kafkaService,
	}
}

// HandleWHIP handles WHIP protocol requests
func (h *Handler) HandleWHIP(w http.ResponseWriter, r *http.Request) {
	// Handle OPTIONS requests for CORS preflight
	if r.Method == "OPTIONS" {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-Session-ID")
		w.WriteHeader(http.StatusOK)
		return
	}

	h.logger.Info("Received WHIP request")

	// Read SDP offer from request body
	offerSDP, err := io.ReadAll(r.Body)
	if err != nil {
		h.logger.WithField("error", err).Error("Failed to read SDP offer")
		http.Error(w, "Failed to read SDP offer", http.StatusBadRequest)
		return
	}

	// Create new peer connection
	peerConnection, err := h.webrtcConfig.CreatePeerConnection()
	if err != nil {
		h.logger.WithField("error", err).Error("Failed to create peer connection")
		http.Error(w, "Failed to create peer connection", http.StatusInternalServerError)
		return
	}

	// Get session ID from header or generate one
	sessionID := r.Header.Get("X-Session-ID")
	if sessionID == "" {
		sessionID = generateSessionID()
		h.logger.WithField("sessionID", sessionID).Info("Generated new session ID")
	} else {
		h.logger.WithField("sessionID", sessionID).Info("Using session ID from header")
	}

	// Create audio processor for echo functionality
	audioProcessor := audio.NewProcessor(h.logger)

	// Create local audio track for AI response (must be done before SDP exchange)
	localTrack, err := webrtc.NewTrackLocalStaticSample(
		webrtc.RTPCodecCapability{
			MimeType:    webrtc.MimeTypeOpus,
			ClockRate:   48000,
			Channels:    2,
			SDPFmtpLine: "minptime=10;useinbandfec=1",
		},
		"audio",
		"ai-response",
	)
	if err != nil {
		h.logger.WithField("error", err).Error("Failed to create local track")
		http.Error(w, "Failed to create local track", http.StatusInternalServerError)
		return
	}

	// Add the local track to the peer connection BEFORE SDP exchange
	if _, err := peerConnection.AddTrack(localTrack); err != nil {
		h.logger.WithField("error", err).Error("Failed to add local track")
		http.Error(w, "Failed to add local track", http.StatusInternalServerError)
		return
	}

	// Set up audio processing handler
	peerConnection.OnTrack(func(remoteTrack *webrtc.TrackRemote, receiver *webrtc.RTPReceiver) {
		h.logger.WithFields(map[string]interface{}{
			"sessionID": sessionID,
			"kind":      remoteTrack.Kind().String(),
		}).Info("Received remote track")

		// Only handle audio tracks
		if remoteTrack.Kind() != webrtc.RTPCodecTypeAudio {
			return
		}

		// Start AI audio processing (Phase 2)
		if h.kafkaService != nil {
			go h.processAIAudio(remoteTrack, localTrack, sessionID)
		} else {
			// Fallback to echo processing (Phase 1)
			go h.processEcho(remoteTrack, localTrack, audioProcessor, sessionID)
		}
	})

	// Set up connection state change handler
	peerConnection.OnConnectionStateChange(func(s webrtc.PeerConnectionState) {
		h.logger.WithFields(map[string]interface{}{
			"sessionID": sessionID,
			"state":     s.String(),
			"timestamp": time.Now().Format("15:04:05"),
		}).Info("Connection state changed")

		// Log specific state transitions for debugging
		switch s {
		case webrtc.PeerConnectionStateNew:
			h.logger.WithField("sessionID", sessionID).Info("Connection created")
		case webrtc.PeerConnectionStateConnecting:
			h.logger.WithField("sessionID", sessionID).Info("Connection establishing - ICE negotiation in progress")
		case webrtc.PeerConnectionStateConnected:
			h.logger.WithField("sessionID", sessionID).Info("Connection established successfully - audio should flow")
		case webrtc.PeerConnectionStateDisconnected:
			h.logger.WithField("sessionID", sessionID).Warn("Connection disconnected - ICE connectivity lost")
		case webrtc.PeerConnectionStateFailed:
			h.logger.WithFields(map[string]interface{}{
				"sessionID": sessionID,
				"reason":    "ICE negotiation failed - likely NAT/firewall blocking direct connection",
			}).Error("Connection failed - ICE negotiation failed")
		case webrtc.PeerConnectionStateClosed:
			h.logger.WithField("sessionID", sessionID).Info("Connection closed")
		}

		if s == webrtc.PeerConnectionStateFailed || s == webrtc.PeerConnectionStateDisconnected {
			h.cleanupConnection(sessionID)
		}
	})

	// Set up ICE candidate handler for logging
	peerConnection.OnICECandidate(func(candidate *webrtc.ICECandidate) {
		if candidate == nil {
			h.logger.WithField("sessionID", sessionID).Info("ICE gathering completed")
			return
		}

		// Log ICE candidate details
		h.logger.WithFields(map[string]interface{}{
			"sessionID": sessionID,
			"candidate": candidate.String(),
		}).Info("ICE candidate generated")
	})

	// Set the remote description
	offer := webrtc.SessionDescription{
		Type: webrtc.SDPTypeOffer,
		SDP:  string(offerSDP),
	}

	if err := peerConnection.SetRemoteDescription(offer); err != nil {
		h.logger.WithField("error", err).Error("Failed to set remote description")
		http.Error(w, "Failed to set remote description", http.StatusInternalServerError)
		return
	}

	// Create answer
	answer, err := peerConnection.CreateAnswer(nil)
	if err != nil {
		h.logger.WithField("error", err).Error("Failed to create answer")
		http.Error(w, "Failed to create answer", http.StatusInternalServerError)
		return
	}

	// Set local description
	err = peerConnection.SetLocalDescription(answer)
	if err != nil {
		h.logger.WithField("error", err).Error("Failed to set local description")
		http.Error(w, "Failed to set local description", http.StatusInternalServerError)
		return
	}

	// Wait for ICE gathering to complete
	h.logger.WithField("sessionID", sessionID).Info("Waiting for ICE gathering to complete...")

	// Create a channel to wait for ICE gathering completion
	gatherComplete := make(chan struct{})

	// Set up ICE gathering state change handler
	peerConnection.OnICEGatheringStateChange(func(state webrtc.ICEGathererState) {
		h.logger.WithFields(map[string]interface{}{
			"sessionID": sessionID,
			"state":     state.String(),
		}).Info("ICE gathering state changed")

		if state == webrtc.ICEGathererStateComplete {
			close(gatherComplete)
		}
	})

	// Wait for ICE gathering to complete with timeout
	select {
	case <-gatherComplete:
		h.logger.WithField("sessionID", sessionID).Info("ICE gathering completed")
	case <-time.After(30 * time.Second): // Reduced timeout for faster failure detection
		h.logger.WithField("sessionID", sessionID).Warn("ICE gathering timeout after 30 seconds, proceeding anyway")
	}

	// Get the final SDP with ICE candidates
	finalAnswer := peerConnection.LocalDescription()
	if finalAnswer == nil {
		h.logger.WithField("sessionID", sessionID).Error("No local description available")
		http.Error(w, "No local description available", http.StatusInternalServerError)
		return
	}

	// Store connection info
	connectionInfo := &ConnectionInfo{
		PeerConnection: peerConnection,
		SessionID:      sessionID,
		CreatedAt:      time.Now(),
		AudioProcessor: audioProcessor,
		IsListening:    false,          // Initialize to false
		mu:             sync.RWMutex{}, // Initialize mutex
	}
	h.connections.Store(sessionID, connectionInfo)

	// Return SDP answer with ICE candidates and session ID
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-Session-ID")
	w.Header().Set("Content-Type", "application/sdp")
	w.Header().Set("Location", fmt.Sprintf("/whip/%s", sessionID))
	w.Header().Set("X-Session-ID", sessionID) // Return the session ID to the client
	w.WriteHeader(http.StatusCreated)
	w.Write([]byte(finalAnswer.SDP))

	h.logger.WithField("sessionID", sessionID).Info("WHIP connection established with ICE candidates")
}

// processAIAudio processes audio through the AI pipeline (Phase 2) with filtering
func (h *Handler) processAIAudio(
	remoteTrack *webrtc.TrackRemote,
	localTrack *webrtc.TrackLocalStaticSample,
	sessionID string,
) {
	h.logger.WithField("sessionID", sessionID).Info("Starting AI audio processing with VAD and filtering")

	// Create audio processor with enhanced filtering
	audioProcessor := audio.NewProcessor(h.logger)
	audioProcessor.StartProcessing()

	// Start consuming AI-generated audio
	go h.kafkaService.StartAudioConsumer(sessionID, localTrack)

	// Read RTP packets from remote track and publish to Kafka
	packetCount := 0
	activePacketCount := 0
	silentPacketCount := 0
	h.logger.WithField("sessionID", sessionID).Info("Starting RTP packet reading loop with filtering")

	for {
		h.logger.WithField("sessionID", sessionID).Debug("Attempting to read RTP packet")
		rtpPacket, _, err := remoteTrack.ReadRTP()
		if err != nil {
			if err == io.EOF {
				h.logger.WithField("sessionID", sessionID).Info("Remote track closed (EOF)")
			} else {
				h.logger.WithFields(map[string]interface{}{
					"sessionID": sessionID,
					"error":     err,
					"errorType": fmt.Sprintf("%T", err),
				}).Error("Failed to read RTP packet")
			}
			break
		}

		packetCount++

		// Check if we should process audio (only when listening is enabled)
		connInfo, exists := h.connections.Load(sessionID)
		if !exists {
			h.logger.WithField("sessionID", sessionID).Warn("Connection info not found, skipping audio processing")
			continue
		}

		connectionInfo := connInfo.(*ConnectionInfo)
		connectionInfo.mu.RLock()
		isListening := connectionInfo.IsListening
		connectionInfo.mu.RUnlock()

		if !isListening {
			// Skip audio processing when not listening
			continue
		}

		// Process audio with VAD and filtering
		processedPacket, shouldPublish := audioProcessor.ProcessAudioForPipeline(rtpPacket)

		if shouldPublish && processedPacket != nil {
			activePacketCount++

			// Publish filtered audio to Kafka for AI processing
			if err := h.kafkaService.PublishAudio(sessionID, processedPacket); err != nil {
				h.logger.WithFields(map[string]interface{}{
					"sessionID": sessionID,
					"error":     err,
				}).Error("Failed to publish audio to Kafka")
			} else {
				// Log successful audio publishing
				h.logger.WithFields(map[string]interface{}{
					"sessionID":  sessionID,
					"packetSize": len(processedPacket.Payload),
					"energy":     audioProcessor.GetStats()["averageEnergy"],
				}).Info("Audio published to Kafka successfully")
			}
		} else {
			silentPacketCount++
			// Log when audio is filtered out
			if packetCount%50 == 0 { // Log every 50th filtered packet to avoid spam
				h.logger.WithFields(map[string]interface{}{
					"sessionID": sessionID,
					"energy":    audioProcessor.GetStats()["averageEnergy"],
					"threshold": audioProcessor.GetStats()["currentThreshold"],
				}).Info("Audio filtered out by VAD")
			}
		}

		// Log processing statistics periodically
		if packetCount%100 == 0 {
			stats := audioProcessor.GetStats()
			h.logger.WithFields(map[string]interface{}{
				"sessionID":        sessionID,
				"packetCount":      packetCount,
				"activePackets":    activePacketCount,
				"silentPackets":    silentPacketCount,
				"activeRatio":      stats["activeRatio"],
				"averageEnergy":    stats["averageEnergy"],
				"currentThreshold": stats["currentThreshold"],
				"backgroundLevel":  stats["backgroundLevel"],
			}).Info("Audio processing statistics")
		}
	}

	// Stop audio processing and log final statistics
	audioProcessor.StopProcessing()
	finalStats := audioProcessor.GetStats()

	h.logger.WithFields(map[string]interface{}{
		"sessionID":        sessionID,
		"totalPackets":     packetCount,
		"activePackets":    activePacketCount,
		"silentPackets":    silentPacketCount,
		"activeRatio":      finalStats["activeRatio"],
		"averageEnergy":    finalStats["averageEnergy"],
		"peakEnergy":       finalStats["peakEnergy"],
		"processingTime":   finalStats["duration"],
		"packetsPerSecond": finalStats["packetsPerSecond"],
	}).Info("AI audio processing stopped with filtering")
}

// processEcho processes audio echo (Phase 1 fallback)
func (h *Handler) processEcho(
	remoteTrack *webrtc.TrackRemote,
	localTrack *webrtc.TrackLocalStaticSample,
	audioProcessor *audio.Processor,
	sessionID string,
) {
	h.logger.WithField("sessionID", sessionID).Info("Starting echo processing")

	// Read RTP packets from remote track and echo them back
	for {
		rtpPacket, _, err := remoteTrack.ReadRTP()
		if err != nil {
			if err == io.EOF {
				h.logger.WithField("sessionID", sessionID).Info("Remote track closed")
			} else {
				h.logger.WithFields(map[string]interface{}{
					"sessionID": sessionID,
					"error":     err,
				}).Error("Failed to read RTP packet")
			}
			break
		}

		// Process audio through echo processor
		processedPacket := audioProcessor.ProcessEcho(rtpPacket)

		// Write processed packet to local track
		if err := localTrack.WriteSample(media.Sample{
			Data:     processedPacket.Payload,
			Duration: 20 * time.Millisecond, // Standard Opus frame duration
		}); err != nil {
			h.logger.WithFields(map[string]interface{}{
				"sessionID": sessionID,
				"error":     err,
			}).Error("Failed to write RTP packet")
			break
		}
	}

	h.logger.WithField("sessionID", sessionID).Info("Echo processing stopped")
}

// cleanupConnection cleans up a WebRTC connection
func (h *Handler) cleanupConnection(sessionID string) {
	if connInfo, ok := h.connections.LoadAndDelete(sessionID); ok {
		connectionInfo := connInfo.(*ConnectionInfo)

		// Close peer connection
		if err := connectionInfo.PeerConnection.Close(); err != nil {
			h.logger.WithFields(map[string]interface{}{
				"sessionID": sessionID,
				"error":     err,
			}).Error("Failed to close peer connection")
		}

		h.logger.WithField("sessionID", sessionID).Info("Connection cleaned up")
	}
}

// GetConnectionCount returns the number of active connections
func (h *Handler) GetConnectionCount() int {
	count := 0
	h.connections.Range(func(key, value interface{}) bool {
		count++
		return true
	})
	return count
}

// SetListeningState controls whether audio processing is enabled for a session
func (h *Handler) SetListeningState(sessionID string, isListening bool) error {
	connInfo, exists := h.connections.Load(sessionID)
	if !exists {
		return fmt.Errorf("connection not found for session: %s", sessionID)
	}

	connectionInfo := connInfo.(*ConnectionInfo)
	connectionInfo.mu.Lock()
	connectionInfo.IsListening = isListening
	connectionInfo.mu.Unlock()

	h.logger.WithFields(map[string]interface{}{
		"sessionID":   sessionID,
		"isListening": isListening,
	}).Info("Listening state updated")

	return nil
}

// GetListeningState returns the current listening state for a session
func (h *Handler) GetListeningState(sessionID string) (bool, error) {
	connInfo, exists := h.connections.Load(sessionID)
	if !exists {
		return false, fmt.Errorf("connection not found for session: %s", sessionID)
	}

	connectionInfo := connInfo.(*ConnectionInfo)
	connectionInfo.mu.RLock()
	isListening := connectionInfo.IsListening
	connectionInfo.mu.RUnlock()

	return isListening, nil
}

// generateSessionID generates a unique session ID
func generateSessionID() string {
	timestamp := time.Now().UnixNano()
	// Generate a more unique random string using crypto/rand
	randomBytes := make([]byte, 4)
	if _, err := rand.Read(randomBytes); err != nil {
		// Fallback to time-based random if crypto/rand fails
		randomBytes = []byte(fmt.Sprintf("%x", time.Now().UnixNano()%1000000000))
	}
	randomPart := fmt.Sprintf("%x", randomBytes)
	return fmt.Sprintf("session_%d_%s", timestamp, randomPart)
}
