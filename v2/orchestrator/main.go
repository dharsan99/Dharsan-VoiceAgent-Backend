package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"voice-agent-orchestrator/internal/ai"
	"voice-agent-orchestrator/internal/audio"
	"voice-agent-orchestrator/internal/grpc"
	"voice-agent-orchestrator/internal/kafka"
	"voice-agent-orchestrator/internal/logger"
	"voice-agent-orchestrator/internal/pipeline"
	"voice-agent-orchestrator/internal/session"
	"voice-agent-orchestrator/pkg/config"

	"github.com/gorilla/websocket"
	"github.com/joho/godotenv"
)

// Define the structure for incoming and outgoing WebSocket messages
type WebSocketMessage struct {
	Event           string  `json:"event"`
	Text            string  `json:"text,omitempty"`
	FinalTranscript string  `json:"final_transcript,omitempty"`
	SessionID       string  `json:"session_id,omitempty"`
	Timestamp       string  `json:"timestamp,omitempty"`
	AudioData       string  `json:"audio_data,omitempty"`
	IsFinal         bool    `json:"is_final,omitempty"`
	Confidence      float64 `json:"confidence,omitempty"`
}

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true // Allow all origins for development
	},
}

// Orchestrator manages the AI processing pipeline
type Orchestrator struct {
	kafkaService *kafka.Service
	aiService    *ai.Service
	audioDecoder *audio.Decoder
	logger       *logger.Logger
	sessions     sync.Map
	ctx          context.Context
	cancel       context.CancelFunc
	wg           sync.WaitGroup
	// WebSocket connections
	wsConnections sync.Map
	// Session ID mapping: media server session -> frontend session
	sessionMapping sync.Map
	// Pipeline state management
	stateManager *pipeline.PipelineStateManager
	// Service coordinators for each session
	coordinators sync.Map
}

// NewOrchestrator creates a new orchestrator instance
func NewOrchestrator(kafkaService *kafka.Service, aiService *ai.Service, logger *logger.Logger) *Orchestrator {
	ctx, cancel := context.WithCancel(context.Background())
	return &Orchestrator{
		kafkaService: kafkaService,
		aiService:    aiService,
		audioDecoder: audio.NewDecoder(logger),
		logger:       logger,
		ctx:          ctx,
		cancel:       cancel,
		stateManager: pipeline.NewPipelineStateManager(logger),
	}
}

// Start starts the orchestrator
func (o *Orchestrator) Start() error {
	o.logger.Info("Starting orchestrator with pipeline state management...")

	// Start WebSocket server
	go o.startWebSocketServer()

	// Start audio consumption
	go o.consumeAudio()

	o.logger.Info("Orchestrator started successfully")
	return nil
}

// BroadcastToSession implements the WebSocketBroadcaster interface
func (o *Orchestrator) BroadcastToSession(sessionID string, message interface{}) {
	// Convert message to JSON
	jsonData, err := json.Marshal(message)
	if err != nil {
		o.logger.WithField("error", err).Error("Failed to marshal WebSocket message")
		return
	}

	// Broadcast to all connections for this session
	o.wsConnections.Range(func(key, value interface{}) bool {
		keyStr := key.(string)

		// Skip session storage keys
		if strings.HasSuffix(keyStr, "_session") {
			return true
		}

		// Check if this connection has a matching session ID
		if sessionKey, ok := o.wsConnections.Load(keyStr + "_session"); ok {
			storedSessionID := sessionKey.(string)
			if storedSessionID == sessionID {
				// This connection belongs to our session, send the message
				if conn, ok := value.(*websocket.Conn); ok {
					if err := conn.WriteMessage(websocket.TextMessage, jsonData); err != nil {
						o.logger.WithField("connID", keyStr).WithField("error", err).Error("Failed to send WebSocket message")
						// Clean up failed connection
						o.wsConnections.Delete(key)
						o.wsConnections.Delete(keyStr + "_session")
					} else {
						o.logger.WithFields(map[string]interface{}{
							"sessionID": sessionID,
							"connID":    keyStr,
						}).Debug("WebSocket message sent successfully")
					}
				}
			}
		}
		return true
	})
}

