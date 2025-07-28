package logger

import (
	"os"

	"github.com/sirupsen/logrus"
)

// Logger wraps logrus logger
type Logger struct {
	*logrus.Logger
}

// New creates a new logger instance
func New() *Logger {
	log := logrus.New()
	
	// Set output to stdout
	log.SetOutput(os.Stdout)
	
	// Set formatter to JSON for structured logging
	log.SetFormatter(&logrus.JSONFormatter{
		TimestampFormat: "2006-01-02T15:04:05.000Z07:00",
	})
	
	// Set default level
	log.SetLevel(logrus.InfoLevel)
	
	return &Logger{log}
}

// SetLevel sets the logging level
func (l *Logger) SetLevel(level string) {
	switch level {
	case "debug":
		l.Logger.SetLevel(logrus.DebugLevel)
	case "info":
		l.Logger.SetLevel(logrus.InfoLevel)
	case "warn":
		l.Logger.SetLevel(logrus.WarnLevel)
	case "error":
		l.Logger.SetLevel(logrus.ErrorLevel)
	case "fatal":
		l.Logger.SetLevel(logrus.FatalLevel)
	case "panic":
		l.Logger.SetLevel(logrus.PanicLevel)
	default:
		l.Logger.SetLevel(logrus.InfoLevel)
	}
}

// WithField adds a field to the logger
func (l *Logger) WithField(key string, value interface{}) *logrus.Entry {
	return l.Logger.WithField(key, value)
}

// WithFields adds multiple fields to the logger
func (l *Logger) WithFields(fields logrus.Fields) *logrus.Entry {
	return l.Logger.WithFields(fields)
} 