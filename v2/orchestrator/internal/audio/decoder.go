package audio

import (
	"fmt"
	"unsafe"
	"voice-agent-orchestrator/internal/logger"
)

// Decoder handles audio format conversion
type Decoder struct {
	logger *logger.Logger
}

// NewDecoder creates a new audio decoder
func NewDecoder(logger *logger.Logger) *Decoder {
	return &Decoder{
		logger: logger,
	}
}

// DecodeOpusToPCMSimple handles audio data (now expects raw PCM)
func (d *Decoder) DecodeOpusToPCMSimple(audioData []byte) ([]byte, error) {
	if len(audioData) == 0 {
		return nil, fmt.Errorf("empty audio data")
	}

	// For now, assume the data is already in PCM format (16-bit, 16kHz, mono)
	// The frontend is now sending raw PCM data directly
	d.logger.WithFields(map[string]interface{}{
		"inputSize":  len(audioData),
		"outputSize": len(audioData),
	}).Debug("Processing raw PCM audio data")

	return audioData, nil
}

// ConvertToMono16kHz converts any audio data to mono 16kHz PCM
func (d *Decoder) ConvertToMono16kHz(audioData []byte) []byte {
	// For raw PCM data, just return as-is
	return audioData
}

// PCMToWAV converts PCM data to WAV format
func (d *Decoder) PCMToWAV(pcmData []byte, sampleRate int, channels int, bitsPerSample int) ([]byte, error) {
	// WAV file header structure
	type WAVHeader struct {
		ChunkID       [4]byte // "RIFF"
		ChunkSize     uint32  // File size - 8
		Format        [4]byte // "WAVE"
		Subchunk1ID   [4]byte // "fmt "
		Subchunk1Size uint32  // 16 for PCM
		AudioFormat   uint16  // 1 for PCM
		NumChannels   uint16  // 1 for mono, 2 for stereo
		SampleRate    uint32  // 16000 for 16kHz
		ByteRate      uint32  // SampleRate * NumChannels * BitsPerSample/8
		BlockAlign    uint16  // NumChannels * BitsPerSample/8
		BitsPerSample uint16  // 16 for 16-bit
		Subchunk2ID   [4]byte // "data"
		Subchunk2Size uint32  // Size of audio data
	}

	// Calculate sizes
	dataSize := uint32(len(pcmData))
	fileSize := dataSize + 36 // 44 bytes header - 8

	// Create header
	header := WAVHeader{
		ChunkID:       [4]byte{'R', 'I', 'F', 'F'},
		ChunkSize:     fileSize,
		Format:        [4]byte{'W', 'A', 'V', 'E'},
		Subchunk1ID:   [4]byte{'f', 'm', 't', ' '},
		Subchunk1Size: 16,
		AudioFormat:   1, // PCM
		NumChannels:   uint16(channels),
		SampleRate:    uint32(sampleRate),
		BitsPerSample: uint16(bitsPerSample),
		Subchunk2ID:   [4]byte{'d', 'a', 't', 'a'},
		Subchunk2Size: dataSize,
	}

	// Calculate derived fields
	header.ByteRate = header.SampleRate * uint32(header.NumChannels) * uint32(header.BitsPerSample) / 8
	header.BlockAlign = header.NumChannels * header.BitsPerSample / 8

	// Create WAV file
	wavData := make([]byte, 44+len(pcmData))

	// Write header
	headerBytes := (*[44]byte)(unsafe.Pointer(&header))
	copy(wavData[:44], headerBytes[:])

	// Write audio data
	copy(wavData[44:], pcmData)

	d.logger.WithFields(map[string]interface{}{
		"pcmSize":       len(pcmData),
		"wavSize":       len(wavData),
		"sampleRate":    sampleRate,
		"channels":      channels,
		"bitsPerSample": bitsPerSample,
	}).Debug("Converted PCM to WAV")

	return wavData, nil
}