// startWebSocketServer starts the WebSocket server for transcript delivery
func (o *Orchestrator) startWebSocketServer() {
	// Add CORS middleware
	corsMiddleware := func(next http.HandlerFunc) http.HandlerFunc {
		return func(w http.ResponseWriter, r *http.Request) {
			// Get environment
			env := os.Getenv("ENVIRONMENT")

			// Get allowed origins
			var allowedOrigins []string
			if env == "production" {
				corsOrigins := os.Getenv("CORS_ALLOWED_ORIGINS")
				if corsOrigins != "" {
					allowedOrigins = strings.Split(corsOrigins, ",")
				} else {
					allowedOrigins = []string{
						"https://dharsan-voice-agent-frontend.vercel.app",
						"https://voice-agent-frontend.vercel.app",
						"https://voice-agent.com",
						"https://www.voice-agent.com",
					}
				}
			} else {
				allowedOrigins = []string{"*"}
			}

			// Check origin
			origin := r.Header.Get("Origin")
			allowedOrigin := "*"

			if env == "production" {
				for _, allowed := range allowedOrigins {
					if allowed == origin {
						allowedOrigin = origin
						break
					}
				}
			}

			w.Header().Set("Access-Control-Allow-Origin", allowedOrigin)
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, Accept, Origin, User-Agent, X-Session-ID")
			w.Header().Set("Access-Control-Allow-Credentials", "true")

			// Set security headers for production
			if env == "production" {
				w.Header().Set("X-Content-Type-Options", "nosniff")
				w.Header().Set("X-Frame-Options", "DENY")
				w.Header().Set("X-XSS-Protection", "1; mode=block")
				w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
			}

			if r.Method == "OPTIONS" {
				w.WriteHeader(http.StatusOK)
				return
			}

			next(w, r)
		}
	}

	// Health check endpoint
	http.HandleFunc("/health", corsMiddleware(o.handleHealth))

	// WebSocket endpoint
	http.HandleFunc("/ws", corsMiddleware(o.handleWebSocket))

	port := ":8001"
	o.logger.WithField("port", port).Info("Starting WebSocket server")

	if err := http.ListenAndServe(port, nil); err != nil {
		o.logger.WithField("error", err).Fatal("Failed to start WebSocket server")
	}
}

