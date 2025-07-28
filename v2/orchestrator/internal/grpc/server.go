package grpc

import (
	"context"
	"fmt"
	"net"
	"time"

	"voice-agent-orchestrator/internal/logger"
	"voice-agent-orchestrator/internal/pipeline"
	"voice-agent-orchestrator/internal/session"

	"google.golang.org/grpc"
	"google.golang.org/grpc/keepalive"
	"google.golang.org/grpc/reflection"

	pb "voice-agent-orchestrator/proto"
)

// Server represents the gRPC server
type Server struct {
	pb.UnimplementedVoiceAgentServiceServer
	grpcServer    *grpc.Server
	logger        *logger.Logger
	pipelineCoord pipeline.Coordinator
	sessionMgr    *session.Manager
	port          int
}

// NewServer creates a new gRPC server instance
func NewServer(logger *logger.Logger, pipelineCoord pipeline.Coordinator, sessionMgr *session.Manager, port int) *Server {
	// Configure gRPC server with keepalive
	grpcServer := grpc.NewServer(
		grpc.KeepaliveParams(keepalive.ServerParameters{
			MaxConnectionIdle: 30 * time.Second,
			MaxConnectionAge:  60 * time.Second,
			Time:              10 * time.Second,
			Timeout:           5 * time.Second,
		}),
		grpc.KeepaliveEnforcementPolicy(keepalive.EnforcementPolicy{
			MinTime:             5 * time.Second,
			PermitWithoutStream: true,
		}),
	)

	server := &Server{
		grpcServer:    grpcServer,
		logger:        logger,
		pipelineCoord: pipelineCoord,
		sessionMgr:    sessionMgr,
		port:          port,
	}

	// Register the service
	pb.RegisterVoiceAgentServiceServer(grpcServer, server)

	// Enable reflection for debugging
	reflection.Register(grpcServer)

	return server
}

// Start starts the gRPC server
func (s *Server) Start() error {
	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", s.port))
	if err != nil {
		return fmt.Errorf("failed to listen: %v", err)
	}

	s.logger.WithField("port", s.port).Info("Starting gRPC server")

	if err := s.grpcServer.Serve(lis); err != nil {
		return fmt.Errorf("failed to serve: %v", err)
	}

	return nil
}

// Stop stops the gRPC server
func (s *Server) Stop() {
	s.logger.Info("Stopping gRPC server")
	s.grpcServer.GracefulStop()
}

// StreamAudio implements the bidirectional streaming RPC for audio processing
func (s *Server) StreamAudio(stream pb.VoiceAgentService_StreamAudioServer) error {
	s.logger.Info("New gRPC audio stream started")

	// Create a new session for this stream
	sessionID := s.sessionMgr.GenerateSessionID()
	_ = s.sessionMgr.CreateSession(sessionID)
	defer s.sessionMgr.RemoveSession(sessionID)

	s.logger.WithField("sessionID", sessionID).Info("Created session for gRPC stream")

	// Start the pipeline for this session
	if err := s.pipelineCoord.StartSession(sessionID); err != nil {
		s.logger.WithField("error", err).Error("Failed to start pipeline session")
		return err
	}
	defer s.pipelineCoord.StopSession(sessionID)

	// Channel for receiving audio chunks from client
	audioChunks := make(chan *pb.AudioChunk, 100)
	// Channel for sending responses to client
	responses := make(chan *pb.AudioResponse, 100)

	// Start goroutine to receive audio chunks from client
	go func() {
		defer close(audioChunks)
		for {
			chunk, err := stream.Recv()
			if err != nil {
				s.logger.WithField("error", err).Info("Client stream closed")
				return
			}

			// Update session with received audio
			// session.UpdateLastActivity() // TODO: Add this method to AudioSession

			// Send audio chunk to pipeline
			audioChunks <- chunk
		}
	}()

	// Start goroutine to send responses to client
	go func() {
		for response := range responses {
			if err := stream.Send(response); err != nil {
				s.logger.WithField("error", err).Error("Failed to send response to client")
				return
			}
		}
	}()

	// Process audio chunks and generate responses
	for chunk := range audioChunks {
		// Process the audio chunk through the pipeline
		response, err := s.processAudioChunk(chunk, sessionID)
		if err != nil {
			s.logger.WithField("error", err).Error("Failed to process audio chunk")
			continue
		}

		// Send response to client
		select {
		case responses <- response:
		default:
			s.logger.Warn("Response channel full, dropping response")
		}
	}

	s.logger.WithField("sessionID", sessionID).Info("gRPC audio stream ended")
	return nil
}

