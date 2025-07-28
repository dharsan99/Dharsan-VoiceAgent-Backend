package config

import (
	"os"
)

// Config holds the application configuration
type Config struct {
	// Kafka configuration
	KafkaBrokers string

	// Google Cloud configuration
	GoogleCredentialsPath string
	GoogleAPIKey          string

	// AI service configuration
	STTModel    string
	LLMModel    string
	TTSVoice    string
	TTSLanguage string
}

// Load loads configuration from environment variables
func Load() *Config {
	return &Config{
		// Kafka configuration
		KafkaBrokers: getEnv("KAFKA_BROKERS", "redpanda.voice-agent-phase5.svc.cluster.local:9092"),

		// Google Cloud configuration
		GoogleCredentialsPath: getEnv("GOOGLE_APPLICATION_CREDENTIALS", ""),
		GoogleAPIKey:          getEnv("GOOGLE_API_KEY", ""),

		// AI service configuration
		STTModel:    getEnv("STT_MODEL", "latest_long"),
		LLMModel:    getEnv("LLM_MODEL", "gemini-1.5-flash"),
		TTSVoice:    getEnv("TTS_VOICE", "en-US-Neural2-A"),
		TTSLanguage: getEnv("TTS_LANGUAGE", "en-US"),
	}
}

// getEnv gets an environment variable with a default value
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
