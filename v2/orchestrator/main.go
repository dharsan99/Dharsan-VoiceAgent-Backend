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

// getEnv gets an environment variable with a default value
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

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
	// TTS request fields
	Voice  string  `json:"voice,omitempty"`
	Speed  float64 `json:"speed,omitempty"`
	Format string  `json:"format,omitempty"`
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
	// Kafka enabled flag
	kafkaEnabled bool
}

// NewOrchestrator creates a new orchestrator instance
func NewOrchestrator(kafkaService *kafka.Service, aiService *ai.Service, logger *logger.Logger, kafkaEnabled bool) *Orchestrator {
	ctx, cancel := context.WithCancel(context.Background())
	return &Orchestrator{
		kafkaService: kafkaService,
		aiService:    aiService,
		audioDecoder: audio.NewDecoder(logger),
		logger:       logger,
		ctx:          ctx,
		cancel:       cancel,
		stateManager: pipeline.NewPipelineStateManager(logger),
		kafkaEnabled: kafkaEnabled,
	}
}

// Start starts the orchestrator
func (o *Orchestrator) Start() error {
	o.logger.Info("Starting orchestrator with pipeline state management...")

	// Start WebSocket server
	go o.startWebSocketServer()

	// Start audio consumption only if Kafka is enabled
	if o.kafkaEnabled {
		go o.consumeAudio()
		o.logger.Info("Audio consumption started (Kafka enabled)")
	} else {
		o.logger.Info("Audio consumption disabled (Kafka disabled for local development)")
	}

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

	// Logs endpoint for backend log access
	http.HandleFunc("/logs", corsMiddleware(o.handleLogs))

	// WebSocket endpoint
	http.HandleFunc("/ws", corsMiddleware(o.handleWebSocket))

	// gRPC WebSocket endpoint
	http.HandleFunc("/grpc", corsMiddleware(func(w http.ResponseWriter, r *http.Request) {
		// Simple WebSocket handler for gRPC bridge
		upgrader := websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool {
				return true // Allow all origins for development
			},
		}

		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			o.logger.WithField("error", err).Error("Failed to upgrade gRPC WebSocket connection")
			return
		}
		defer conn.Close()

		o.logger.Info("gRPC WebSocket client connected")

		// Handle messages
		for {
			var msg map[string]interface{}
			err := conn.ReadJSON(&msg)
			if err != nil {
				if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
					o.logger.WithField("error", err).Error("gRPC WebSocket read error")
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
				o.logger.WithField("error", err).Error("Failed to send gRPC WebSocket response")
				break
			}
		}

		o.logger.Info("gRPC WebSocket client disconnected")
	}))

	port := ":" + getEnv("ORCHESTRATOR_PORT", "8004")
	o.logger.WithField("port", port).Info("Starting WebSocket server")

	// Check if HTTPS is enabled
	enableHTTPS := os.Getenv("ENABLE_HTTPS") == "true"

	if enableHTTPS {
		// HTTPS server configuration
		certPath := os.Getenv("SSL_CERT_PATH")
		keyPath := os.Getenv("SSL_KEY_PATH")

		if certPath == "" {
			certPath = "/etc/ssl/certs/server.crt"
		}
		if keyPath == "" {
			keyPath = "/etc/ssl/private/server.key"
		}

		o.logger.WithFields(map[string]interface{}{
			"cert_path": certPath,
			"key_path":  keyPath,
		}).Info("Starting HTTPS WebSocket server")

		if err := http.ListenAndServeTLS(port, certPath, keyPath, nil); err != nil {
			o.logger.WithField("error", err).Fatal("Failed to start HTTPS WebSocket server")
		}
	} else {
		// HTTP server (for development)
		o.logger.Info("Starting HTTP WebSocket server (development mode)")
		if err := http.ListenAndServe(port, nil); err != nil {
			o.logger.WithField("error", err).Fatal("Failed to start HTTP WebSocket server")
		}
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

	// Set initial read deadline (increased for long-running operations)
	conn.SetReadDeadline(time.Now().Add(300 * time.Second)) // 5 minutes for LLM processing

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

			// Extend read deadline after each message
			conn.SetReadDeadline(time.Now().Add(300 * time.Second))

			// Debug: Log the raw message first
			o.logger.WithFields(map[string]interface{}{
				"connID":        connID,
				"rawMessage":    string(message),
				"messageLength": len(message),
				"timestamp":     time.Now().Format(time.RFC3339),
			}).Info("Raw WebSocket message received")

			// Parse and handle the message
			var msg WebSocketMessage
			if err := json.Unmarshal(message, &msg); err != nil {
				o.logger.WithFields(map[string]interface{}{
					"connID":        connID,
					"error":         err,
					"message":       string(message),
					"messageLength": len(message),
					"timestamp":     time.Now().Format(time.RFC3339),
				}).Error("Failed to parse WebSocket message")
				continue
			}

			// Debug: Log the parsed message
			o.logger.WithFields(map[string]interface{}{
				"connID":    connID,
				"event":     msg.Event,
				"text":      msg.Text,
				"sessionID": msg.SessionID,
				"voice":     msg.Voice,
				"speed":     msg.Speed,
				"format":    msg.Format,
			}).Info("Parsed WebSocket message")

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

				o.logger.WithFields(map[string]interface{}{
					"connID":    connID,
					"sessionID": sessionID,
					"event":     "start_listening",
					"timestamp": time.Now().Format(time.RFC3339),
				}).Info("Start listening event received - Processing pipeline initialization")

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

			case "ping":
				// Handle ping messages for heartbeat
				o.logger.WithField("connID", connID).Debug("Received ping message")
				pongMsg := WebSocketMessage{
					Event:     "pong",
					Timestamp: time.Now().Format(time.RFC3339),
				}
				conn.WriteJSON(pongMsg)

			case "tts_request":
				// Handle TTS synthesis requests
				text := msg.Text
				voice := msg.Voice
				if voice == "" {
					voice = "en_US-lessac-high" // Default voice
				}
				speed := msg.Speed
				if speed == 0 {
					speed = 1.0 // Default speed
				}
				format := msg.Format
				if format == "" {
					format = "wav" // Default format
				}

				o.logger.WithFields(map[string]interface{}{
					"connID": connID,
					"text":   text,
					"voice":  voice,
					"speed":  speed,
					"format": format,
				}).Info("TTS request received")

				// Use the AI service to synthesize speech
				o.logger.WithFields(map[string]interface{}{
					"text":   text,
					"voice":  voice,
					"speed":  speed,
					"format": format,
				}).Info("Calling AI service TextToSpeechWithParams")
				audioData, err := o.aiService.TextToSpeechWithParams(text, voice, speed, format)
				if err != nil {
					o.logger.WithField("error", err).Error("Failed to synthesize speech")
					errorMsg := WebSocketMessage{
						Event:     "error",
						Text:      "Failed to synthesize speech",
						Timestamp: time.Now().Format(time.RFC3339),
					}
					conn.WriteJSON(errorMsg)
					continue
				}

				o.logger.WithFields(map[string]interface{}{
					"audioDataSize": len(audioData),
					"text":          text,
				}).Info("TTS synthesis successful")

				// Send audio data back to frontend
				audioMsg := WebSocketMessage{
					Event:     "tts_audio_chunk",
					AudioData: base64.StdEncoding.EncodeToString(audioData),
					Timestamp: time.Now().Format(time.RFC3339),
				}

				o.logger.WithFields(map[string]interface{}{
					"audioDataSize": len(audioData),
					"base64Size":    len(audioMsg.AudioData),
				}).Info("Sending TTS audio chunk to frontend")

				if err := conn.WriteJSON(audioMsg); err != nil {
					o.logger.WithField("error", err).Error("Failed to send TTS audio chunk")
				} else {
					o.logger.Info("TTS audio chunk sent successfully")
				}

			case "audio_data":
				// Handle audio data from frontend
				sessionID := msg.SessionID
				audioData := msg.AudioData
				isFinal := msg.IsFinal

				if sessionID == "" {
					o.logger.WithField("connID", connID).Error("Missing session_id in audio_data event")
					continue
				}

				o.logger.WithFields(map[string]interface{}{
					"connID":    connID,
					"sessionID": sessionID,
					"audioSize": len(audioData),
					"isFinal":   isFinal,
					"event":     "audio_data",
					"timestamp": time.Now().Format(time.RFC3339),
				}).Info("Received audio_data event from frontend - Starting audio processing pipeline")

				if audioData != "" {
					// Decode base64 audio data
					decodedAudio, err := base64.StdEncoding.DecodeString(audioData)
					if err != nil {
						o.logger.WithField("error", err).Error("Failed to decode base64 audio data")
						continue
					}

					o.logger.WithFields(map[string]interface{}{
						"sessionID": sessionID,
						"audioSize": len(decodedAudio),
					}).Debug("Decoded audio data successfully")

					// If this is the final chunk, process the complete AI pipeline
					if isFinal {
						o.logger.WithField("sessionID", sessionID).Info("Processing final audio chunk with complete AI pipeline")
						go func() {
							// Convert PCM to WAV format for STT service
							wavData, err := o.audioDecoder.PCMToWAV(decodedAudio, 16000, 1, 16) // 16kHz mono 16-bit
							if err != nil {
								o.logger.WithField("sessionID", sessionID).WithField("error", err).Error("Failed to convert PCM to WAV")
								return
							}

							o.logger.WithFields(map[string]interface{}{
								"sessionID": sessionID,
								"pcmSize":   len(decodedAudio),
								"wavSize":   len(wavData),
							}).Debug("Converted PCM to WAV successfully")

							// Get or create coordinator for this session
							coordinator := o.getOrCreateCoordinator(sessionID)

							// Process the complete AI pipeline: STT → LLM → TTS
							if err := coordinator.ProcessPipeline(wavData); err != nil {
								o.logger.WithField("sessionID", sessionID).WithField("error", err).Error("Failed to process AI pipeline")
							}
						}()
					}
				}

			default:
				// Check if this is a ping message with "type" field instead of "event"
				if msg.Text == "" && msg.SessionID == "" && msg.Event == "" {
					// Try to parse as a ping message with "type" field
					var pingMsg struct {
						Type string `json:"type"`
					}
					if err := json.Unmarshal(message, &pingMsg); err == nil && pingMsg.Type == "ping" {
						o.logger.WithField("connID", connID).Debug("Received ping message (type format)")
						pongMsg := WebSocketMessage{
							Event:     "pong",
							Timestamp: time.Now().Format(time.RFC3339),
						}
						conn.WriteJSON(pongMsg)
						continue
					}
				}

				o.logger.WithFields(map[string]interface{}{
					"connID":    connID,
					"event":     msg.Event,
					"text":      msg.Text,
					"sessionID": msg.SessionID,
				}).Warn("Received unhandled event type")
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
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":    "healthy",
		"timestamp": time.Now().Format(time.RFC3339),
		"service":   "orchestrator",
		"version":   "phase2",
	})
}

