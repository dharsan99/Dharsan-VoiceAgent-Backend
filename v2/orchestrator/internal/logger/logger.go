package logger

import (
	"github.com/sirupsen/logrus"
)

// Logger wraps logrus.Logger
type Logger struct {
	*logrus.Logger
}

// New creates a new logger instance
func New() *Logger {
	logger := logrus.New()
	logger.SetFormatter(&logrus.JSONFormatter{})
	logger.SetLevel(logrus.DebugLevel)
	return &Logger{Logger: logger}
}

// WithField adds a field to the log entry
func (l *Logger) WithField(key string, value interface{}) *logrus.Entry {
	return l.Logger.WithField(key, value)
}

// WithFields adds multiple fields to the log entry
func (l *Logger) WithFields(fields map[string]interface{}) *logrus.Entry {
	return l.Logger.WithFields(logrus.Fields(fields))
}