// handleWebSocket handles WebSocket connections
func (o *Orchestrator) handleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		o.logger.WithField("error", err).Error("Failed to upgrade WebSocket connection")
		return
	}
	defer conn.Close()

	// Generate a unique connection ID
	connID := fmt.Sprintf("ws_%d", time.Now().UnixNano())
	o.wsConnections.Store(connID, conn)
	defer o.wsConnections.Delete(connID)

	o.logger.WithField("connID", connID).Info("WebSocket client connected")

	// Keep connection alive with ping/pong
	conn.SetPongHandler(func(string) error {
		conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

	// Set up ping ticker
	pingTicker := time.NewTicker(30 * time.Second)
	defer pingTicker.Stop()

	// Set initial read deadline
	conn.SetReadDeadline(time.Now().Add(60 * time.Second))

	// Keep connection alive
	for {
		select {
		case <-o.ctx.Done():
			return
		case <-pingTicker.C:
			// Send ping to keep connection alive
			if err := conn.WriteControl(websocket.PingMessage, []byte{}, time.Now().Add(10*time.Second)); err != nil {
				o.logger.WithField("connID", connID).Info("Failed to send ping, client disconnected")
				return
			}
		default:
			// Read messages with timeout
			_, message, err := conn.ReadMessage()
			if err != nil {
				if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
					o.logger.WithField("connID", connID).WithField("error", err).Error("WebSocket read error")
				} else {
					o.logger.WithField("connID", connID).Info("WebSocket client disconnected")
				}
				return
			}

			// Parse and handle the message
			var msg WebSocketMessage
			if err := json.Unmarshal(message, &msg); err != nil {
				o.logger.WithField("connID", connID).WithField("error", err).Error("Failed to parse WebSocket message")
				continue
			}

			// Handle different event types based on the new event-driven architecture
			switch msg.Event {
			case "greeting_request":
				// Send the automatic greeting response
				greetingMsg := WebSocketMessage{
					Event:     "greeting",
					Text:      "how may i help you today",
					Timestamp: time.Now().Format(time.RFC3339),
				}
				if err := conn.WriteJSON(greetingMsg); err != nil {
					o.logger.WithField("connID", connID).WithField("error", err).Error("Failed to send greeting")
				} else {
					o.logger.WithField("connID", connID).Info("Sent greeting message")
				}

			case "start_listening":
				sessionID := msg.SessionID
				if sessionID == "" {
					// Generate session ID if not provided
					sessionID = fmt.Sprintf("session_%d", time.Now().UnixNano())
				}

				o.logger.WithField("connID", connID).WithField("sessionID", sessionID).Info("Start listening event received")

				// Store the session ID for this connection
				o.wsConnections.Store(connID+"_session", sessionID)
				o.sessionMapping.Store(sessionID, sessionID)

				// Create pipeline session if it doesn't exist
				o.stateManager.CreateSession(sessionID)

				// Get or create coordinator and start listening
				coordinator := o.getOrCreateCoordinator(sessionID)
				coordinator.StartListening()

				// Send confirmation back to frontend
				confirmMsg := WebSocketMessage{
					Event:     "listening_started",
					SessionID: sessionID,
					Timestamp: time.Now().Format(time.RFC3339),
				}
				conn.WriteJSON(confirmMsg)

			case "trigger_llm":
				sessionID := msg.SessionID
				finalTranscript := msg.FinalTranscript

				if sessionID == "" || finalTranscript == "" {
					o.logger.WithField("connID", connID).Error("Missing session_id or final_transcript in trigger_llm event")
					continue
				}

				o.logger.WithField("connID", connID).WithField("sessionID", sessionID).WithField("transcript", finalTranscript).Info("Trigger LLM event received")

				// Get coordinator and process the final transcript
				coordinator := o.getOrCreateCoordinator(sessionID)
				go func() {
					if err := coordinator.ProcessFinalTranscript(finalTranscript); err != nil {
						o.logger.WithField("sessionID", sessionID).WithField("error", err).Error("Failed to process final transcript")
					}
				}()

			case "session_info":
				// Handle legacy session info for backward compatibility
				if sessionID := msg.SessionID; sessionID != "" {
					o.logger.WithField("connID", connID).WithField("sessionID", sessionID).Info("Received session info from frontend")
					o.wsConnections.Store(connID+"_session", sessionID)
					o.sessionMapping.Store(sessionID, sessionID)
					o.stateManager.CreateSession(sessionID)

					confirmMsg := WebSocketMessage{
						Event:     "session_confirmed",
						SessionID: sessionID,
						Timestamp: time.Now().Format(time.RFC3339),
					}
					conn.WriteJSON(confirmMsg)
				}

			default:
				o.logger.WithField("connID", connID).WithField("event", msg.Event).Warn("Received unhandled event type")
			}
		}
	}
}

// handleConversationControl handles conversation control messages from frontend
func (o *Orchestrator) handleConversationControl(sessionID, action string) {
	o.logger.WithFields(map[string]interface{}{
		"sessionID": sessionID,
		"action":    action,
	}).Info("Handling conversation control")

	// Get or create coordinator for this session
	coordinator := o.getOrCreateCoordinator(sessionID)

	switch action {
	case "start":
		coordinator.StartListening()
	case "stop":
		coordinator.StopConversation()
	case "pause":
		coordinator.PauseConversation()
	default:
		o.logger.WithField("action", action).Warn("Unknown conversation control action")
	}
}

// getOrCreateCoordinator gets or creates a service coordinator for a session
func (o *Orchestrator) getOrCreateCoordinator(sessionID string) *pipeline.ServiceCoordinator {
	if existing, ok := o.coordinators.Load(sessionID); ok {
		return existing.(*pipeline.ServiceCoordinator)
	}

	// Create new coordinator
	flags := o.stateManager.GetSession(sessionID)
	if flags == nil {
		flags = o.stateManager.CreateSession(sessionID)
	}

	coordinator := pipeline.NewServiceCoordinator(
		sessionID,
		flags,
		o.logger,
		o, // Orchestrator implements WebSocketBroadcaster
		o.aiService,
		o.stateManager,
	)

	o.coordinators.Store(sessionID, coordinator)
	return coordinator
}

