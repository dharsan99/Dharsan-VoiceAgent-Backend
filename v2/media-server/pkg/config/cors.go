package config

import (
	"os"
	"strings"
)

// CORSConfig holds CORS configuration
type CORSConfig struct {
	AllowedOrigins   []string
	AllowedMethods   []string
	AllowedHeaders   []string
	AllowCredentials bool
}

// GetCORSConfig returns CORS configuration based on environment
func GetCORSConfig() *CORSConfig {
	env := os.Getenv("ENVIRONMENT")

	// Default configuration for development
	config := &CORSConfig{
		AllowedOrigins:   []string{"*"},
		AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Content-Type", "Authorization", "Accept", "Origin", "User-Agent", "X-Session-ID"},
		AllowCredentials: true,
	}

	// Production configuration
	if env == "production" {
		// Get allowed origins from environment variable
		allowedOrigins := os.Getenv("CORS_ALLOWED_ORIGINS")
		if allowedOrigins != "" {
			config.AllowedOrigins = strings.Split(allowedOrigins, ",")
		} else {
			// Default production origins
			config.AllowedOrigins = []string{
				"https://dharsan-voice-agent-frontend.vercel.app",
				"https://voice-agent-frontend.vercel.app",
				"https://voice-agent.com",
				"https://www.voice-agent.com",
			}
		}

		// Production security headers
		config.AllowedHeaders = append(config.AllowedHeaders,
			"X-Requested-With",
			"X-CSRF-Token",
		)
	}

	return config
}

// GetAllowedOrigin checks if the given origin is allowed
func (c *CORSConfig) GetAllowedOrigin(origin string) string {
	// Allow all origins in development
	if len(c.AllowedOrigins) == 1 && c.AllowedOrigins[0] == "*" {
		return "*"
	}

	// Check if origin is in allowed list
	for _, allowed := range c.AllowedOrigins {
		if allowed == origin {
			return origin
		}
	}

	return ""
}
