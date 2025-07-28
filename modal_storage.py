"""
Modal Cloud Storage Integration for Voice Agent
Provides cloud-based storage for metrics, conversation history, and asynchronous processing
"""

import modal
import json
import time
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Modal app
app = modal.App("voice-agent-cloud-storage")

# Cloud Storage Resources
metrics_volume = modal.Volume.from_name("voice-agent-metrics", create_if_missing=True)
conversation_store = modal.Dict.from_name("voice-conversations", create_if_missing=True)
voice_queue = modal.Queue.from_name("voice-processing", create_if_missing=True)
session_store = modal.Dict.from_name("voice-sessions", create_if_missing=True)

# Storage paths
METRICS_PATH = "/metrics"
VOLUME_MOUNT_PATH = "/vol"

# ==================== METRICS STORAGE (Volumes) ====================

@app.function(volumes={METRICS_PATH: metrics_volume})
def store_session_metrics(session_data: Dict[str, Any]) -> str:
    """Store session metrics to cloud volume"""
    try:
        session_id = session_data.get("session_id")
        if not session_id:
            raise ValueError("Session ID is required")
        
        # Create timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics_file = f"{METRICS_PATH}/session_{session_id}_{timestamp}.json"
        
        # Store metrics with metadata
        metrics_data = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "data": session_data,
            "version": "1.0"
        }
        
        with open(metrics_file, "w") as f:
            json.dump(metrics_data, f, indent=2)
        
        # Commit changes to volume
        metrics_volume.commit()
        
        logger.info(f"Stored metrics for session {session_id} to cloud volume")
        return f"Stored metrics for session {session_id}"
        
    except Exception as e:
        logger.error(f"Error storing session metrics: {e}")
        raise