// handleHealth handles health check requests
func (o *Orchestrator) handleHealth(w http.ResponseWriter, r *http.Request) {
	response := map[string]interface{}{
		"status":     "healthy",
		"timestamp":  time.Now().UTC().Format(time.RFC3339),
		"version":    "2.0.0",
		"service":    "voice-agent-orchestrator",
		"phase":      "4",
		"kafka":      "connected",
		"ai_enabled": true,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// broadcastToWebSocket sends a message to WebSocket clients with matching session ID
func (o *Orchestrator) broadcastToWebSocket(msg WebSocketMessage) {
	o.logger.WithFields(map[string]interface{}{
		"type":      msg.Event,
		"sessionID": msg.SessionID,
	}).Info("Broadcasting WebSocket message")

	o.wsConnections.Range(func(key, value interface{}) bool {
		keyStr := key.(string)

		// Skip session storage keys
		if strings.HasSuffix(keyStr, "_session") {
			return true
		}

		// Check if this connection has a matching session ID
		if sessionKey, ok := o.wsConnections.Load(keyStr + "_session"); ok {
			sessionID := sessionKey.(string)
			o.logger.WithFields(map[string]interface{}{
				"connectionKey":  keyStr,
				"storedSession":  sessionID,
				"messageSession": msg.SessionID,
				"match":          sessionID == msg.SessionID,
			}).Debug("Checking WebSocket connection")

			if sessionID == msg.SessionID {
				conn := value.(*websocket.Conn)
				if err := conn.WriteJSON(msg); err != nil {
					o.logger.WithField("error", err).Error("Failed to send WebSocket message")
					o.wsConnections.Delete(key)
					o.wsConnections.Delete(keyStr + "_session")
				} else {
					o.logger.WithFields(map[string]interface{}{
						"type":      msg.Event,
						"sessionID": msg.SessionID,
					}).Info("WebSocket message sent successfully")
				}
			}
		}
		return true
	})
}

// Stop stops the orchestrator gracefully
func (o *Orchestrator) Stop(ctx context.Context) error {
	o.logger.Info("Stopping orchestrator...")

	// Cancel context to stop all goroutines
	o.cancel()

	// Wait for all goroutines to finish
	done := make(chan struct{})
	go func() {
		o.wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		o.logger.Info("All goroutines stopped")
	case <-ctx.Done():
		o.logger.Warn("Timeout waiting for goroutines to stop")
	}

	// Close services
	if err := o.kafkaService.Close(); err != nil {
		o.logger.WithField("error", err).Error("Failed to close Kafka service")
	}

	if err := o.aiService.Close(); err != nil {
		o.logger.WithField("error", err).Error("Failed to close AI service")
	}

	return nil
}

// consumeAudio consumes audio from the audio-in topic and processes it
func (o *Orchestrator) consumeAudio() {
	defer o.wg.Done()

	o.logger.Info("Starting audio consumption...")

	for {
		select {
		case <-o.ctx.Done():
			o.logger.Info("Audio consumption stopped")
			return
		default:
			// Read message from Kafka
			msg, err := o.kafkaService.ConsumeAudio()
			if err != nil {
				o.logger.WithField("error", err).Error("Failed to consume audio")
				time.Sleep(1 * time.Second) // Avoid tight loop on errors
				continue
			}

			// Process audio in a separate goroutine
			o.wg.Add(1)
			go o.processAudioSession(msg)
		}
	}
}

// processAudioSession processes a single audio session
func (o *Orchestrator) processAudioSession(msg *kafka.AudioMessage) {
	defer o.wg.Done()

	sessionID := msg.SessionID
	o.logger.WithField("sessionID", sessionID).Info("Processing audio session")

	// Get or create session
	audioSession := o.getOrCreateSession(sessionID)

	// Get or create coordinator for state management
	coordinator := o.getOrCreateCoordinator(sessionID)

	// Add audio data to session buffer
	audioSession.AddAudio(msg.AudioData)

	// Update metadata with buffer size and quality
	o.stateManager.UpdateSessionMetadata(sessionID, "buffer_size", len(audioSession.GetAudioBuffer()))
	o.stateManager.UpdateSessionMetadata(sessionID, "audio_quality", audioSession.GetQualityMetrics().AverageQuality)

	// In complete mode, we only process when the session is inactive and has enough audio
	if audioSession.HasEnoughAudio() {
		o.logger.WithField("sessionID", sessionID).Info("Complete audio ready for processing")

		// Get the complete audio buffer
		audioData := audioSession.GetAudioBuffer()

		// Process the complete audio through the AI pipeline with state tracking
		if err := coordinator.ProcessPipeline(audioData); err != nil {
			o.logger.WithFields(map[string]interface{}{
				"sessionID": sessionID,
				"error":     err,
			}).Error("Failed to process AI pipeline")
		}

		// Only clean up the session after AI pipeline processing is complete
		o.cleanupSession(sessionID)
	}
}

// processAIPipeline processes audio through STT -> LLM -> TTS pipeline
func (o *Orchestrator) processAIPipeline(audioSession *session.AudioSession) error {
	mediaSessionID := audioSession.SessionID
	frontendSessionID := o.getFrontendSessionID(mediaSessionID)

	o.logger.WithFields(map[string]interface{}{
		"mediaSessionID":    mediaSessionID,
		"frontendSessionID": frontendSessionID,
	}).Info("Starting AI pipeline")

	// Get audio buffer (Opus encoded)
	opusData := audioSession.GetAudioBuffer()
	o.logger.WithFields(map[string]interface{}{
		"sessionID": mediaSessionID,
		"opusSize":  len(opusData),
	}).Info("Retrieved audio buffer")

	// Check if this is test data (non-audio) - DISABLED for normal operation
	isTestData := false
	if len(opusData) > 0 {
		// Simple heuristic: if all bytes are the same, it's likely test data
		firstByte := opusData[0]
		allSame := true
		for _, b := range opusData {
			if b != firstByte {
				allSame = false
				break
			}
		}
		isTestData = allSame

		// Log test data detection but don't process it
		if isTestData {
			o.logger.WithField("sessionID", mediaSessionID).Info("Test data detected - skipping processing")
			return nil // Skip processing test data
		}
	}

	var transcript string
	var err error

	// Decode Opus to PCM
	pcmData, err := o.audioDecoder.DecodeOpusToPCMSimple(opusData)
	if err != nil {
		o.logger.WithFields(map[string]interface{}{
			"sessionID": mediaSessionID,
			"error":     err,
		}).Error("Failed to decode Opus audio")
		return fmt.Errorf("failed to decode Opus audio: %w", err)
	}

	o.logger.WithFields(map[string]interface{}{
		"sessionID": mediaSessionID,
		"pcmSize":   len(pcmData),
	}).Info("Audio decoded successfully")

	// Convert PCM to WAV format for STT service
	wavData, err := o.audioDecoder.PCMToWAV(pcmData, 16000, 1, 16) // 16kHz mono 16-bit
	if err != nil {
		o.logger.WithFields(map[string]interface{}{
			"sessionID": mediaSessionID,
			"error":     err,
		}).Error("Failed to convert PCM to WAV")
		return fmt.Errorf("failed to convert PCM to WAV: %w", err)
	}

	// Step 1: Speech-to-Text with interim support
	o.logger.WithField("sessionID", mediaSessionID).Info("Starting Speech-to-Text")
	sttStartTime := time.Now()

	// Use the new interim STT method
	sttResp, err := o.aiService.SpeechToTextWithInterim(wavData)
	sttLatency := int(time.Since(sttStartTime).Milliseconds())

	if err != nil {
		o.logger.WithFields(map[string]interface{}{
			"sessionID": mediaSessionID,
			"error":     err,
		}).Error("STT failed")

		// Send error to frontend
		o.broadcastToWebSocket(WebSocketMessage{
			Event:     "error",
			SessionID: frontendSessionID,
			Text:      fmt.Sprintf("Speech-to-Text failed: %v", err),
			Timestamp: time.Now().Format(time.RFC3339),
		})
		return fmt.Errorf("STT failed: %w", err)
	}

	transcript = sttResp.Transcription
	confidence := 0.0
	if sttResp.Confidence != nil {
		confidence = *sttResp.Confidence
	}

	// Enhanced background noise and silence detection - Filter out STT fallback responses
	if transcript == "" {
		// Very small audio chunks - likely background noise
		o.logger.WithField("sessionID", mediaSessionID).Info("Empty transcript detected, skipping LLM/TTS")
		return nil
	} else if transcript == "I heard something. Please continue speaking." {
		// TEMPORARILY DISABLED: Filter out STT fallback responses for background noise
		// o.logger.WithField("sessionID", mediaSessionID).Info("STT fallback response detected, skipping processing")
		// return nil

		// TEMPORARY: Allow fallback responses to be processed for debugging
		o.logger.WithField("sessionID", mediaSessionID).Info("STT fallback response detected, but allowing processing for debugging")
	} else if len(transcript) < 2 {
		// Only skip extremely short transcripts (1 character)
		o.logger.WithField("sessionID", mediaSessionID).Info("Extremely short transcript detected, likely noise - skipping")
		return nil
	}

	// Send transcript to frontend (interim or final)
	messageType := "interim_transcript"
	if sttResp.IsFinal {
		messageType = "final_transcript"
	}

	o.broadcastToWebSocket(WebSocketMessage{
		Event:      messageType,
		SessionID:  frontendSessionID,
		Text:       transcript,
		IsFinal:    sttResp.IsFinal,
		Confidence: confidence,
		Timestamp:  time.Now().Format(time.RFC3339),
	})

	o.logger.WithFields(map[string]interface{}{
		"sessionID":  mediaSessionID,
		"transcript": transcript,
		"is_final":   sttResp.IsFinal,
		"confidence": confidence,
		"latency":    sttLatency,
	}).Info("STT completed successfully")

	// If this is an interim transcript, don't proceed to LLM/TTS
	if !sttResp.IsFinal {
		o.logger.WithField("sessionID", mediaSessionID).Info("Interim transcript sent, waiting for final transcript")
		return nil
	}

	// Step 2: Generate AI Response
	o.logger.WithField("sessionID", mediaSessionID).Info("Starting AI response generation")
	llmStartTime := time.Now()

	// Send processing start notification
	o.broadcastToWebSocket(WebSocketMessage{
		Event:     "processing_start",
		SessionID: frontendSessionID,
		Timestamp: time.Now().Format(time.RFC3339),
	})

	response, err := o.aiService.GenerateResponse(transcript)
	llmLatency := int(time.Since(llmStartTime).Milliseconds())

	if err != nil {
		o.logger.WithFields(map[string]interface{}{
			"sessionID": mediaSessionID,
			"error":     err,
		}).Error("LLM failed")

		// Send error to frontend
		o.broadcastToWebSocket(WebSocketMessage{
			Event:     "error",
			SessionID: frontendSessionID,
			Text:      fmt.Sprintf("AI response generation failed: %v", err),
			Timestamp: time.Now().Format(time.RFC3339),
		})
		return fmt.Errorf("LLM failed: %w", err)
	}

	// Send AI response to frontend
	o.broadcastToWebSocket(WebSocketMessage{
		Event:     "ai_response",
		SessionID: frontendSessionID,
		Text:      response,
		Timestamp: time.Now().Format(time.RFC3339),
	})

	o.logger.WithFields(map[string]interface{}{
		"sessionID": mediaSessionID,
		"response":  response,
		"latency":   llmLatency,
	}).Info("AI response generated successfully")

	// Step 3: Text-to-Speech
	o.logger.WithField("sessionID", mediaSessionID).Info("Starting Text-to-Speech")
	ttsStartTime := time.Now()

	audioData, err := o.aiService.TextToSpeech(response)
	ttsLatency := int(time.Since(ttsStartTime).Milliseconds())

	if err != nil {
		o.logger.WithFields(map[string]interface{}{
			"sessionID": mediaSessionID,
			"error":     err,
		}).Error("TTS failed")

		// Send error to frontend
		o.broadcastToWebSocket(WebSocketMessage{
			Event:     "error",
			SessionID: frontendSessionID,
			Text:      fmt.Sprintf("Text-to-Speech failed: %v", err),
			Timestamp: time.Now().Format(time.RFC3339),
		})
		return fmt.Errorf("TTS failed: %w", err)
	}

	// Send TTS audio to frontend via WebSocket
	o.broadcastToWebSocket(WebSocketMessage{
		Event:     "tts_audio",
		SessionID: frontendSessionID,
		AudioData: base64.StdEncoding.EncodeToString(audioData),
		Timestamp: time.Now().Format(time.RFC3339),
	})

	// Send processing complete notification
	o.broadcastToWebSocket(WebSocketMessage{
		Event:     "processing_complete",
		SessionID: frontendSessionID,
		Timestamp: time.Now().Format(time.RFC3339),
	})

	o.logger.WithFields(map[string]interface{}{
		"sessionID": mediaSessionID,
		"audioSize": len(audioData),
		"latency":   ttsLatency,
	}).Info("TTS completed successfully")

	// Log total pipeline latency
	totalLatency := int(time.Since(sttStartTime).Milliseconds())
	o.logger.WithFields(map[string]interface{}{
		"sessionID":    mediaSessionID,
		"totalLatency": totalLatency,
		"sttLatency":   sttLatency,
		"llmLatency":   llmLatency,
		"ttsLatency":   ttsLatency,
		"transcript":   transcript,
		"response":     response,
	}).Info("AI pipeline completed successfully")

	return nil
}

func main() {
	// Load environment variables
	if err := godotenv.Load(); err != nil {
		log.Printf("Warning: .env file not found, using system environment variables")
	}

	// Initialize logger
	logger := logger.New()
	logger.Info("Starting Voice Agent Orchestrator (Phase 2) with gRPC support...")

	// Load configuration
	cfg := config.Load()

	// Initialize Kafka service
	kafkaService := kafka.NewService(logger)
	if err := kafkaService.Initialize(); err != nil {
		logger.WithField("error", err).Fatal("Failed to initialize Kafka service")
	}

	// Initialize AI services
	aiService := ai.NewService(cfg, logger)
	if err := aiService.Initialize(); err != nil {
		logger.WithField("error", err).Fatal("Failed to initialize AI service")
	}

	// Create orchestrator
	orchestrator := NewOrchestrator(kafkaService, aiService, logger)

	// Initialize pipeline coordinator and session manager for gRPC
	pipelineCoord := pipeline.NewDefaultCoordinator(orchestrator.stateManager, logger)
	sessionMgr := session.NewManager(logger)

	// Initialize gRPC server
	grpcServer := grpc.NewServer(logger, pipelineCoord, sessionMgr, 8002)

	// Start the orchestrator
	if err := orchestrator.Start(); err != nil {
		logger.WithField("error", err).Fatal("Failed to start orchestrator")
	}

	// Start gRPC server in a goroutine
	go func() {
		if err := grpcServer.Start(); err != nil {
			logger.WithField("error", err).Fatal("Failed to start gRPC server")
		}
	}()

	logger.Info("gRPC server started on port 8002")

	// Add gRPC WebSocket handler to the HTTP server
	http.HandleFunc("/grpc", func(w http.ResponseWriter, r *http.Request) {
		// Simple WebSocket handler for gRPC bridge
		upgrader := websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool {
				return true // Allow all origins for development
			},
		}

		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			logger.WithField("error", err).Error("Failed to upgrade WebSocket connection")
			return
		}
		defer conn.Close()

		logger.Info("gRPC WebSocket client connected")

		// Handle messages
		for {
			var msg map[string]interface{}
			err := conn.ReadJSON(&msg)
			if err != nil {
				if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
					logger.WithField("error", err).Error("WebSocket read error")
				}
				break
			}

			// Simple response for now
			response := map[string]interface{}{
				"id": msg["id"],
				"result": map[string]interface{}{
					"status":  "success",
					"message": "gRPC WebSocket bridge active",
				},
			}

			if err := conn.WriteJSON(response); err != nil {
				logger.WithField("error", err).Error("Failed to send WebSocket response")
				break
			}
		}

		logger.Info("gRPC WebSocket client disconnected")
	})

	// Wait for interrupt signal to gracefully shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info("Shutting down orchestrator...")

	// Graceful shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Stop gRPC server
	grpcServer.Stop()

	if err := orchestrator.Stop(ctx); err != nil {
		logger.WithField("error", err).Error("Failed to stop orchestrator gracefully")
	}

	logger.Info("Orchestrator exited")
}

