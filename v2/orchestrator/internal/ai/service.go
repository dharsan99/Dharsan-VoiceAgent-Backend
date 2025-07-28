package ai

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net"
	"net/http"
	"net/url"
	"time"

	"voice-agent-orchestrator/internal/logger"
	"voice-agent-orchestrator/pkg/config"
)

// Service handles AI operations (STT, LLM, TTS) using self-hosted services
type Service struct {
	config *config.Config
	logger *logger.Logger

	// Internal service endpoints
	sttServiceURL string
	ttsServiceURL string
	llmServiceURL string

	// HTTP client for internal service communication
	httpClient *http.Client
}

// STTResponse represents the response from the STT service
type STTResponse struct {
	Transcription  string   `json:"transcription"`
	Language       string   `json:"language"`
	Duration       float64  `json:"duration"`
	Confidence     *float64 `json:"confidence,omitempty"`
	Model          string   `json:"model"`
	ProcessingTime float64  `json:"processing_time"`
	IsFinal        bool     `json:"is_final,omitempty"` // Added for interim transcripts
}

// TTSRequest represents the request to the TTS service
type TTSRequest struct {
	Text   string  `json:"text"`
	Voice  string  `json:"voice"`
	Speed  float64 `json:"speed"`
	Format string  `json:"format"`
}

// TTSResponse represents the response from the TTS service
type TTSResponse struct {
	AudioSize      int     `json:"audio_size"`
	Duration       float64 `json:"duration"`
	Voice          string  `json:"voice"`
	Format         string  `json:"format"`
	ProcessingTime float64 `json:"processing_time"`
}

// LLMRequest represents the request to the LLM service
type LLMRequest struct {
	Prompt       string  `json:"prompt"`
	Model        string  `json:"model"`
	MaxTokens    int     `json:"max_tokens"`
	Temperature  float64 `json:"temperature"`
	TopP         float64 `json:"top_p"`
	SystemPrompt *string `json:"system_prompt,omitempty"`
	Stream       bool    `json:"stream"`
}

// LLMResponse represents the response from the LLM service
type LLMResponse struct {
	Response       string  `json:"response"`
	Model          string  `json:"model"`
	TokensUsed     int     `json:"tokens_used"`
	ProcessingTime float64 `json:"processing_time"`
	FinishReason   string  `json:"finish_reason"`
}

// NewService creates a new AI service with improved HTTP client configuration
func NewService(cfg *config.Config, logger *logger.Logger) *Service {
	// Create a custom transport with connection pooling and better timeout handling
	transport := &http.Transport{
		DialContext: (&net.Dialer{
			Timeout:   30 * time.Second, // Connection timeout
			KeepAlive: 30 * time.Second, // Keep-alive interval
		}).DialContext,
		MaxIdleConns:        100,              // Maximum idle connections
		MaxIdleConnsPerHost: 10,               // Maximum idle connections per host
		IdleConnTimeout:     90 * time.Second, // Idle connection timeout
		TLSHandshakeTimeout: 10 * time.Second, // TLS handshake timeout
		DisableCompression:  true,             // Disable compression for better performance
	}

	return &Service{
		config: cfg,
		logger: logger,
		httpClient: &http.Client{
			Transport: transport,
			Timeout:   120 * time.Second, // Increased timeout for model loading and processing
		},
	}
}

// Initialize initializes the AI service with internal service endpoints
func (s *Service) Initialize() error {
	// Get service URLs from environment or use defaults
	s.sttServiceURL = s.getEnvOrDefault("STT_SERVICE_URL", "http://stt-service.voice-agent-phase5.svc.cluster.local:8000")
	s.ttsServiceURL = s.getEnvOrDefault("TTS_SERVICE_URL", "http://tts-service.voice-agent-phase5.svc.cluster.local:5000")
	s.llmServiceURL = s.getEnvOrDefault("LLM_SERVICE_URL", "http://llm-service.voice-agent-phase5.svc.cluster.local:11434")

	s.logger.WithFields(map[string]interface{}{
		"stt_service": s.sttServiceURL,
		"tts_service": s.ttsServiceURL,
		"llm_service": s.llmServiceURL,
	}).Info("AI service initialized with internal services")

	return nil
}

// Close closes the AI service connections
func (s *Service) Close() error {
	// HTTP client doesn't need explicit closing
	s.logger.Info("AI service closed")
	return nil
}