@app.function(volumes={METRICS_PATH: metrics_volume})
def get_session_metrics(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve session metrics from cloud volume"""
    try:
        import os
        import glob
        
        # Search for session files
        pattern = f"{METRICS_PATH}/session_{session_id}_*.json"
        session_files = glob.glob(pattern)
        
        if not session_files:
            logger.warning(f"No metrics found for session {session_id}")
            return None
        
        # Get the most recent file
        latest_file = max(session_files, key=os.path.getctime)
        
        with open(latest_file, "r") as f:
            metrics_data = json.load(f)
        
        logger.info(f"Retrieved metrics for session {session_id} from cloud volume")
        return metrics_data
        
    except Exception as e:
        logger.error(f"Error retrieving session metrics: {e}")
        return None

@app.function(volumes={METRICS_PATH: metrics_volume})
def list_all_metrics() -> List[str]:
    """List all stored metrics files"""
    try:
        import os
        import glob
        
        pattern = f"{METRICS_PATH}/session_*.json"
        metric_files = glob.glob(pattern)
        
        # Extract session IDs from filenames
        session_ids = []
        for file_path in metric_files:
            filename = os.path.basename(file_path)
            if filename.startswith("session_") and filename.endswith(".json"):
                session_id = filename.split("_")[1]
                if session_id not in session_ids:
                    session_ids.append(session_id)
        
        logger.info(f"Found {len(session_ids)} unique sessions in cloud volume")
        return session_ids
        
    except Exception as e:
        logger.error(f"Error listing metrics: {e}")
        return []

# ==================== CONVERSATION STORAGE (Dicts) ====================

@app.function()
def store_conversation(session_id: str, conversation_data: Dict[str, Any]) -> str:
    """Store conversation in distributed dict"""
    try:
        # Generate unique conversation ID
        conversation_id = f"conv_{int(time.time() * 1000)}_{session_id}"
        
        # Prepare conversation data
        conversation_entry = {
            "conversation_id": conversation_id,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "data": conversation_data,
            "version": "1.0"
        }
        
        # Store in conversation dict
        if session_id not in conversation_store:
            conversation_store[session_id] = []
        
        conversation_store[session_id].append(conversation_entry)
        
        logger.info(f"Stored conversation {conversation_id} for session {session_id}")
        return conversation_id
        
    except Exception as e:
        logger.error(f"Error storing conversation: {e}")
        raise

@app.function()
def get_conversation_history(session_id: str) -> List[Dict[str, Any]]:
    """Retrieve conversation history for a session"""
    try:
        conversations = conversation_store.get(session_id, [])
        logger.info(f"Retrieved {len(conversations)} conversations for session {session_id}")
        return conversations
        
    except Exception as e:
        logger.error(f"Error retrieving conversation history: {e}")
        return []

@app.function()
def get_all_conversations() -> Dict[str, List[Dict[str, Any]]]:
    """Get all conversations from all sessions"""
    try:
        all_conversations = dict(conversation_store)
        total_conversations = sum(len(conv_list) for conv_list in all_conversations.values())
        logger.info(f"Retrieved {total_conversations} total conversations from {len(all_conversations)} sessions")
        return all_conversations
        
    except Exception as e:
        logger.error(f"Error retrieving all conversations: {e}")
        return {}

# ==================== SESSION STORAGE (Dicts) ====================

@app.function()
def store_session(session_data: Dict[str, Any]) -> str:
    """Store session information in distributed dict"""
    try:
        session_id = session_data.get("session_id")
        if not session_id:
            raise ValueError("Session ID is required")
        
        # Add metadata
        session_entry = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "data": session_data,
            "status": "active",
            "version": "1.0"
        }
        
        session_store[session_id] = session_entry
        
        logger.info(f"Stored session {session_id} in cloud dict")
        return session_id
        
    except Exception as e:
        logger.error(f"Error storing session: {e}")
        raise

@app.function()
def update_session(session_id: str, updates: Dict[str, Any]) -> bool:
    """Update session information"""
    try:
        if session_id not in session_store:
            logger.warning(f"Session {session_id} not found for update")
            return False
        
        session_entry = session_store[session_id]
        session_entry["data"].update(updates)
        session_entry["updated_at"] = datetime.now().isoformat()
        
        session_store[session_id] = session_entry
        
        logger.info(f"Updated session {session_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating session: {e}")
        return False

@app.function()
def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve session information"""
    try:
        session_data = session_store.get(session_id)
        if session_data:
            logger.info(f"Retrieved session {session_id}")
        else:
            logger.warning(f"Session {session_id} not found")
        return session_data
        
    except Exception as e:
        logger.error(f"Error retrieving session: {e}")
        return None

@app.function()
def list_all_sessions() -> List[str]:
    """List all session IDs"""
    try:
        session_ids = list(session_store.keys())
        logger.info(f"Found {len(session_ids)} sessions in cloud storage")
        return session_ids
        
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return []

# ==================== ASYNCHRONOUS PROCESSING (Queues) ====================

@app.function()
def queue_voice_processing(processing_data: Dict[str, Any]) -> str:
    """Queue voice processing task"""
    try:
        # Add metadata to processing data
        task_data = {
            "task_id": f"task_{int(time.time() * 1000)}",
            "timestamp": datetime.now().isoformat(),
            "data": processing_data,
            "status": "queued",
            "version": "1.0"
        }
        
        # Add to processing queue
        voice_queue.put(task_data)
        
        logger.info(f"Queued voice processing task {task_data['task_id']}")
        return task_data["task_id"]
        
    except Exception as e:
        logger.error(f"Error queuing voice processing: {e}")
        raise

@app.function()
def get_voice_processing_result(timeout: int = 30) -> Optional[Dict[str, Any]]:
    """Get next voice processing result from queue"""
    try:
        import queue
        
        result = voice_queue.get(timeout=timeout)
        logger.info(f"Retrieved voice processing result: {result.get('task_id', 'unknown')}")
        return result
        
    except queue.Empty:
        logger.warning("No voice processing results available")
        return None
    except Exception as e:
        logger.error(f"Error getting voice processing result: {e}")
        return None

@app.function()
def get_queue_status() -> Dict[str, Any]:
    """Get queue status information"""
    try:
        # Note: Modal Queue doesn't expose size directly, so we'll estimate
        # based on recent activity
        queue_info = {
            "queue_name": "voice-processing",
            "estimated_items": "dynamic",  # Modal handles this internally
            "status": "active",
            "last_updated": datetime.now().isoformat()
        }
        
        return queue_info
        
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        return {"error": str(e)}

# ==================== UTILITY FUNCTIONS ====================

@app.function()
def get_storage_stats() -> Dict[str, Any]:
    """Get comprehensive storage statistics"""
    try:
        # Get session count
        session_count = len(session_store)
        
        # Get conversation count
        total_conversations = sum(len(conv_list) for conv_list in conversation_store.values())
        
        # Get metrics count (approximate)
        metrics_count = len(list_all_metrics.remote())
        
        stats = {
            "sessions": session_count,
            "conversations": total_conversations,
            "metrics_files": metrics_count,
            "storage_type": "modal_cloud",
            "last_updated": datetime.now().isoformat(),
            "version": "1.0"
        }
        
        logger.info(f"Storage stats: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Error getting storage stats: {e}")
        return {"error": str(e)}

@app.function()
def clear_storage(storage_type: str = "all") -> bool:
    """Clear storage data (use with caution!)"""
    try:
        if storage_type in ["all", "conversations"]:
            conversation_store.clear()
            logger.info("Cleared conversation storage")
        
        if storage_type in ["all", "sessions"]:
            session_store.clear()
            logger.info("Cleared session storage")
        
        if storage_type in ["all", "queue"]:
            voice_queue.clear()
            logger.info("Cleared voice processing queue")
        
        logger.warning(f"Cleared {storage_type} storage data")
        return True
        
    except Exception as e:
        logger.error(f"Error clearing storage: {e}")
        return False

# ==================== UTILITY FUNCTIONS (Non-Modal) ====================

def generate_session_id() -> str:
    """Generate a unique session ID with enhanced uniqueness"""
    timestamp = int(time.time() * 1000)
    random_part = ''.join([chr(ord('a') + int(time.time() * 1000) % 26) for _ in range(8)])
    return f"session_{timestamp}_{random_part}"

def generate_conversation_id() -> str:
    """Generate a unique conversation ID"""
    timestamp = int(time.time() * 1000)
    random_part = ''.join([chr(ord('a') + int(time.time() * 1000) % 26) for _ in range(8)])
    return f"conv_{timestamp}_{random_part}"

def validate_data_integrity() -> Dict[str, Any]:
    """Validate data integrity across all storage types"""
    try:
        # Check sessions
        session_count = len(session_store)
        
        # Check conversations
        conversation_count = sum(len(conv_list) for conv_list in conversation_store.values())
        
        # Check for orphaned conversations
        orphaned_conversations = 0
        for session_id, conv_list in conversation_store.items():
            if session_id not in session_store:
                orphaned_conversations += len(conv_list)
        
        integrity_report = {
            "sessions_valid": session_count > 0,
            "conversations_valid": conversation_count >= 0,
            "orphaned_conversations": orphaned_conversations,
            "overall_integrity": orphaned_conversations == 0,
            "timestamp": datetime.now().isoformat()
        }
        
        return integrity_report
        
    except Exception as e:
        return {
            "error": str(e),
            "overall_integrity": False,
            "timestamp": datetime.now().isoformat()
        }

# Export the app for deployment
if __name__ == "__main__":
    app.serve() 