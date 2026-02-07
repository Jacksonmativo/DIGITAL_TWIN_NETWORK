#!/usr/bin/env python3
"""
Digital Twin Network - MQTT Client Wrapper
Robust MQTT client with reconnection, queuing, and callback management
"""

import os
import sys
import json
import time
import logging
import threading
from typing import Dict, List, Callable, Optional, Any
from queue import Queue, Empty
from dataclasses import dataclass
from enum import Enum

import paho.mqtt.client as mqtt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Enumerations
# ============================================================================

class QoS(Enum):
    """MQTT Quality of Service levels"""
    AT_MOST_ONCE = 0      # Fire and forget
    AT_LEAST_ONCE = 1     # Acknowledged delivery
    EXACTLY_ONCE = 2      # Guaranteed delivery


class ConnectionState(Enum):
    """Connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class MQTTConfig:
    """MQTT client configuration"""
    broker_host: str = "localhost"
    broker_port: int = 1883
    client_id: str = ""
    username: Optional[str] = None
    password: Optional[str] = None
    keepalive: int = 60
    clean_session: bool = True
    protocol: int = mqtt.MQTTv311
    transport: str = "tcp"  # tcp or websockets

    # TLS/SSL settings
    use_tls: bool = False
    ca_certs: Optional[str] = None
    certfile: Optional[str] = None
    keyfile: Optional[str] = None

    # Reconnection settings
    auto_reconnect: bool = True
    reconnect_delay: int = 5
    max_reconnect_delay: int = 120

    # Message settings
    queue_size: int = 1000
    message_timeout: int = 30


@dataclass
class Subscription:
    """Topic subscription information"""
    topic: str
    qos: int
    callback: Optional[Callable] = None


@dataclass
class QueuedMessage:
    """Message queued for publishing"""
    topic: str
    payload: Any
    qos: int
    retain: bool
    timestamp: float


# ============================================================================
# MQTT Client Wrapper
# ============================================================================

class MQTTClientWrapper:
    """
    Wrapper for Paho MQTT client with enhanced features:
    - Automatic reconnection
    - Message queuing during disconnection
    - Topic-based callback routing
    - Connection state management
    - Thread-safe operations
    """

    def __init__(self, config: MQTTConfig):
        """Initialize MQTT client wrapper"""
        self.config = config
        self.client_id = config.client_id or f"mqtt_client_{int(time.time())}"

        # Create Paho MQTT client
        self.client = mqtt.Client(
            client_id=self.client_id,
            clean_session=config.clean_session,
            protocol=config.protocol,
            transport=config.transport
        )

        # State tracking
        self.state = ConnectionState.DISCONNECTED
        self.connected = False
        self._lock = threading.Lock()

        # Subscriptions
        self.subscriptions: Dict[str, Subscription] = {}
        self.wildcard_callbacks: List[tuple] = []  # (pattern, callback)

        # Message queue for offline publishing
        self.message_queue: Queue = Queue(maxsize=config.queue_size)
        self.queue_thread: Optional[threading.Thread] = None
        self.queue_running = False

        # Statistics
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'messages_queued': 0,
            'reconnect_count': 0,
            'errors': 0
        }

        # Setup callbacks
        self._setup_callbacks()

        # Configure authentication
        if config.username and config.password:
            self.client.username_pw_set(config.username, config.password)

        # Configure TLS/SSL
        if config.use_tls:
            self._configure_tls()

        logger.info(f"MQTT Client initialized: {self.client_id}")

    def _setup_callbacks(self):
        """Setup Paho MQTT callbacks"""
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish
        self.client.on_subscribe = self._on_subscribe
        self.client.on_unsubscribe = self._on_unsubscribe
        self.client.on_log = self._on_log

    def _configure_tls(self):
        """Configure TLS/SSL encryption"""
        try:
            import ssl
            self.client.tls_set(
                ca_certs=self.config.ca_certs,
                certfile=self.config.certfile,
                keyfile=self.config.keyfile,
                tls_version=ssl.PROTOCOL_TLSv1_2
            )
            logger.info("TLS/SSL configured")
        except Exception as e:
            logger.error(f"Failed to configure TLS: {e}")
            raise

    # ========================================================================
    # Connection Management
    # ========================================================================

    def connect(self) -> bool:
        """
        Connect to MQTT broker
        Returns True if successful, False otherwise
        """
        try:
            with self._lock:
                if self.connected:
                    logger.warning("Already connected")
                    return True

                self.state = ConnectionState.CONNECTING
                logger.info(f"Connecting to {self.config.broker_host}:{self.config.broker_port}")

            # Connect to broker
            self.client.connect(
                self.config.broker_host,
                self.config.broker_port,
                self.config.keepalive
            )

            # Start network loop
            self.client.loop_start()

            # Wait for connection (with timeout)
            timeout = 10
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            if self.connected:
                logger.info("Connected successfully")
                return True
            else:
                logger.error("Connection timeout")
                return False

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.state = ConnectionState.ERROR
            self.stats['errors'] += 1
            return False

    def disconnect(self):
        """Disconnect from MQTT broker"""
        try:
            logger.info("Disconnecting from broker")

            # Stop queue processing
            self._stop_queue_processor()

            # Disconnect from broker
            self.client.loop_stop()
            self.client.disconnect()

            with self._lock:
                self.connected = False
                self.state = ConnectionState.DISCONNECTED

            logger.info("Disconnected successfully")

        except Exception as e:
            logger.error(f"Disconnect error: {e}")

    def reconnect(self) -> bool:
        """Manually trigger reconnection"""
        logger.info("Manual reconnect triggered")
        self.disconnect()
        time.sleep(1)
        return self.connect()

    # ========================================================================
    # Callback Handlers
    # ========================================================================

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker"""
        if rc == 0:
            with self._lock:
                self.connected = True
                self.state = ConnectionState.CONNECTED

            logger.info(f"Connected to broker (flags: {flags})")

            # Resubscribe to all topics
            self._resubscribe_all()

            # Start queue processor
            self._start_queue_processor()

        else:
            error_messages = {
                1: "Incorrect protocol version",
                2: "Invalid client identifier",
                3: "Server unavailable",
                4: "Bad username or password",
                5: "Not authorized"
            }
            error_msg = error_messages.get(rc, f"Unknown error ({rc})")
            logger.error(f"Connection failed: {error_msg}")

            with self._lock:
                self.connected = False
                self.state = ConnectionState.ERROR

            self.stats['errors'] += 1

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker"""
        with self._lock:
            self.connected = False

            if rc == 0:
                self.state = ConnectionState.DISCONNECTED
                logger.info("Disconnected gracefully")
            else:
                self.state = ConnectionState.RECONNECTING
                logger.warning(f"Unexpected disconnect (rc: {rc})")

        # Stop queue processor
        self._stop_queue_processor()

        # Automatic reconnection
        if self.config.auto_reconnect and rc != 0:
            self._handle_reconnect()

    def _on_message(self, client, userdata, message):
        """Callback when message received"""
        try:
            topic = message.topic
            payload = message.payload.decode('utf-8')

            logger.debug(f"Message received: {topic} -> {payload[:100]}")

            self.stats['messages_received'] += 1

            # Try to parse as JSON
            try:
                payload_data = json.loads(payload)
            except json.JSONDecodeError:
                payload_data = payload

            # Route to topic-specific callback
            if topic in self.subscriptions:
                callback = self.subscriptions[topic].callback
                if callback:
                    try:
                        callback(topic, payload_data, message)
                    except Exception as e:
                        logger.error(f"Callback error for {topic}: {e}")

            # Route to wildcard callbacks
            for pattern, callback in self.wildcard_callbacks:
                if self._topic_matches(topic, pattern):
                    try:
                        callback(topic, payload_data, message)
                    except Exception as e:
                        logger.error(f"Wildcard callback error for {pattern}: {e}")

        except Exception as e:
            logger.error(f"Message processing error: {e}")
            self.stats['errors'] += 1

    def _on_publish(self, client, userdata, mid):
        """Callback when message published"""
        logger.debug(f"Message published (mid: {mid})")

    def _on_subscribe(self, client, userdata, mid, granted_qos):
        """Callback when subscribed to topic"""
        logger.debug(f"Subscribed (mid: {mid}, QoS: {granted_qos})")

    def _on_unsubscribe(self, client, userdata, mid):
        """Callback when unsubscribed from topic"""
        logger.debug(f"Unsubscribed (mid: {mid})")

    def _on_log(self, client, userdata, level, buf):
        """Callback for MQTT client logs"""
        # Only log warnings and errors
        if level <= mqtt.MQTT_LOG_WARNING:
            logger.debug(f"MQTT Log: {buf}")

    # ========================================================================
    # Publishing
    # ========================================================================

    def publish(self, topic: str, payload: Any, qos: int = 1,
                retain: bool = False) -> bool:
        """
        Publish message to topic

        Args:
            topic: MQTT topic
            payload: Message payload (will be JSON encoded if dict/list)
            qos: Quality of Service (0, 1, or 2)
            retain: Retain flag

        Returns:
            True if published successfully, False otherwise
        """
        try:
            # Convert payload to string
            if isinstance(payload, (dict, list)):
                payload_str = json.dumps(payload)
            else:
                payload_str = str(payload)

            # Publish if connected
            if self.connected:
                result = self.client.publish(topic, payload_str, qos, retain)

                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    self.stats['messages_sent'] += 1
                    logger.debug(f"Published to {topic}: {payload_str[:100]}")
                    return True
                else:
                    logger.warning(f"Publish failed (rc: {result.rc})")
                    # Queue message for retry
                    self._queue_message(topic, payload_str, qos, retain)
                    return False
            else:
                # Queue message if not connected
                logger.debug(f"Not connected, queueing message to {topic}")
                self._queue_message(topic, payload_str, qos, retain)
                return False

        except Exception as e:
            logger.error(f"Publish error: {e}")
            self.stats['errors'] += 1
            return False

    def _queue_message(self, topic: str, payload: str, qos: int, retain: bool):
        """Queue message for later publishing"""
        try:
            message = QueuedMessage(
                topic=topic,
                payload=payload,
                qos=qos,
                retain=retain,
                timestamp=time.time()
            )

            self.message_queue.put_nowait(message)
            self.stats['messages_queued'] += 1
            logger.debug(f"Message queued: {topic}")

        except Exception as e:
            logger.error(f"Failed to queue message: {e}")

    # ========================================================================
    # Subscribing
    # ========================================================================

    def subscribe(self, topic: str, qos: int = 1,
                  callback: Optional[Callable] = None) -> bool:
        """
        Subscribe to topic

        Args:
            topic: MQTT topic (can include wildcards)
            qos: Quality of Service
            callback: Function to call when message received
                      Signature: callback(topic, payload, message)

        Returns:
            True if subscribed successfully, False otherwise
        """
        try:
            # Store subscription
            subscription = Subscription(topic=topic, qos=qos, callback=callback)

            # Handle wildcard subscriptions
            if '+' in topic or '#' in topic:
                self.wildcard_callbacks.append((topic, callback))
            else:
                self.subscriptions[topic] = subscription

            # Subscribe if connected
            if self.connected:
                result, mid = self.client.subscribe(topic, qos)

                if result == mqtt.MQTT_ERR_SUCCESS:
                    logger.info(f"Subscribed to: {topic} (QoS {qos})")
                    return True
                else:
                    logger.error(f"Subscribe failed (rc: {result})")
                    return False
            else:
                logger.debug(f"Not connected, subscription will be applied on connect")
                return True

        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            self.stats['errors'] += 1
            return False

    def unsubscribe(self, topic: str) -> bool:
        """Unsubscribe from topic"""
        try:
            # Remove from subscriptions
            if topic in self.subscriptions:
                del self.subscriptions[topic]

            # Remove from wildcard callbacks
            self.wildcard_callbacks = [
                (t, c) for t, c in self.wildcard_callbacks if t != topic
            ]

            # Unsubscribe if connected
            if self.connected:
                result, mid = self.client.unsubscribe(topic)

                if result == mqtt.MQTT_ERR_SUCCESS:
                    logger.info(f"Unsubscribed from: {topic}")
                    return True
                else:
                    logger.error(f"Unsubscribe failed (rc: {result})")
                    return False
            else:
                return True

        except Exception as e:
            logger.error(f"Unsubscribe error: {e}")
            return False

    def _resubscribe_all(self):
        """Resubscribe to all topics after reconnection"""
        logger.info("Resubscribing to all topics")

        # Subscribe to regular topics
        for topic, sub in self.subscriptions.items():
            self.client.subscribe(topic, sub.qos)

        # Subscribe to wildcard topics
        for topic, callback in self.wildcard_callbacks:
            self.client.subscribe(topic, 1)

    # ========================================================================
    # Queue Processing
    # ========================================================================

    def _start_queue_processor(self):
        """Start background thread to process queued messages"""
        if not self.queue_running:
            self.queue_running = True
            self.queue_thread = threading.Thread(
                target=self._process_queue,
                daemon=True
            )
            self.queue_thread.start()
            logger.info("Queue processor started")

    def _stop_queue_processor(self):
        """Stop queue processor thread"""
        self.queue_running = False
        if self.queue_thread:
            self.queue_thread.join(timeout=2)
            logger.info("Queue processor stopped")

    def _process_queue(self):
        """Process queued messages (runs in background thread)"""
        logger.info("Queue processor running")

        while self.queue_running:
            try:
                # Get message from queue (with timeout)
                try:
                    message = self.message_queue.get(timeout=1)
                except Empty:
                    continue

                # Check if message is too old
                age = time.time() - message.timestamp
                if age > self.config.message_timeout:
                    logger.warning(f"Dropping old message (age: {age:.1f}s)")
                    continue

                # Publish message
                if self.connected:
                    result = self.client.publish(
                        message.topic,
                        message.payload,
                        message.qos,
                        message.retain
                    )

                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        logger.debug(f"Published queued message to {message.topic}")
                        self.stats['messages_sent'] += 1
                    else:
                        # Put back in queue
                        self.message_queue.put(message)
                        time.sleep(1)
                else:
                    # Put back in queue if not connected
                    self.message_queue.put(message)
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Queue processing error: {e}")
                time.sleep(1)

    # ========================================================================
    # Reconnection Handling
    # ========================================================================

    def _handle_reconnect(self):
        """Handle reconnection with exponential backoff"""
        self.stats['reconnect_count'] += 1
        delay = self.config.reconnect_delay

        logger.info(f"Reconnection attempt #{self.stats['reconnect_count']}")

        while self.config.auto_reconnect and not self.connected:
            try:
                logger.info(f"Reconnecting in {delay} seconds...")
                time.sleep(delay)

                # Try to reconnect
                self.client.reconnect()

                # Exponential backoff
                delay = min(delay * 2, self.config.max_reconnect_delay)

            except Exception as e:
                logger.error(f"Reconnect failed: {e}")
                continue

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def is_connected(self) -> bool:
        """Check if connected to broker"""
        return self.connected

    def get_state(self) -> ConnectionState:
        """Get current connection state"""
        return self.state

    def get_stats(self) -> Dict[str, int]:
        """Get client statistics"""
        return {
            **self.stats,
            'queue_size': self.message_queue.qsize()
        }

    def _topic_matches(self, topic: str, pattern: str) -> bool:
        """
        Check if topic matches pattern with wildcards
        + matches single level
        # matches multiple levels
        """
        topic_parts = topic.split('/')
        pattern_parts = pattern.split('/')

        # # must be last element
        if '#' in pattern_parts[:-1]:
            return False

        # Check each level
        for i, pattern_part in enumerate(pattern_parts):
            if pattern_part == '#':
                return True

            if i >= len(topic_parts):
                return False

            if pattern_part != '+' and pattern_part != topic_parts[i]:
                return False

        return len(topic_parts) == len(pattern_parts)

    # ========================================================================
    # Context Manager Support
    # ========================================================================

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


# ============================================================================
# Helper Functions
# ============================================================================

def create_client(broker_host: str = "localhost",
                  broker_port: int = 1883,
                  client_id: str = "",
                  username: Optional[str] = None,
                  password: Optional[str] = None) -> MQTTClientWrapper:
    """
    Create and return configured MQTT client

    Args:
        broker_host: MQTT broker hostname
        broker_port: MQTT broker port
        client_id: Unique client identifier
        username: Authentication username
        password: Authentication password

    Returns:
        Configured MQTTClientWrapper instance
    """
    config = MQTTConfig(
        broker_host=broker_host,
        broker_port=broker_port,
        client_id=client_id,
        username=username,
        password=password
    )

    return MQTTClientWrapper(config)


def create_client_from_env() -> MQTTClientWrapper:
    """
    Create MQTT client from environment variables

    Environment variables:
        MQTT_BROKER_HOST
        MQTT_BROKER_PORT
        MQTT_CLIENT_ID
        MQTT_USERNAME
        MQTT_PASSWORD
    """
    config = MQTTConfig(
        broker_host=os.getenv('MQTT_BROKER_HOST', 'localhost'),
        broker_port=int(os.getenv('MQTT_BROKER_PORT', 1883)),
        client_id=os.getenv('MQTT_CLIENT_ID', ''),
        username=os.getenv('MQTT_USERNAME'),
        password=os.getenv('MQTT_PASSWORD')
    )

    return MQTTClientWrapper(config)


# ============================================================================
# Example Usage
# ============================================================================

def example_usage():
    """Example of how to use the MQTT client wrapper"""

    # Create client
    config = MQTTConfig(
        broker_host="localhost",
        broker_port=1883,
        client_id="example_client"
    )

    client = MQTTClientWrapper(config)

    # Define message callback
    def on_message(topic, payload, message):
        print(f"Received: {topic} -> {payload}")

    # Connect
    if client.connect():
        # Subscribe to topics
        client.subscribe("device/+/telemetry", callback=on_message)
        client.subscribe("device/+/status", callback=on_message)

        # Publish messages
        client.publish("device/sensor-001/telemetry", {
            "temperature": 23.5,
            "humidity": 65
        })

        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

        # Disconnect
        client.disconnect()


if __name__ == '__main__':
    # Run example
    example_usage()