// getOrCreateSession gets or creates a session for the given session ID
func (o *Orchestrator) getOrCreateSession(sessionID string) *session.AudioSession {
	// Validate session ID format
	if !isValidSessionID(sessionID) {
		o.logger.WithField("sessionID", sessionID).Warn("Invalid session ID format, using as-is")
	}

	if existing, ok := o.sessions.Load(sessionID); ok {
		return existing.(*session.AudioSession)
	}

	audioSession := session.NewAudioSession(sessionID, o.logger)
	o.sessions.Store(sessionID, audioSession)
	o.logger.WithField("sessionID", sessionID).Info("Created new audio session")
	return audioSession
}

// isValidSessionID checks if a session ID has a valid format
func isValidSessionID(sessionID string) bool {
	// Check if session ID follows the expected format: session_timestamp_random
	if len(sessionID) < 20 {
		return false
	}

	if !strings.HasPrefix(sessionID, "session_") {
		return false
	}

	parts := strings.Split(sessionID, "_")
	if len(parts) < 3 {
		return false
	}

	// Check if timestamp part is numeric and reasonable (not too old or future)
	if timestamp, err := strconv.ParseInt(parts[1], 10, 64); err != nil {
		return false
	} else {
		// Check if timestamp is within reasonable bounds (not older than 1 year, not in future)
		now := time.Now().UnixNano()
		oneYearAgo := now - (365 * 24 * 60 * 60 * 1000000000)      // 1 year in nanoseconds
		if timestamp < oneYearAgo || timestamp > now+60000000000 { // Allow 1 minute in future
			return false
		}
	}

	// Check if random part exists and has reasonable length
	if len(parts[2]) < 3 {
		return false
	}

	return true
}

