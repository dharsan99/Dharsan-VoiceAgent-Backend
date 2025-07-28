package session

import (
	"sync"
	"time"

	"voice-agent-orchestrator/internal/logger"
)

// Manager manages multiple audio sessions
type Manager struct {
	sessions map[string]*AudioSession
	mu       sync.RWMutex
	logger   *logger.Logger
}

// NewManager creates a new session manager
func NewManager(logger *logger.Logger) *Manager {
	return &Manager{
		sessions: make(map[string]*AudioSession),
		logger:   logger,
	}
}

// CreateSession creates a new session
func (m *Manager) CreateSession(sessionID string) *AudioSession {
	m.mu.Lock()
	defer m.mu.Unlock()

	session := NewAudioSession(sessionID, m.logger)
	m.sessions[sessionID] = session

	m.logger.WithField("sessionID", sessionID).Info("Created new session")
	return session
}

// GetSession retrieves a session by ID
func (m *Manager) GetSession(sessionID string) (*AudioSession, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	session, exists := m.sessions[sessionID]
	return session, exists
}

// RemoveSession removes a session
func (m *Manager) RemoveSession(sessionID string) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if session, exists := m.sessions[sessionID]; exists {
		session.Cleanup()
		delete(m.sessions, sessionID)
		m.logger.WithField("sessionID", sessionID).Info("Removed session")
	}
}

// GetActiveSessionCount returns the number of active sessions
func (m *Manager) GetActiveSessionCount() int {
	m.mu.RLock()
	defer m.mu.RUnlock()

	count := 0
	for _, session := range m.sessions {
		if session.IsSessionActive() {
			count++
		}
	}
	return count
}

// GenerateSessionID generates a unique session ID
func (m *Manager) GenerateSessionID() string {
	return time.Now().Format("20060102150405") + "-" + generateRandomString(8)
}

// CleanupStaleSessions removes stale sessions
func (m *Manager) CleanupStaleSessions() {
	m.mu.Lock()
	defer m.mu.Unlock()

	for sessionID, session := range m.sessions {
		if session.IsStale() {
			session.Cleanup()
			delete(m.sessions, sessionID)
			m.logger.WithField("sessionID", sessionID).Info("Cleaned up stale session")
		}
	}
}

// generateRandomString generates a random string of specified length
func generateRandomString(length int) string {
	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	b := make([]byte, length)
	for i := range b {
		b[i] = charset[time.Now().UnixNano()%int64(len(charset))]
	}
	return string(b)
}
