# Pipeline Flag System Design

## 🎯 **Overview**

Implementing a robust flag-based state management system for the voice agent pipeline to provide better control, feedback, and reliability.

## 🏗️ **System Architecture**

### **Frontend Flags:**
```typescript
enum PipelineState {
  IDLE = 'idle',
  LISTENING = 'listening',
  PROCESSING = 'processing',
  STT_ACTIVE = 'stt_active',
  LLM_ACTIVE = 'llm_active',
  TTS_ACTIVE = 'tts_active',
  COMPLETE = 'complete',
  ERROR = 'error'
}

enum ConversationState {
  STOPPED = 'stopped',
  ACTIVE = 'active',
  PAUSED = 'paused'
}
```

### **Backend Service Flags:**
```go
type ServiceState string

const (
    ServiceStateIdle     ServiceState = "idle"
    ServiceStateWaiting  ServiceState = "waiting"
    ServiceStateExecuting ServiceState = "executing"
    ServiceStateComplete ServiceState = "complete"
    ServiceStateError    ServiceState = "error"
)

type PipelineFlags struct {
    SessionID      string                 `json:"session_id"`
    ConversationID string                 `json:"conversation_id"`
    State          PipelineState          `json:"state"`
    Services       map[string]ServiceState `json:"services"`
    Timestamps     map[string]time.Time   `json:"timestamps"`
    Metadata       map[string]interface{} `json:"metadata"`
}
```

## 🔄 **Pipeline Flow with Flags**

### **1. Frontend State Management**
```typescript
interface PipelineController {
  // User Controls
  startListening(): Promise<void>
  stopConversation(): Promise<void>
  pauseConversation(): Promise<void>
  
  // State Management
  updateState(state: PipelineState): void
  updateServiceState(service: string, state: ServiceState): void
  
  // UI Updates
  updateUI(state: PipelineState): void
  showServiceStatus(service: string, state: ServiceState): void
}
```

### **2. Backend Service Coordination**
```go
type ServiceCoordinator struct {
    sessionID      string
    flags          *PipelineFlags
    logger         *logger.Logger
    websocket      *WebSocketManager
    services       map[string]ServiceInterface
}

func (sc *ServiceCoordinator) ProcessPipeline(audioData []byte) error {
    // 1. Update to STT_WAITING
    sc.updateServiceState("stt", ServiceStateWaiting)
    sc.broadcastState()
    
    // 2. Execute STT
    sc.updateServiceState("stt", ServiceStateExecuting)
    transcript, err := sc.services["stt"].Process(audioData)
    if err != nil {
        sc.updateServiceState("stt", ServiceStateError)
        return err
    }
    
    // 3. STT Complete, LLM Waiting
    sc.updateServiceState("stt", ServiceStateComplete)
    sc.updateServiceState("llm", ServiceStateWaiting)
    sc.broadcastState()
    
    // 4. Execute LLM
    sc.updateServiceState("llm", ServiceStateExecuting)
    response, err := sc.services["llm"].Process(transcript)
    if err != nil {
        sc.updateServiceState("llm", ServiceStateError)
        return err
    }
    
    // 5. LLM Complete, TTS Waiting
    sc.updateServiceState("llm", ServiceStateComplete)
    sc.updateServiceState("tts", ServiceStateWaiting)
    sc.broadcastState()
    
    // 6. Execute TTS
    sc.updateServiceState("tts", ServiceStateExecuting)
    audioResponse, err := sc.services["tts"].Process(response)
    if err != nil {
        sc.updateServiceState("tts", ServiceStateError)
        return err
    }
    
    // 7. TTS Complete, Pipeline Complete
    sc.updateServiceState("tts", ServiceStateComplete)
    sc.updatePipelineState(PipelineStateComplete)
    sc.broadcastState()
    
    return nil
}
```

## 📡 **WebSocket Message Types**

### **State Update Messages:**
```json
{
  "type": "pipeline_state_update",
  "session_id": "session_123",
  "state": "processing",
  "services": {
    "stt": "executing",
    "llm": "waiting",
    "tts": "idle"
  },
  "timestamp": "2025-07-28T04:15:00Z",
  "metadata": {
    "buffer_size": 8192,
    "audio_quality": 0.75
  }
}
```

### **Service Status Messages:**
```json
{
  "type": "service_status",
  "service": "stt",
  "state": "executing",
  "progress": 0.65,
  "message": "Transcribing audio...",
  "timestamp": "2025-07-28T04:15:00Z"
}
```

### **Conversation Control Messages:**
```json
{
  "type": "conversation_control",
  "action": "stop",
  "session_id": "session_123",
  "timestamp": "2025-07-28T04:15:00Z"
}
```

## 🎨 **Frontend UI Components**