// cleanupSession cleans up a session
func (o *Orchestrator) cleanupSession(sessionID string) {
	if audioSession, ok := o.sessions.LoadAndDelete(sessionID); ok {
		audioSession.(*session.AudioSession).Cleanup()
		o.logger.WithField("sessionID", sessionID).Debug("Session cleaned up")
	}
}

// getFrontendSessionID returns the frontend session ID for a given media server session ID
func (o *Orchestrator) getFrontendSessionID(mediaSessionID string) string {
	// First, try to find a direct mapping
	if frontendSessionID, ok := o.sessionMapping.Load(mediaSessionID); ok {
		o.logger.WithFields(map[string]interface{}{
			"mediaSessionID":    mediaSessionID,
			"frontendSessionID": frontendSessionID.(string),
		}).Debug("Found existing session mapping")
		return frontendSessionID.(string)
	}

	// If no direct mapping exists, try to find the most recent active WebSocket session
	var latestSessionID string
	var latestTime int64

	o.wsConnections.Range(func(key, value interface{}) bool {
		keyStr := key.(string)
		// Look for session keys that end with "_session"
		if strings.HasSuffix(keyStr, "_session") {
			if sessionID, ok := o.wsConnections.Load(keyStr); ok {
				sessionIDStr := sessionID.(string)
				// Extract timestamp from the session ID itself
				if strings.HasPrefix(sessionIDStr, "session_") {
					parts := strings.Split(sessionIDStr, "_")
					if len(parts) >= 2 {
						if timestamp, err := strconv.ParseInt(parts[1], 10, 64); err == nil {
							if timestamp > latestTime {
								latestTime = timestamp
								latestSessionID = sessionIDStr
							}
						}
					}
				}
			}
		}
		return true
	})

	// If we found a frontend session, create a mapping
	if latestSessionID != "" {
		o.sessionMapping.Store(mediaSessionID, latestSessionID)
		o.logger.WithFields(map[string]interface{}{
			"mediaSessionID":    mediaSessionID,
			"frontendSessionID": latestSessionID,
		}).Info("Created session mapping from WebSocket connection")
		return latestSessionID
	}

	// Fallback: use the media session ID as the frontend session ID
	// This ensures the system continues to work even without WebSocket mapping
	o.sessionMapping.Store(mediaSessionID, mediaSessionID)
	o.logger.WithFields(map[string]interface{}{
		"mediaSessionID":    mediaSessionID,
		"frontendSessionID": mediaSessionID,
	}).Info("Using media session ID as frontend session ID (no WebSocket mapping found)")
	return mediaSessionID
}
