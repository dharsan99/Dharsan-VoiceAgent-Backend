"""
Redis Manager for Voice AI Backend v2
Handles session persistence and message bus functionality
"""

import asyncio
import json
import logging
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
import redis.asyncio as redis
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class MessageType(Enum):
    """Message types for Redis pub/sub"""
    SIGNALING = "signaling"
    SESSION_UPDATE = "session_update"
    PEER_CONNECTION = "peer_connection"
    AUDIO_FRAME = "audio_frame"
    HEARTBEAT = "heartbeat"

@dataclass
class SessionData:
    """Session data structure"""
    id: str
    created_at: str
    status: str
    peer_connections: Dict[str, Any]
    is_ai_speaking: bool
    transcript: str
    ai_response: str
    metrics: Dict[str, Any]
    last_activity: str
    expires_at: str

@dataclass
class SignalingMessage:
    """Signaling message structure"""
    type: str
    session_id: str
    data: Dict[str, Any]
    timestamp: str
    source: str

class RedisManager:
    """Redis manager for session persistence and message bus"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.is_connected = False
        self.subscribers: Dict[str, List[callable]] = {}
        
        # Configuration
        self.session_ttl = 3600  # 1 hour
        self.heartbeat_interval = 30  # 30 seconds
        self.cleanup_interval = 300  # 5 minutes
        
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            await self.redis_client.ping()
            self.is_connected = True
            
            # Initialize pub/sub
            self.pubsub = self.redis_client.pubsub()
            
            logger.info(f"Connected to Redis at {self.redis_url}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.is_connected = False
            raise
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.pubsub:
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()
        self.is_connected = False
        logger.info("Disconnected from Redis")
    
    async def health_check(self) -> bool:
        """Check Redis connection health"""
        try:
            if not self.redis_client:
                return False
            await self.redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    # Session Management
    async def save_session(self, session_data: SessionData) -> bool:
        """Save session data to Redis"""
        try:
            if not self.is_connected:
                return False
            
            key = f"session:{session_data.id}"
            data = asdict(session_data)
            
            # Set session data with TTL
            await self.redis_client.hset(key, mapping=data)
            await self.redis_client.expire(key, self.session_ttl)
            
            # Update session index
            await self.redis_client.sadd("sessions:active", session_data.id)
            await self.redis_client.zadd("sessions:timeline", {session_data.id: datetime.now().timestamp()})
            
            logger.debug(f"Saved session {session_data.id} to Redis")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save session {session_data.id}: {e}")
            return False
    
    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session data from Redis"""
        try:
            if not self.is_connected:
                return None
            
            key = f"session:{session_id}"
            data = await self.redis_client.hgetall(key)
            
            if not data:
                return None
            
            # Convert string values back to appropriate types
            data['peer_connections'] = json.loads(data.get('peer_connections', '{}'))
            data['metrics'] = json.loads(data.get('metrics', '{}'))
            
            return SessionData(**data)
            
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None
    
    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session data in Redis"""
        try:
            if not self.is_connected:
                return False
            
            key = f"session:{session_id}"
            
            # Update specific fields
            for field, value in updates.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                await self.redis_client.hset(key, field, value)
            
            # Update last activity
            await self.redis_client.hset(key, "last_activity", datetime.now().isoformat())
            
            # Extend TTL
            await self.redis_client.expire(key, self.session_ttl)
            
            logger.debug(f"Updated session {session_id} in Redis")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update session {session_id}: {e}")
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session from Redis"""
        try:
            if not self.is_connected:
                return False
            
            key = f"session:{session_id}"
            
            # Remove session data
            await self.redis_client.delete(key)
            
            # Remove from indexes
            await self.redis_client.srem("sessions:active", session_id)
            await self.redis_client.zrem("sessions:timeline", session_id)
            
            logger.info(f"Deleted session {session_id} from Redis")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    async def list_sessions(self) -> List[str]:
        """List all active session IDs"""
        try:
            if not self.is_connected:
                return []
            
            session_ids = await self.redis_client.smembers("sessions:active")
            return list(session_ids)
            
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []
    
    async def get_session_count(self) -> int:
        """Get count of active sessions"""
        try:
            if not self.is_connected:
                return 0
            
            return await self.redis_client.scard("sessions:active")
            
        except Exception as e:
            logger.error(f"Failed to get session count: {e}")
            return 0
    
    # Message Bus (Pub/Sub)
    async def publish_message(self, channel: str, message: SignalingMessage) -> bool:
        """Publish message to Redis channel"""
        try:
            if not self.is_connected:
                return False
            
            message_data = asdict(message)
            await self.redis_client.publish(channel, json.dumps(message_data))
            
            logger.debug(f"Published message to channel {channel}: {message.type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish message to {channel}: {e}")
            return False
    
    async def subscribe_to_channel(self, channel: str, callback: callable):
        """Subscribe to Redis channel"""
        try:
            if not self.is_connected or not self.pubsub:
                return False
            
            await self.pubsub.subscribe(channel)
            
            if channel not in self.subscribers:
                self.subscribers[channel] = []
            self.subscribers[channel].append(callback)
            
            logger.info(f"Subscribed to channel {channel}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to subscribe to {channel}: {e}")
            return False
    
    async def unsubscribe_from_channel(self, channel: str, callback: callable = None):
        """Unsubscribe from Redis channel"""
        try:
            if not self.is_connected or not self.pubsub:
                return False
            
            if callback:
                if channel in self.subscribers:
                    self.subscribers[channel] = [cb for cb in self.subscribers[channel] if cb != callback]
            else:
                await self.pubsub.unsubscribe(channel)
                if channel in self.subscribers:
                    del self.subscribers[channel]
            
            logger.info(f"Unsubscribed from channel {channel}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unsubscribe from {channel}: {e}")
            return False
    
    async def listen_for_messages(self):
        """Listen for messages from subscribed channels"""
        try:
            if not self.is_connected or not self.pubsub:
                return
            
            async for message in self.pubsub.listen():
                if message['type'] == 'message':
                    channel = message['channel']
                    data = json.loads(message['data'])
                    
                    # Call registered callbacks
                    if channel in self.subscribers:
                        for callback in self.subscribers[channel]:
                            try:
                                await callback(data)
                            except Exception as e:
                                logger.error(f"Error in message callback: {e}")
                                
        except Exception as e:
            logger.error(f"Error listening for messages: {e}")
    
    # Cleanup and Maintenance
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        try:
            if not self.is_connected:
                return
            
            # Get sessions that haven't been active recently
            cutoff_time = datetime.now() - timedelta(hours=1)
            cutoff_timestamp = cutoff_time.timestamp()
            
            expired_sessions = await self.redis_client.zrangebyscore(
                "sessions:timeline", 0, cutoff_timestamp
            )
            
            for session_id in expired_sessions:
                await self.delete_session(session_id)
                logger.info(f"Cleaned up expired session {session_id}")
                
        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")
    
    async def start_maintenance_tasks(self):
        """Start background maintenance tasks"""
        async def maintenance_loop():
            while self.is_connected:
                try:
                    await self.cleanup_expired_sessions()
                    await asyncio.sleep(self.cleanup_interval)
                except Exception as e:
                    logger.error(f"Error in maintenance loop: {e}")
                    await asyncio.sleep(60)  # Wait before retrying
        
        asyncio.create_task(maintenance_loop())
        logger.info("Started Redis maintenance tasks")
    
    # Metrics and Statistics
    async def get_redis_stats(self) -> Dict[str, Any]:
        """Get Redis statistics"""
        try:
            if not self.is_connected:
                return {}
            
            info = await self.redis_client.info()
            
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0),
                "session_count": await self.get_session_count(),
                "is_connected": self.is_connected
            }
            
        except Exception as e:
            logger.error(f"Failed to get Redis stats: {e}")
            return {"is_connected": False, "error": str(e)}

# Global Redis manager instance
redis_manager = RedisManager() 