// SendControlMessage implements the control message RPC
func (s *Server) SendControlMessage(ctx context.Context, msg *pb.ControlMessage) (*pb.ControlResponse, error) {
	s.logger.WithField("sessionID", msg.SessionId).WithField("controlType", msg.ControlType).Info("Received control message")

	response := &pb.ControlResponse{
		SessionId: msg.SessionId,
		Timestamp: time.Now().Unix(),
	}

	switch msg.ControlType {
	case pb.ControlType_CONTROL_TYPE_START_LISTENING:
		if err := s.pipelineCoord.StartSession(msg.SessionId); err != nil {
			response.Success = false
			response.Message = fmt.Sprintf("Failed to start listening: %v", err)
		} else {
			response.Success = true
			response.Message = "Started listening"
		}

	case pb.ControlType_CONTROL_TYPE_STOP_LISTENING:
		if err := s.pipelineCoord.StopSession(msg.SessionId); err != nil {
			response.Success = false
			response.Message = fmt.Sprintf("Failed to stop listening: %v", err)
		} else {
			response.Success = true
			response.Message = "Stopped listening"
		}

	case pb.ControlType_CONTROL_TYPE_TRIGGER_LLM:
		if err := s.pipelineCoord.TriggerLLM(msg.SessionId); err != nil {
			response.Success = false
			response.Message = fmt.Sprintf("Failed to trigger LLM: %v", err)
		} else {
			response.Success = true
			response.Message = "LLM triggered"
		}

	case pb.ControlType_CONTROL_TYPE_RESET_SESSION:
		if err := s.pipelineCoord.ResetSession(msg.SessionId); err != nil {
			response.Success = false
			response.Message = fmt.Sprintf("Failed to reset session: %v", err)
		} else {
			response.Success = true
			response.Message = "Session reset"
		}

	case pb.ControlType_CONTROL_TYPE_PAUSE_PIPELINE:
		if err := s.pipelineCoord.PauseSession(msg.SessionId); err != nil {
			response.Success = false
			response.Message = fmt.Sprintf("Failed to pause pipeline: %v", err)
		} else {
			response.Success = true
			response.Message = "Pipeline paused"
		}

	case pb.ControlType_CONTROL_TYPE_RESUME_PIPELINE:
		if err := s.pipelineCoord.ResumeSession(msg.SessionId); err != nil {
			response.Success = false
			response.Message = fmt.Sprintf("Failed to resume pipeline: %v", err)
		} else {
			response.Success = true
			response.Message = "Pipeline resumed"
		}

	default:
		response.Success = false
		response.Message = "Unknown control type"
	}

	return response, nil
}

// HealthCheck implements the health check RPC
func (s *Server) HealthCheck(ctx context.Context, req *pb.HealthRequest) (*pb.HealthResponse, error) {
	s.logger.WithField("service", req.ServiceName).Debug("Health check request")

	// Check pipeline health
	pipelineHealthy := s.pipelineCoord.IsHealthy()
	sessionCount := s.sessionMgr.GetActiveSessionCount()

	response := &pb.HealthResponse{
		ServiceName: req.ServiceName,
		Timestamp:   time.Now().Unix(),
		Metadata: map[string]string{
			"pipeline_healthy": fmt.Sprintf("%t", pipelineHealthy),
			"active_sessions":  fmt.Sprintf("%d", sessionCount),
			"version":          "2.0.0",
			"phase":            "4",
		},
	}

	if pipelineHealthy {
		response.Healthy = true
		response.Status = "healthy"
	} else {
		response.Healthy = false
		response.Status = "unhealthy"
	}

	return response, nil
}

// processAudioChunk processes an audio chunk through the pipeline
func (s *Server) processAudioChunk(chunk *pb.AudioChunk, sessionID string) (*pb.AudioResponse, error) {
	// Create response
	response := &pb.AudioResponse{
		SessionId: sessionID,
		Timestamp: time.Now().Unix(),
	}

	// Process audio through pipeline
	// This is where you would integrate with your existing pipeline logic
	// For now, we'll create a simple echo response

	if chunk.Metadata != nil && chunk.Metadata.VoiceActivity {
		// Simulate processing when voice activity is detected
		response.ResponseType = pb.ResponseType_RESPONSE_TYPE_INTERIM_TRANSCRIPT
		response.Transcript = "Processing audio..."
	} else {
		// No voice activity, just acknowledge
		response.ResponseType = pb.ResponseType_RESPONSE_TYPE_UNSPECIFIED
	}

	return response, nil
}