// SpeechToText converts speech to text using the internal STT service with retry logic
func (s *Service) SpeechToText(audioData []byte) (string, error) {
	startTime := time.Now()
	maxRetries := 3
	var lastErr error

	for attempt := 1; attempt <= maxRetries; attempt++ {
		// Create multipart form data
		var buf bytes.Buffer
		writer := multipart.NewWriter(&buf)

		// Add audio file
		part, err := writer.CreateFormFile("file", "audio.wav")
		if err != nil {
			return "", fmt.Errorf("failed to create form file: %w", err)
		}
		_, err = part.Write(audioData)
		if err != nil {
			return "", fmt.Errorf("failed to write audio data: %w", err)
		}

		// Add parameters
		writer.WriteField("language", "en")
		writer.WriteField("threads", "4")
		writer.WriteField("temperature", "0.3")

		writer.Close()

		// Create request
		req, err := http.NewRequest("POST", s.sttServiceURL+"/transcribe", &buf)
		if err != nil {
			return "", fmt.Errorf("failed to create request: %w", err)
		}
		req.Header.Set("Content-Type", writer.FormDataContentType())
		req.Header.Set("Connection", "keep-alive") // Explicitly request keep-alive

		// Make request
		resp, err := s.httpClient.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("STT service unavailable (attempt %d/%d): %w", attempt, maxRetries, err)
			s.logger.WithFields(map[string]interface{}{
				"attempt":     attempt,
				"max_retries": maxRetries,
				"error":       err.Error(),
			}).Warn("STT request failed, retrying...")

			if attempt < maxRetries {
				// Wait before retry with exponential backoff
				backoffTime := time.Duration(attempt) * time.Second
				time.Sleep(backoffTime)
				continue
			}
			return "", lastErr
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			body, _ := io.ReadAll(resp.Body)
			lastErr = fmt.Errorf("STT service error (attempt %d/%d): %s - %s", attempt, maxRetries, resp.Status, string(body))
			s.logger.WithFields(map[string]interface{}{
				"attempt":       attempt,
				"max_retries":   maxRetries,
				"status_code":   resp.StatusCode,
				"response_body": string(body),
			}).Warn("STT service returned error, retrying...")

			if attempt < maxRetries {
				// Wait before retry with exponential backoff
				backoffTime := time.Duration(attempt) * time.Second
				time.Sleep(backoffTime)
				continue
			}
			return "", lastErr
		}

		// Parse response
		var sttResp STTResponse
		if err := json.NewDecoder(resp.Body).Decode(&sttResp); err != nil {
			lastErr = fmt.Errorf("failed to decode STT response (attempt %d/%d): %w", attempt, maxRetries, err)
			s.logger.WithFields(map[string]interface{}{
				"attempt":     attempt,
				"max_retries": maxRetries,
				"error":       err.Error(),
			}).Warn("Failed to decode STT response, retrying...")

			if attempt < maxRetries {
				// Wait before retry with exponential backoff
				backoffTime := time.Duration(attempt) * time.Second
				time.Sleep(backoffTime)
				continue
			}
			return "", lastErr
		}

		// Success!
		latency := time.Since(startTime)
		s.logger.WithFields(map[string]interface{}{
			"transcription": sttResp.Transcription,
			"latency_ms":    latency.Milliseconds(),
			"processing_ms": int(sttResp.ProcessingTime * 1000),
			"attempt":       attempt,
		}).Debug("STT completed successfully")

		return sttResp.Transcription, nil
	}

	return "", lastErr
}

