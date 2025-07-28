package config

import (
	"os"
	"strconv"
)

// Config holds all configuration for the media server
type Config struct {
	ServerAddress string
	WebRTC        WebRTCConfig
	Logging       LoggingConfig
}

// WebRTCConfig holds WebRTC-specific configuration
type WebRTCConfig struct {
	STUNServers []string
	ICEServers  []string
	AudioCodec  string
	SampleRate  int
	// TURN server credentials
	TURNUsername   string
	TURNCredential string
}

// LoggingConfig holds logging configuration
type LoggingConfig struct {
	Level string
}

// Load loads configuration from environment variables
func Load() *Config {
	return &Config{
		ServerAddress: getEnv("SERVER_ADDRESS", ":8001"),
		WebRTC: WebRTCConfig{
			STUNServers: []string{
				// Primary Google STUN servers
				"stun:stun.l.google.com:19302",
				"stun:stun1.l.google.com:19302",
				"stun:stun2.l.google.com:19302",
				"stun:stun3.l.google.com:19302",
				"stun:stun4.l.google.com:19302",
				// Additional reliable STUN servers
				"stun:stun.cloudflare.com:3478",
				"stun:stun.stunprotocol.org:3478",
				// OpenRelay STUN servers
				"stun:stun.relay.metered.ca:80",
				"stun:stun.relay.metered.ca:443",
				// Additional public STUN servers
				"stun:stun.voiparound.com:3478",
				"stun:stun.voipbuster.com:3478",
				"stun:stun.voipstunt.com:3478",
			},
			ICEServers: []string{
				// TURN servers with authentication
				"turn:global.relay.metered.ca:80",
				"turn:global.relay.metered.ca:80?transport=tcp",
				"turn:global.relay.metered.ca:443",
				"turns:global.relay.metered.ca:443?transport=tcp",
			},
			AudioCodec: getEnv("AUDIO_CODEC", "opus"),
			SampleRate: getEnvAsInt("SAMPLE_RATE", 48000),
			// TURN server credentials
			TURNUsername:   "10f1dfa42670d72b3a31482a",
			TURNCredential: "FvFd4gNrt9+OZk4r",
		},
		Logging: LoggingConfig{
			Level: getEnv("LOG_LEVEL", "info"),
		},
	}
}

// getEnv gets an environment variable or returns a default value
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// getEnvAsInt gets an environment variable as integer or returns a default value
func getEnvAsInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}
