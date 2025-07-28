package webrtc

import (
	"voice-agent-media-server/pkg/config"

	"github.com/pion/webrtc/v3"
)

// Config holds WebRTC configuration
type Config struct {
	webrtc.Configuration
	AudioCodec string
	SampleRate int
}

// NewConfig creates a new WebRTC configuration
func NewConfig(cfg *config.Config) *Config {
	// Create ICE servers configuration
	var iceServers []webrtc.ICEServer

	// Add STUN servers
	for _, stunServer := range cfg.WebRTC.STUNServers {
		iceServers = append(iceServers, webrtc.ICEServer{
			URLs: []string{stunServer},
		})
	}

	// Add TURN servers if configured
	for _, turnServer := range cfg.WebRTC.ICEServers {
		iceServers = append(iceServers, webrtc.ICEServer{
			URLs:       []string{turnServer},
			Username:   cfg.WebRTC.TURNUsername,
			Credential: cfg.WebRTC.TURNCredential,
		})
	}

	return &Config{
		Configuration: webrtc.Configuration{
			ICEServers: iceServers,
			// Enhanced ICE configuration for better connectivity
			ICECandidatePoolSize: 20,                           // Increased for more candidates
			ICETransportPolicy:   webrtc.ICETransportPolicyAll, // Allow all candidate types
			BundlePolicy:         webrtc.BundlePolicyMaxBundle,
			RTCPMuxPolicy:        webrtc.RTCPMuxPolicyRequire,
			// Additional settings for better connectivity
			SDPSemantics: webrtc.SDPSemanticsUnifiedPlan,
		},
		AudioCodec: cfg.WebRTC.AudioCodec,
		SampleRate: cfg.WebRTC.SampleRate,
	}
}

// CreatePeerConnection creates a new WebRTC peer connection
func (c *Config) CreatePeerConnection() (*webrtc.PeerConnection, error) {
	// Create media engine
	mediaEngine := webrtc.MediaEngine{}

	// Register audio codecs
	if err := mediaEngine.RegisterCodec(webrtc.RTPCodecParameters{
		RTPCodecCapability: webrtc.RTPCodecCapability{
			MimeType:    webrtc.MimeTypeOpus,
			ClockRate:   48000,
			Channels:    2,
			SDPFmtpLine: "minptime=10;useinbandfec=1",
		},
		PayloadType: 111,
	}, webrtc.RTPCodecTypeAudio); err != nil {
		return nil, err
	}

	// Create API
	api := webrtc.NewAPI(webrtc.WithMediaEngine(&mediaEngine))

	// Create peer connection
	peerConnection, err := api.NewPeerConnection(c.Configuration)
	if err != nil {
		return nil, err
	}

	return peerConnection, nil
}