// SpeechToTextWithInterim performs STT with interim results support
func (s *Service) SpeechToTextWithInterim(audioData []byte) (*STTResponse, error) {
	startTime := time.Now()
	maxRetries := 3
	var lastErr error

	for attempt := 1; attempt <= maxRetries; attempt++ {
		// Create multipart form data
		var buf bytes.Buffer
		writer := multipart.NewWriter(&buf)

		// Add audio file
		part, err := writer.CreateFormFile("file", "audio.wav")
		if err != nil {
			return nil, fmt.Errorf("failed to create form file: %w", err)
		}
		_, err = part.Write(audioData)
		if err != nil {
			return nil, fmt.Errorf("failed to write audio data: %w", err)
		}

		// Add parameters
		writer.WriteField("language", "en")
		writer.WriteField("threads", "4")
		writer.WriteField("temperature", "0.3")

		writer.Close()

		// Create request
		req, err := http.NewRequest("POST", s.sttServiceURL+"/transcribe", &buf)
		if err != nil {
			return nil, fmt.Errorf("failed to create request: %w", err)
		}
		req.Header.Set("Content-Type", writer.FormDataContentType())
		req.Header.Set("Connection", "keep-alive") // Explicitly request keep-alive

		// Make request
		resp, err := s.httpClient.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("STT service unavailable (attempt %d/%d): %w", attempt, maxRetries, err)
			s.logger.WithFields(map[string]interface{}{
				"attempt":     attempt,
				"max_retries": maxRetries,
				"error":       err.Error(),
			}).Warn("STT request failed, retrying...")

			if attempt < maxRetries {
				// Wait before retry with exponential backoff
				backoffTime := time.Duration(attempt) * time.Second
				time.Sleep(backoffTime)
				continue
			}
			return nil, lastErr
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			body, _ := io.ReadAll(resp.Body)
			lastErr = fmt.Errorf("STT service error (attempt %d/%d): %s - %s", attempt, maxRetries, resp.Status, string(body))
			s.logger.WithFields(map[string]interface{}{
				"attempt":       attempt,
				"max_retries":   maxRetries,
				"status_code":   resp.StatusCode,
				"response_body": string(body),
			}).Warn("STT service returned error, retrying...")

			if attempt < maxRetries {
				// Wait before retry with exponential backoff
				backoffTime := time.Duration(attempt) * time.Second
				time.Sleep(backoffTime)
				continue
			}
			return nil, lastErr
		}

		// Parse response
		var sttResp STTResponse
		if err := json.NewDecoder(resp.Body).Decode(&sttResp); err != nil {
			lastErr = fmt.Errorf("failed to decode STT response (attempt %d/%d): %w", attempt, maxRetries, err)
			s.logger.WithFields(map[string]interface{}{
				"attempt":     attempt,
				"max_retries": maxRetries,
				"error":       err.Error(),
			}).Warn("Failed to decode STT response, retrying...")

			if attempt < maxRetries {
				// Wait before retry with exponential backoff
				backoffTime := time.Duration(attempt) * time.Second
				time.Sleep(backoffTime)
				continue
			}
			return nil, lastErr
		}

		// Success!
		latency := time.Since(startTime)

		// Since our STT service doesn't support interim/final distinction,
		// treat all transcripts as final if they contain meaningful content
		if sttResp.Transcription != "" && sttResp.Transcription != "[No speech detected]" && sttResp.Transcription != "[Transcription error]" {
			sttResp.IsFinal = true
		}

		s.logger.WithFields(map[string]interface{}{
			"transcription": sttResp.Transcription,
			"is_final":      sttResp.IsFinal,
			"latency_ms":    latency.Milliseconds(),
			"processing_ms": int(sttResp.ProcessingTime * 1000),
			"attempt":       attempt,
		}).Debug("STT completed successfully")

		return &sttResp, nil
	}

	return nil, lastErr
}

// GenerateResponse generates a response using the internal LLM service with retry logic
func (s *Service) GenerateResponse(prompt string) (string, error) {
	startTime := time.Now()
	maxRetries := 3
	var lastErr error

	for attempt := 1; attempt <= maxRetries; attempt++ {
		// Create request for Ollama API
		llmReq := map[string]interface{}{
			"model":  "qwen3:0.6b", // Use qwen3:0.6b model (523MB)
			"prompt": prompt,
			"stream": false,
			"options": map[string]interface{}{
				"num_predict": 150,
				"temperature": 0.7,
				"top_p":       0.9,
			},
		}

		// Add system prompt if available
		if systemPrompt := s.getSystemPrompt(); systemPrompt != nil {
			llmReq["system"] = *systemPrompt
		}

		reqBody, err := json.Marshal(llmReq)
		if err != nil {
			return "", fmt.Errorf("failed to marshal LLM request: %w", err)
		}

		// Create request to Ollama API
		req, err := http.NewRequest("POST", s.llmServiceURL+"/api/generate", bytes.NewBuffer(reqBody))
		if err != nil {
			return "", fmt.Errorf("failed to create LLM request: %w", err)
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Connection", "keep-alive") // Explicitly request keep-alive

		// Make request
		resp, err := s.httpClient.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("LLM service unavailable (attempt %d/%d): %w", attempt, maxRetries, err)
			s.logger.WithFields(map[string]interface{}{
				"attempt":     attempt,
				"max_retries": maxRetries,
				"error":       err.Error(),
			}).Warn("LLM request failed, retrying...")

			if attempt < maxRetries {
				// Wait before retry with exponential backoff
				backoffTime := time.Duration(attempt) * time.Second
				time.Sleep(backoffTime)
				continue
			}
			return "", lastErr
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			body, _ := io.ReadAll(resp.Body)
			lastErr = fmt.Errorf("LLM service error (attempt %d/%d): %s - %s", attempt, maxRetries, resp.Status, string(body))
			s.logger.WithFields(map[string]interface{}{
				"attempt":       attempt,
				"max_retries":   maxRetries,
				"status_code":   resp.StatusCode,
				"response_body": string(body),
			}).Warn("LLM service returned error, retrying...")

			if attempt < maxRetries {
				// Wait before retry with exponential backoff
				backoffTime := time.Duration(attempt) * time.Second
				time.Sleep(backoffTime)
				continue
			}
			return "", lastErr
		}

		// Parse Ollama response
		var ollamaResp map[string]interface{}
		if err := json.NewDecoder(resp.Body).Decode(&ollamaResp); err != nil {
			lastErr = fmt.Errorf("failed to decode LLM response (attempt %d/%d): %w", attempt, maxRetries, err)
			s.logger.WithFields(map[string]interface{}{
				"attempt":     attempt,
				"max_retries": maxRetries,
				"error":       err.Error(),
			}).Warn("Failed to decode LLM response, retrying...")

			if attempt < maxRetries {
				// Wait before retry with exponential backoff
				backoffTime := time.Duration(attempt) * time.Second
				time.Sleep(backoffTime)
				continue
			}
			return "", lastErr
		}

		response := ollamaResp["response"].(string)
		tokensUsed := int(ollamaResp["eval_count"].(float64))

		latency := time.Since(startTime)
		s.logger.WithFields(map[string]interface{}{
			"response":    response,
			"tokens_used": tokensUsed,
			"latency_ms":  latency.Milliseconds(),
			"attempt":     attempt,
		}).Debug("LLM completed successfully")

		return response, nil
	}

	return "", lastErr
}