### **1. Pipeline Status Indicator:**
```typescript
const PipelineStatusIndicator: React.FC<{state: PipelineState}> = ({state}) => {
  const getStatusColor = (state: PipelineState) => {
    switch(state) {
      case 'idle': return 'gray'
      case 'listening': return 'blue'
      case 'processing': return 'yellow'
      case 'complete': return 'green'
      case 'error': return 'red'
    }
  }
  
  return (
    <div className={`status-indicator ${getStatusColor(state)}`}>
      <span className="status-text">{state.toUpperCase()}</span>
      <div className="status-animation" />
    </div>
  )
}
```

### **2. Service Status Cards:**
```typescript
const ServiceStatusCard: React.FC<{service: string, state: ServiceState}> = ({service, state}) => {
  const getServiceIcon = (service: string) => {
    switch(service) {
      case 'stt': return '🎤'
      case 'llm': return '🧠'
      case 'tts': return '🔊'
    }
  }
  
  return (
    <div className={`service-card ${state}`}>
      <div className="service-icon">{getServiceIcon(service)}</div>
      <div className="service-name">{service.toUpperCase()}</div>
      <div className="service-state">{state}</div>
      <div className="service-progress" />
    </div>
  )
}
```

### **3. Conversation Controls:**
```typescript
const ConversationControls: React.FC<{onStart: () => void, onStop: () => void, onPause: () => void}> = ({onStart, onStop, onPause}) => {
  return (
    <div className="conversation-controls">
      <button onClick={onStart} className="btn-start">
        <span className="icon">🎤</span>
        Start Listening
      </button>
      <button onClick={onPause} className="btn-pause">
        <span className="icon">⏸️</span>
        Pause
      </button>
      <button onClick={onStop} className="btn-stop">
        <span className="icon">⏹️</span>
        Stop Conversation
      </button>
    </div>
  )
}
```

## 🔧 **Backend Implementation**

### **1. Pipeline State Manager:**
```go
type PipelineStateManager struct {
    mu            sync.RWMutex
    sessions      map[string]*PipelineFlags
    websocket     *WebSocketManager
    logger        *logger.Logger
}

func (psm *PipelineStateManager) UpdateServiceState(sessionID, service string, state ServiceState) {
    psm.mu.Lock()
    defer psm.mu.Unlock()
    
    if flags, exists := psm.sessions[sessionID]; exists {
        flags.Services[service] = state
        flags.Timestamps[fmt.Sprintf("%s_%s", service, state)] = time.Now()
        
        // Broadcast state update
        psm.broadcastStateUpdate(sessionID, flags)
    }
}

func (psm *PipelineStateManager) broadcastStateUpdate(sessionID string, flags *PipelineFlags) {
    message := PipelineStateMessage{
        Type:      "pipeline_state_update",
        SessionID: sessionID,
        State:     flags.State,
        Services:  flags.Services,
        Timestamp: time.Now(),
        Metadata:  flags.Metadata,
    }
    
    psm.websocket.BroadcastToSession(sessionID, message)
}
```

### **2. Service Interface:**
```go
type ServiceInterface interface {
    GetName() string
    GetState() ServiceState
    Process(input interface{}) (interface{}, error)
    SetState(state ServiceState)
}

type BaseService struct {
    name  string
    state ServiceState
    logger *logger.Logger
}

func (bs *BaseService) GetName() string {
    return bs.name
}

func (bs *BaseService) GetState() ServiceState {
    return bs.state
}

func (bs *BaseService) SetState(state ServiceState) {
    bs.state = state
    bs.logger.WithFields(map[string]interface{}{
        "service": bs.name,
        "state":   state,
    }).Info("Service state updated")
}
```

## 🚀 **Implementation Plan**

### **Phase 1: Backend State Management**
1. Create `PipelineStateManager` in orchestrator
2. Implement service state tracking
3. Add WebSocket state broadcasting
4. Update service interfaces

### **Phase 2: Frontend State Management**
1. Create React state management hooks
2. Implement UI components for status display
3. Add WebSocket state listeners
4. Create conversation controls

### **Phase 3: Integration & Testing**
1. Connect frontend and backend state systems
2. Test complete pipeline flow
3. Add error handling and recovery
4. Optimize performance

## 📊 **Benefits**

1. **Better User Experience:** Real-time feedback on pipeline status
2. **Improved Reliability:** Clear state management prevents race conditions
3. **Enhanced Debugging:** Detailed state tracking for troubleshooting
4. **Flexible Control:** Easy to add new states and services
5. **Visual Feedback:** Users can see exactly what's happening

## 🎯 **Next Steps**

1. Implement backend state management system
2. Create frontend state management components
3. Add WebSocket communication for real-time updates
4. Test the complete flag-based pipeline
5. Add error handling and recovery mechanisms

This flag system will make the pipeline much more robust and provide excellent user feedback throughout the entire conversation process. 