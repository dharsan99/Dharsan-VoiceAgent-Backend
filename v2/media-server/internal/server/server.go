package server

import (
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"voice-agent-media-server/internal/kafka"
	"voice-agent-media-server/internal/webrtc"
	"voice-agent-media-server/internal/whip"
	"voice-agent-media-server/pkg/config"
	"voice-agent-media-server/pkg/logger"

	"github.com/gorilla/mux"
)

// Server represents the media server
type Server struct {
	config       *config.Config
	logger       *logger.Logger
	webrtcConfig *webrtc.Config
	kafkaService *kafka.Service
	whipHandler  *whip.Handler
	startTime    time.Time
}

// New creates a new server instance
func New(cfg *config.Config, logger *logger.Logger) *Server {
	// Create WebRTC configuration
	webrtcConfig := webrtc.NewConfig(cfg)

	// Initialize Kafka service
	kafkaService := kafka.NewService(logger)
	if err := kafkaService.Initialize(); err != nil {
		logger.WithField("error", err).Warn("Failed to initialize Kafka service, falling back to echo mode")
		kafkaService = nil
	}

	// Create WHIP handler
	whipHandler := whip.NewHandler(webrtcConfig, logger, kafkaService)

	return &Server{
		config:       cfg,
		logger:       logger,
		webrtcConfig: webrtcConfig,
		kafkaService: kafkaService,
		whipHandler:  whipHandler,
		startTime:    time.Now(),
	}
}

// RegisterRoutes registers all HTTP routes
func (s *Server) RegisterRoutes(router *mux.Router) {
	// WHIP endpoint - allow both POST and OPTIONS
	router.HandleFunc("/whip", s.whipHandler.HandleWHIP).Methods("POST", "OPTIONS")

	// Listening control endpoints
	router.HandleFunc("/listening/start", s.handleStartListening).Methods("POST", "OPTIONS")
	router.HandleFunc("/listening/stop", s.handleStopListening).Methods("POST", "OPTIONS")
	router.HandleFunc("/listening/status", s.handleListeningStatus).Methods("GET", "OPTIONS")

	// Health check endpoint
	router.HandleFunc("/health", s.handleHealth).Methods("GET")

	// Metrics endpoint
	router.HandleFunc("/metrics", s.handleMetrics).Methods("GET")

	// Logs endpoint
	router.HandleFunc("/logs", s.handleLogs).Methods("GET")

	// Root endpoint
	router.HandleFunc("/", s.handleRoot).Methods("GET")
}

// Close cleans up server resources
func (s *Server) Close() error {
	if s.kafkaService != nil {
		return s.kafkaService.Close()
	}
	return nil
}

// handleHealth handles health check requests
func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	kafkaStatus := "disconnected"
	if s.kafkaService != nil {
		kafkaStatus = "connected"
	}

	response := map[string]interface{}{
		"status":     "healthy",
		"timestamp":  time.Now().UTC().Format(time.RFC3339),
		"version":    "2.0.0",
		"service":    "voice-agent-media-server",
		"phase":      "2",
		"kafka":      kafkaStatus,
		"ai_enabled": s.kafkaService != nil,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// handleMetrics handles metrics requests
func (s *Server) handleMetrics(w http.ResponseWriter, r *http.Request) {
	response := map[string]interface{}{
		"connections": s.whipHandler.GetConnectionCount(),
		"timestamp":   time.Now().UTC().Format(time.RFC3339),
		"uptime":      time.Since(s.startTime).String(),
		"phase":       "2",
		"ai_enabled":  s.kafkaService != nil,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// handleLogs handles log retrieval requests
func (s *Server) handleLogs(w http.ResponseWriter, r *http.Request) {
	// Get query parameters
	sessionID := r.URL.Query().Get("session_id")
	limit := r.URL.Query().Get("limit")

	// Parse limit with default
	limitInt := 100
	if limit != "" {
		if parsed, err := strconv.Atoi(limit); err == nil && parsed > 0 {
			limitInt = parsed
		}
	}

	// For now, return a simple response indicating logs are available
	// In a full implementation, this would fetch logs from a log storage system
	response := map[string]interface{}{
		"status":     "success",
		"service":    "media-server",
		"timestamp":  time.Now().UTC().Format(time.RFC3339),
		"logs":       []map[string]interface{}{}, // Empty for now
		"count":      0,
		"session_id": sessionID,
		"limit":      limitInt,
		"message":    "Logs endpoint available - logs would be fetched from log storage system",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// handleStartListening enables audio processing for a session
func (s *Server) handleStartListening(w http.ResponseWriter, r *http.Request) {
	// Handle OPTIONS requests for CORS preflight
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	var request struct {
		SessionID string `json:"session_id"`
	}

	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if request.SessionID == "" {
		http.Error(w, "Session ID is required", http.StatusBadRequest)
		return
	}

	if err := s.whipHandler.SetListeningState(request.SessionID, true); err != nil {
		s.logger.WithField("error", err).Error("Failed to start listening")
		http.Error(w, "Failed to start listening", http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"status":     "success",
		"session_id": request.SessionID,
		"listening":  true,
		"timestamp":  time.Now().UTC().Format(time.RFC3339),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// handleStopListening disables audio processing for a session
func (s *Server) handleStopListening(w http.ResponseWriter, r *http.Request) {
	// Handle OPTIONS requests for CORS preflight
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	var request struct {
		SessionID string `json:"session_id"`
	}

	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if request.SessionID == "" {
		http.Error(w, "Session ID is required", http.StatusBadRequest)
		return
	}

	if err := s.whipHandler.SetListeningState(request.SessionID, false); err != nil {
		s.logger.WithField("error", err).Error("Failed to stop listening")
		http.Error(w, "Failed to stop listening", http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"status":     "success",
		"session_id": request.SessionID,
		"listening":  false,
		"timestamp":  time.Now().UTC().Format(time.RFC3339),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// handleListeningStatus returns the current listening state for a session
func (s *Server) handleListeningStatus(w http.ResponseWriter, r *http.Request) {
	// Handle OPTIONS requests for CORS preflight
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	sessionID := r.URL.Query().Get("session_id")
	if sessionID == "" {
		http.Error(w, "Session ID is required", http.StatusBadRequest)
		return
	}

	isListening, err := s.whipHandler.GetListeningState(sessionID)
	if err != nil {
		s.logger.WithField("error", err).Error("Failed to get listening status")
		http.Error(w, "Failed to get listening status", http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"status":     "success",
		"session_id": sessionID,
		"listening":  isListening,
		"timestamp":  time.Now().UTC().Format(time.RFC3339),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// handleRoot handles root requests
func (s *Server) handleRoot(w http.ResponseWriter, r *http.Request) {
	response := map[string]interface{}{
		"service":    "Voice Agent Media Server",
		"version":    "2.0.0",
		"phase":      "2",
		"ai_enabled": s.kafkaService != nil,
		"endpoints": []string{
			"POST /whip - WHIP protocol endpoint",
			"GET /health - Health check",
			"GET /metrics - Server metrics",
		},
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}