// TextToSpeech converts text to speech using the internal TTS service with retry logic
func (s *Service) TextToSpeech(text string) ([]byte, error) {
	startTime := time.Now()
	maxRetries := 3
	var lastErr error

	for attempt := 1; attempt <= maxRetries; attempt++ {
		// Create request parameters
		voice := "en_US-lessac-high"
		speed := 1.0
		format := "wav"

		// Create request using GET endpoint for actual audio data
		url := fmt.Sprintf("%s/synthesize?text=%s&voice=%s&speed=%.1f&format=%s",
			s.ttsServiceURL,
			url.QueryEscape(text),
			voice,
			speed,
			format)

		req, err := http.NewRequest("GET", url, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create TTS request: %w", err)
		}
		req.Header.Set("Connection", "keep-alive") // Explicitly request keep-alive

		// Make request
		resp, err := s.httpClient.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("TTS service unavailable (attempt %d/%d): %w", attempt, maxRetries, err)
			s.logger.WithFields(map[string]interface{}{
				"attempt":     attempt,
				"max_retries": maxRetries,
				"error":       err.Error(),
			}).Warn("TTS request failed, retrying...")

			if attempt < maxRetries {
				// Wait before retry with exponential backoff
				backoffTime := time.Duration(attempt) * time.Second
				time.Sleep(backoffTime)
				continue
			}
			return nil, lastErr
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			body, _ := io.ReadAll(resp.Body)
			lastErr = fmt.Errorf("TTS service error (attempt %d/%d): %s - %s", attempt, maxRetries, resp.Status, string(body))
			s.logger.WithFields(map[string]interface{}{
				"attempt":       attempt,
				"max_retries":   maxRetries,
				"status_code":   resp.StatusCode,
				"response_body": string(body),
			}).Warn("TTS service returned error, retrying...")

			if attempt < maxRetries {
				// Wait before retry with exponential backoff
				backoffTime := time.Duration(attempt) * time.Second
				time.Sleep(backoffTime)
				continue
			}
			return nil, lastErr
		}

		// Read audio data
		audioData, err := io.ReadAll(resp.Body)
		if err != nil {
			lastErr = fmt.Errorf("failed to read TTS response (attempt %d/%d): %w", attempt, maxRetries, err)
			s.logger.WithFields(map[string]interface{}{
				"attempt":     attempt,
				"max_retries": maxRetries,
				"error":       err.Error(),
			}).Warn("Failed to read TTS response, retrying...")

			if attempt < maxRetries {
				// Wait before retry with exponential backoff
				backoffTime := time.Duration(attempt) * time.Second
				time.Sleep(backoffTime)
				continue
			}
			return nil, lastErr
		}

		// Success!
		latency := time.Since(startTime)
		s.logger.WithFields(map[string]interface{}{
			"audio_size": len(audioData),
			"latency_ms": latency.Milliseconds(),
			"attempt":    attempt,
		}).Debug("TTS completed successfully")

		return audioData, nil
	}

	return nil, lastErr
}

// getSystemPrompt returns the default system prompt for voice interactions
func (s *Service) getSystemPrompt() *string {
	prompt := `You are a helpful voice assistant. Keep your responses concise and natural for voice interaction. 
	Respond in a conversational tone that sounds natural when spoken aloud. 
	Keep responses under 100 words and avoid complex formatting.`
	return &prompt
}

// getEnvOrDefault gets an environment variable with a default value
func (s *Service) getEnvOrDefault(key, defaultValue string) string {
	// In a real implementation, you would get this from environment
	// For now, we'll use the default values
	return defaultValue
}
