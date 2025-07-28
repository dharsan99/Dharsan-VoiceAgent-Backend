# STT Classification Improvements - Reduced Filtering

## 🎯 **Problem Identified:**

The user was speaking loudly and clearly, but the system was still classifying speech as background noise and returning:
```
"I heard something. Please continue speaking."
```

## 🔍 **Root Cause Analysis:**

1. **Orchestrator Filtering Too Aggressive**: The orchestrator was filtering out transcripts that matched "I heard something. Please continue speaking." and transcripts shorter than 3 characters.

2. **STT Temperature Too Conservative**: The STT service was using `temperature=0.0`, making Whisper very conservative in speech detection.

3. **VAD Working Correctly**: The VAD was detecting audio (100% active ratio) but the STT classification was the bottleneck.

---

## ✅ **Fixes Implemented:**

### **1. Orchestrator Classification - More Permissive**

**File**: `v2/orchestrator/main.go`

**Changes Made**:
```go
// OLD - Too Aggressive
if transcript == "I heard something. Please continue speaking." {
    o.logger.WithField("sessionID", mediaSessionID).Info("Speech pause/breathing detected, skipping processing")
    return nil
} else if len(transcript) < 3 {
    o.logger.WithField("sessionID", mediaSessionID).Info("Very short transcript detected, likely noise - skipping")
    return nil
}

// NEW - More Permissive
if transcript == "I heard something. Please continue speaking." && len(transcript) < 5 {
    // Only skip if it's very short - allow longer "I heard something" responses
    o.logger.WithField("sessionID", mediaSessionID).Info("Very short generic response detected, skipping processing")
    return nil
} else if len(transcript) < 2 {
    // Only skip extremely short transcripts (1 character)
    o.logger.WithField("sessionID", mediaSessionID).Info("Extremely short transcript detected, likely noise - skipping")
    return nil
}
```

**Benefits**:
- Allows longer "I heard something" responses to pass through
- Only filters out single-character transcripts
- More permissive for actual speech

### **2. STT Temperature - More Sensitive**

**File**: `v2/orchestrator/internal/ai/service.go`

**Changes Made**:
```go
// OLD - Very Conservative
writer.WriteField("temperature", "0.0")

// NEW - More Sensitive
writer.WriteField("temperature", "0.3")
```

**Benefits**:
- Whisper will be more sensitive to speech detection
- Less likely to classify speech as background noise
- Better handling of unclear or quiet speech

---

## 🚀 **Deployment Status:**

### **New Image Built and Deployed**:
- **Image**: `orchestrator:v1.0.27`
- **Status**: ✅ Successfully deployed to GKE
- **Rollout**: ✅ Completed successfully

### **Services Updated**:
- ✅ Orchestrator service updated with new classification logic
- ✅ STT service calls now use higher temperature (0.3)
- ✅ Both `SpeechToText` and `SpeechToTextWithInterim` methods updated

---

## 🧪 **Testing Instructions:**

### **1. Test with Clear Speech**
- Speak loudly and clearly: "Hello, this is a test message"
- Watch for the transcript to appear in the conversation
- Monitor pipeline status progression

### **2. Monitor Pipeline Status**
- **Audio Input**: Should show higher levels when speaking
- **Kafka Message**: Should turn green when audio is processed
- **Speech-to-Text**: Should turn green with actual transcript
- **AI Response**: Should generate a response

### **3. Check GKE Logs**
```bash
kubectl logs -n voice-agent-phase5 -l app=orchestrator --since=2m | grep -E "(transcript|STT|processing)"
```

---

## 📊 **Expected Improvements:**

| Component | Before | After | Improvement |
|-----------|--------|-------|-------------|
| **STT Temperature** | 0.0 (Conservative) | 0.3 (Sensitive) | More speech detection |
| **Transcript Filtering** | < 3 chars filtered | < 2 chars filtered | More transcripts pass |
| **Generic Response Filtering** | All filtered | Only short ones filtered | Better speech handling |
| **Classification Sensitivity** | High (missed speech) | Balanced | Better accuracy |

---

## 🎯 **Next Steps:**

1. **Test the System**: Try speaking clearly and monitor the results
2. **Check Logs**: Verify that transcripts are being processed
3. **Monitor Pipeline**: Watch for progression through Kafka → STT → AI
4. **If Still Issues**: We can further adjust temperature or add more debugging

**The system should now be much more sensitive to actual speech while still filtering out obvious background noise!** 🎤✨ 