// handleLogs handles log retrieval requests
func (o *Orchestrator) handleLogs(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	// Get query parameters
	sessionID := r.URL.Query().Get("session_id")
	limit := r.URL.Query().Get("limit")
	service := r.URL.Query().Get("service")

	// Parse limit with default
	limitInt := 100
	if limit != "" {
		if parsed, err := strconv.Atoi(limit); err == nil && parsed > 0 {
			limitInt = parsed
		}
	}

	// Get logs from different services based on environment
	env := os.Getenv("ENVIRONMENT")
	var logs []map[string]interface{}

	if env == "production" {
		// In production, fetch logs from GKE services
		logs = o.getProductionLogs(sessionID, limitInt, service)
	} else {
		// In development, fetch logs from localhost services
		logs = o.getDevelopmentLogs(sessionID, limitInt, service)
	}

	response := map[string]interface{}{
		"status":      "success",
		"timestamp":   time.Now().Format(time.RFC3339),
		"service":     "orchestrator",
		"environment": env,
		"logs":        logs,
		"count":       len(logs),
		"session_id":  sessionID,
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}

// getProductionLogs fetches logs from GKE services
func (o *Orchestrator) getProductionLogs(sessionID string, limit int, service string) []map[string]interface{} {
	var logs []map[string]interface{}

	// Define service URLs for production
	services := map[string]string{
		"orchestrator": "http://orchestrator.voice-agent-phase5.svc.cluster.local:8001",
		"stt":          "http://stt-service.voice-agent-phase5.svc.cluster.local:8000",
		"tts":          "http://tts-service.voice-agent-phase5.svc.cluster.local:5001",
		"media-server": "http://media-server.voice-agent-phase5.svc.cluster.local:8001",
		"logging":      "http://logging-service.voice-agent-phase5.svc.cluster.local:8080",
	}

	// If specific service requested, only fetch from that service
	if service != "" {
		if serviceURL, exists := services[service]; exists {
			serviceLogs := o.fetchServiceLogs(serviceURL, sessionID, limit)
			logs = append(logs, serviceLogs...)
		}
	} else {
		// Fetch from all services
		for serviceName, serviceURL := range services {
			serviceLogs := o.fetchServiceLogs(serviceURL, sessionID, limit)
			// Add service identifier to each log
			for _, log := range serviceLogs {
				log["service"] = serviceName
			}
			logs = append(logs, serviceLogs...)
		}
	}

	return logs
}

// getDevelopmentLogs fetches logs from localhost services
func (o *Orchestrator) getDevelopmentLogs(sessionID string, limit int, service string) []map[string]interface{} {
	var logs []map[string]interface{}

	// Define service URLs for development
	orchestratorPort := getEnv("ORCHESTRATOR_PORT", "8004")
	sttPort := getEnv("STT_SERVICE_PORT", "8000")
	ttsPort := getEnv("TTS_SERVICE_PORT", "5001")
	mediaServerPort := getEnv("MEDIA_SERVER_PORT", "8001")
	llmPort := getEnv("LLM_SERVICE_PORT", "8003")

	services := map[string]string{
		"orchestrator": fmt.Sprintf("http://localhost:%s", orchestratorPort),
		"stt":          fmt.Sprintf("http://localhost:%s", sttPort),
		"tts":          fmt.Sprintf("http://localhost:%s", ttsPort),
		"media-server": fmt.Sprintf("http://localhost:%s", mediaServerPort),
		"llm":          fmt.Sprintf("http://localhost:%s", llmPort),
	}

	// If specific service requested, only fetch from that service
	if service != "" {
		if serviceURL, exists := services[service]; exists {
			serviceLogs := o.fetchServiceLogs(serviceURL, sessionID, limit)
			logs = append(logs, serviceLogs...)
		}
	} else {
		// Fetch from all services
		for serviceName, serviceURL := range services {
			serviceLogs := o.fetchServiceLogs(serviceURL, sessionID, limit)
			// Add service identifier to each log
			for _, log := range serviceLogs {
				log["service"] = serviceName
			}
			logs = append(logs, serviceLogs...)
		}
	}

	return logs
}

// fetchServiceLogs fetches logs from a specific service
func (o *Orchestrator) fetchServiceLogs(serviceURL, sessionID string, limit int) []map[string]interface{} {
	var logs []map[string]interface{}

	// Create HTTP client with timeout
	client := &http.Client{
		Timeout: 5 * time.Second,
	}

	// Build request URL
	reqURL := fmt.Sprintf("%s/logs", serviceURL)
	if sessionID != "" {
		reqURL += fmt.Sprintf("?session_id=%s&limit=%d", sessionID, limit)
	} else {
		reqURL += fmt.Sprintf("?limit=%d", limit)
	}

	// Make request
	resp, err := client.Get(reqURL)
	if err != nil {
		o.logger.WithFields(map[string]interface{}{
			"service_url": serviceURL,
			"error":       err,
		}).Warn("Failed to fetch logs from service")
		return logs
	}
	defer resp.Body.Close()

	// Parse response
	if resp.StatusCode == http.StatusOK {
		var response map[string]interface{}
		if err := json.NewDecoder(resp.Body).Decode(&response); err == nil {
			if logsData, ok := response["logs"]; ok {
				if logsArray, ok := logsData.([]interface{}); ok {
					for _, logItem := range logsArray {
						if logMap, ok := logItem.(map[string]interface{}); ok {
							logs = append(logs, logMap)
						}
					}
				}
			}
		}
	}

	return logs
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

	// Check if Kafka is enabled
	if !o.kafkaEnabled {
		o.logger.Info("Kafka disabled, audio consumption not started")
		return
	}

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

	// Reset pipeline state to idle after completion
	o.stateManager.UpdateSessionState(frontendSessionID, pipeline.PipelineStateIdle)

	o.logger.WithFields(map[string]interface{}{
		"sessionID": frontendSessionID,
		"action":    "pipeline_reset",
	}).Info("Pipeline state reset to idle after completion")

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
	// Always load env.local for local development
	if err := godotenv.Load("env.local"); err != nil {
		log.Printf("Warning: env.local file not found, using system environment variables")
	}

	// Initialize logger
	logger := logger.New()
	logger.Info("Starting Voice Agent Orchestrator (Phase 2) with gRPC support...")

	// Load configuration
	cfg := config.Load()

	// Initialize Kafka service (optional for local development)
	kafkaService := kafka.NewService(logger)
	kafkaEnabled := getEnv("KAFKA_ENABLED", "true")

	if kafkaEnabled == "true" {
		if err := kafkaService.Initialize(); err != nil {
			logger.WithField("error", err).Fatal("Failed to initialize Kafka service")
		}
		logger.Info("Kafka service initialized successfully")
	} else {
		logger.Info("Kafka service disabled for local development")
	}

	// Initialize AI services
	aiService := ai.NewService(cfg, logger)
	if err := aiService.Initialize(); err != nil {
		logger.WithField("error", err).Fatal("Failed to initialize AI service")
	}

	// Create orchestrator
	orchestrator := NewOrchestrator(kafkaService, aiService, logger, kafkaEnabled == "true")

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
