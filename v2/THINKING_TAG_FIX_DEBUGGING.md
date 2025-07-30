# Thinking Tag Fix - Debugging and Testing

## Issue Summary
The LLM was returning `<think>...</think>` tags in its responses, which were being sent to the frontend instead of clean, spoken responses.

## Root Cause Analysis
1. **Primary Path**: The orchestrator uses a Kafka-based audio processing pipeline (`processAIPipeline` function)
2. **Secondary Path**: WebSocket-based `trigger_llm` flow (coordinator-based)
3. **Issue**: The Kafka path calls `o.aiService.GenerateResponse()` directly, bypassing the coordinator's cleaning function

## Fixes Implemented

### 1. Enhanced System Prompt
- Updated ConfigMap with explicit instructions to avoid thinking tags
- Added to environment variable `SYSTEM_PROMPT`

### 2. Post-Processing in AI Service
- Added `cleanThinkingTags()` function in `orchestrator/internal/ai/service.go`
- Function removes:
  - `<think>...</think>` tags and content
  - `<reasoning>...</reasoning>` tags and content
  - `<thought>...</thought>` tags and content
  - `<analysis>...</analysis>` tags and content
  - Any remaining thinking-related tags
  - Extra whitespace and newlines

### 3. Debug Logging Added
- Added debug logs before and after cleaning to track the process
- Logs show original and cleaned response lengths

## Technical Implementation

### AI Service (`orchestrator/internal/ai/service.go`)
```go
// cleanThinkingTags removes thinking tags and cleans up the response
func (s *Service) cleanThinkingTags(response string) string {
    // Remove thinking tags and their content
    response = regexp.MustCompile(`(?i)<think>.*?</think>`).ReplaceAllString(response, "")
    response = regexp.MustCompile(`(?i)<reasoning>.*?</reasoning>`).ReplaceAllString(response, "")
    response = regexp.MustCompile(`(?i)<thought>.*?</thought>`).ReplaceAllString(response, "")
    response = regexp.MustCompile(`(?i)<analysis>.*?</analysis>`).ReplaceAllString(response, "")
    
    // Remove any remaining thinking-related tags
    response = regexp.MustCompile(`(?i)<[^>]*think[^>]*>.*?</[^>]*>`).ReplaceAllString(response, "")
    
    // Clean up extra whitespace
    response = regexp.MustCompile(`\n\s*\n`).ReplaceAllString(response, "\n")
    response = strings.TrimSpace(response)
    
    return response
}
```

### Called in GenerateResponse Function
```go
// Clean up thinking tags and extra whitespace
s.logger.WithFields(map[string]interface{}{
    "original_response": response,
    "response_length":   len(response),
}).Debug("Before cleaning thinking tags")

response = s.cleanThinkingTags(response)

s.logger.WithFields(map[string]interface{}{
    "cleaned_response": response,
    "response_length":  len(response),
}).Debug("After cleaning thinking tags")
```

## Deployment Status
- ✅ New orchestrator image built and pushed: `gcr.io/speechtotext-466820/orchestrator:latest`
- ✅ Deployment updated and restarted
- ✅ Rollout completed successfully

## Testing Instructions

### 1. Test the Fix
1. Open the frontend application
2. Start a voice conversation
3. Say "Hello, hi, how are you?" or similar greeting
4. Check if the response contains thinking tags

### 2. Monitor Logs
```bash
# Check orchestrator logs for cleaning process
kubectl logs -n voice-agent-phase5 -l app=orchestrator --tail=100 | grep -i "clean\|think\|response"

# Check for debug messages
kubectl logs -n voice-agent-phase5 -l app=orchestrator --tail=100 | grep -i "before cleaning\|after cleaning"
```

### 3. Expected Behavior
- **Before Fix**: Response contains `<think>...</think>` tags
- **After Fix**: Response is clean without thinking tags
- **Debug Logs**: Should show "Before cleaning thinking tags" and "After cleaning thinking tags" messages

### 4. Verification Commands
```bash
# Check if new image is running
kubectl get pods -n voice-agent-phase5 -l app=orchestrator -o wide

# Check deployment status
kubectl rollout status deployment/orchestrator -n voice-agent-phase5

# Check ConfigMap
kubectl get configmap llm-system-prompt -n voice-agent-phase5 -o yaml
```

## Troubleshooting

### If Thinking Tags Still Appear
1. **Check if new image is running**:
   ```bash
   kubectl describe pod -n voice-agent-phase5 -l app=orchestrator | grep Image
   ```

2. **Check debug logs**:
   ```bash
   kubectl logs -n voice-agent-phase5 -l app=orchestrator --tail=50 | grep -i "clean"
   ```

3. **Verify ConfigMap**:
   ```bash
   kubectl get configmap llm-system-prompt -n voice-agent-phase5 -o yaml
   ```

### If No Debug Logs Appear
- The request might be using a different path
- Check if the request is going through the Kafka pipeline or WebSocket pipeline
- Verify that the `GenerateResponse` function is being called

## Success Criteria
- [ ] No thinking tags in LLM responses
- [ ] Debug logs show cleaning process
- [ ] Responses are natural and conversational
- [ ] TTS receives clean text for synthesis

## Files Modified
1. `orchestrator/internal/ai/service.go` - Added `cleanThinkingTags()` function and debug logging
2. `patch-llm-quality-gke.sh` - Updated ConfigMap with improved system prompt
3. `THINKING_TAG_FIX_SUCCESS.md` - Success documentation 