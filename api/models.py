#!/usr/bin/env python3
"""
Digital Twin Network - API Data Models
Data classes and schemas for twins, devices, commands, and telemetry
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import json


# ============================================================================
# Enumerations
# ============================================================================

class TwinStatus(Enum):
    """Twin status enumeration"""
    PENDING = "pending"
    ACTIVE = "active"
    ONLINE = "online"
    OFFLINE = "offline"
    SUSPENDED = "suspended"
    DECOMMISSIONED = "decommissioned"
    ERROR = "error"


class CommandStatus(Enum):
    """Command execution status"""
    PENDING = "pending"
    SENT = "sent"
    RECEIVED = "received"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class DeviceType(Enum):
    """Common device types"""
    TEMPERATURE_SENSOR = "temperature_sensor"
    HUMIDITY_SENSOR = "humidity_sensor"
    PRESSURE_SENSOR = "pressure_sensor"
    MOTION_SENSOR = "motion_sensor"
    LIGHT_SENSOR = "light_sensor"
    SMART_LIGHT = "smart_light"
    SMART_THERMOSTAT = "smart_thermostat"
    ACTUATOR = "actuator"
    CONTROLLER = "controller"
    GATEWAY = "gateway"
    GENERIC = "generic"


class MessageType(Enum):
    """MQTT message types"""
    TELEMETRY = "telemetry"
    STATE = "state"
    COMMAND = "command"
    ACK = "ack"
    ERROR = "error"
    STATUS = "status"
    HEARTBEAT = "heartbeat"


# ============================================================================
# Base Model Class
# ============================================================================

@dataclass
class BaseModel:
    """Base class for all models with common functionality"""

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return asdict(self)

    def to_json(self) -> str:
        """Convert model to JSON string"""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create model instance from dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str):
        """Create model instance from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)


# ============================================================================
# Digital Twin Models
# ============================================================================

@dataclass
class TwinMetadata(BaseModel):
    """Metadata for a digital twin"""
    location: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    hardware_version: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TwinProperties(BaseModel):
    """Static properties of a digital twin"""
    capabilities: List[str] = field(default_factory=list)
    supported_commands: List[str] = field(default_factory=list)
    update_interval_seconds: int = 5
    timeout_seconds: int = 30
    max_retries: int = 3
    qos_level: int = 1
    custom_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TwinState(BaseModel):
    """Current state of a digital twin"""
    values: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[str] = None
    version: int = 0

    def update(self, new_values: Dict[str, Any]):
        """Update state with new values"""
        self.values.update(new_values)
        self.version += 1
        self.timestamp = datetime.utcnow().isoformat() + 'Z'


@dataclass
class DigitalTwin(BaseModel):
    """Complete digital twin model"""
    id: str
    type: str
    state: TwinState = field(default_factory=TwinState)
    properties: TwinProperties = field(default_factory=TwinProperties)
    metadata: TwinMetadata = field(default_factory=TwinMetadata)
    status: str = TwinStatus.PENDING.value
    created_at: Optional[str] = None
    last_updated: Optional[str] = None
    last_seen: Optional[str] = None
    error_count: int = 0
    message_count: int = 0

    def __post_init__(self):
        """Initialize timestamps if not provided"""
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat() + 'Z'
        if self.last_updated is None:
            self.last_updated = self.created_at

    def update_state(self, new_state: Dict[str, Any]):
        """Update twin state"""
        self.state.update(new_state)
        self.last_updated = datetime.utcnow().isoformat() + 'Z'
        self.last_seen = self.last_updated
        self.message_count += 1

        # Update status to online when receiving data
        if self.status != TwinStatus.ONLINE.value:
            self.status = TwinStatus.ONLINE.value

    def mark_offline(self):
        """Mark twin as offline"""
        self.status = TwinStatus.OFFLINE.value
        self.last_updated = datetime.utcnow().isoformat() + 'Z'

    def record_error(self):
        """Record an error occurrence"""
        self.error_count += 1
        self.last_updated = datetime.utcnow().isoformat() + 'Z'


# ============================================================================
# Device Models
# ============================================================================

@dataclass
class DeviceInfo(BaseModel):
    """Basic device information"""
    device_id: str
    device_type: str
    status: str = TwinStatus.OFFLINE.value
    last_seen: Optional[str] = None
    uptime_seconds: int = 0
    firmware_version: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None


@dataclass
class DeviceHealth(BaseModel):
    """Device health metrics"""
    device_id: str
    status: str
    last_updated: str
    uptime_seconds: int = 0
    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    battery_level: Optional[float] = None
    signal_strength: Optional[float] = None
    error_count: int = 0
    message_count: int = 0
    last_error: Optional[str] = None


# ============================================================================
# Telemetry Models
# ============================================================================

@dataclass
class TelemetryData(BaseModel):
    """Telemetry data point"""
    device_id: str
    timestamp: str
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Ensure timestamp is set"""
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + 'Z'


@dataclass
class TelemetryBatch(BaseModel):
    """Batch of telemetry data points"""
    device_id: str
    count: int
    telemetry: List[TelemetryData]
    start_time: Optional[str] = None
    end_time: Optional[str] = None


@dataclass
class SensorReading(BaseModel):
    """Generic sensor reading"""
    sensor_type: str
    value: float
    unit: str
    timestamp: str
    accuracy: Optional[float] = None

    def __post_init__(self):
        """Ensure timestamp is set"""
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + 'Z'


# ============================================================================
# Command Models
# ============================================================================

@dataclass
class CommandParameters(BaseModel):
    """Command parameters"""
    params: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default=None):
        """Get parameter value"""
        return self.params.get(key, default)

    def set(self, key: str, value: Any):
        """Set parameter value"""
        self.params[key] = value


@dataclass
class CommandResult(BaseModel):
    """Result of command execution"""
    success: bool
    execution_time_seconds: float = 0.0
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class Command(BaseModel):
    """Command to be sent to a device"""
    command_id: str
    device_id: str
    action: str
    parameters: CommandParameters = field(default_factory=CommandParameters)
    status: str = CommandStatus.PENDING.value
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    sent_at: Optional[str] = None
    completed_at: Optional[str] = None
    timeout_seconds: int = 30
    retries: int = 0
    max_retries: int = 3
    result: Optional[CommandResult] = None

    def __post_init__(self):
        """Initialize timestamps"""
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat() + 'Z'
        if self.updated_at is None:
            self.updated_at = self.created_at

    def mark_sent(self):
        """Mark command as sent"""
        self.status = CommandStatus.SENT.value
        self.sent_at = datetime.utcnow().isoformat() + 'Z'
        self.updated_at = self.sent_at

    def mark_completed(self, result: CommandResult):
        """Mark command as completed"""
        self.status = CommandStatus.COMPLETED.value
        self.result = result
        self.completed_at = datetime.utcnow().isoformat() + 'Z'
        self.updated_at = self.completed_at

    def mark_failed(self, error_message: str, error_code: Optional[str] = None):
        """Mark command as failed"""
        self.status = CommandStatus.FAILED.value
        self.result = CommandResult(
            success=False,
            error_message=error_message,
            error_code=error_code
        )
        self.updated_at = datetime.utcnow().isoformat() + 'Z'

    def retry(self) -> bool:
        """Attempt to retry command"""
        if self.retries < self.max_retries:
            self.retries += 1
            self.status = CommandStatus.PENDING.value
            self.updated_at = datetime.utcnow().isoformat() + 'Z'
            return True
        return False


# ============================================================================
# Message Models
# ============================================================================

@dataclass
class MQTTMessage(BaseModel):
    """MQTT message wrapper"""
    topic: str
    payload: Dict[str, Any]
    qos: int = 1
    retain: bool = False
    timestamp: Optional[str] = None

    def __post_init__(self):
        """Ensure timestamp is set"""
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + 'Z'


@dataclass
class TelemetryMessage(MQTTMessage):
    """Telemetry MQTT message"""
    device_id: str = ""
    message_type: str = MessageType.TELEMETRY.value
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Set topic based on device_id"""
        super().__post_init__()
        if self.device_id and not self.topic:
            self.topic = f"device/{self.device_id}/telemetry"
        self.payload = {
            "device_id": self.device_id,
            "type": self.message_type,
            "data": self.data,
            "timestamp": self.timestamp
        }


@dataclass
class CommandMessage(MQTTMessage):
    """Command MQTT message"""
    device_id: str = ""
    command_id: str = ""
    action: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Set topic and payload"""
        super().__post_init__()
        if self.device_id and not self.topic:
            self.topic = f"device/{self.device_id}/command"
        self.payload = {
            "command_id": self.command_id,
            "device_id": self.device_id,
            "action": self.action,
            "parameters": self.parameters,
            "timestamp": self.timestamp
        }
        self.qos = 2  # Commands use QoS 2 for exactly-once delivery


@dataclass
class AckMessage(MQTTMessage):
    """Acknowledgment MQTT message"""
    device_id: str = ""
    command_id: str = ""
    status: str = ""
    result: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Set topic and payload"""
        super().__post_init__()
        if self.device_id and not self.topic:
            self.topic = f"device/{self.device_id}/ack"
        self.payload = {
            "command_id": self.command_id,
            "device_id": self.device_id,
            "status": self.status,
            "result": self.result,
            "timestamp": self.timestamp
        }


@dataclass
class ErrorMessage(MQTTMessage):
    """Error MQTT message"""
    device_id: str = ""
    error_code: str = ""
    error_message: str = ""
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Set topic and payload"""
        super().__post_init__()
        if self.device_id and not self.topic:
            self.topic = f"device/{self.device_id}/error"
        self.payload = {
            "device_id": self.device_id,
            "error_code": self.error_code,
            "message": self.error_message,
            "details": self.details,
            "timestamp": self.timestamp
        }


# ============================================================================
# Statistics Models
# ============================================================================

@dataclass
class TwinStatistics(BaseModel):
    """Statistical summary for a twin"""
    twin_id: str
    message_count: int = 0
    error_count: int = 0
    command_count: int = 0
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    uptime_percent: float = 0.0
    average_values: Dict[str, float] = field(default_factory=dict)
    min_values: Dict[str, float] = field(default_factory=dict)
    max_values: Dict[str, float] = field(default_factory=dict)
    std_dev_values: Dict[str, float] = field(default_factory=dict)


@dataclass
class SystemStatistics(BaseModel):
    """System-wide statistics"""
    total_twins: int = 0
    active_twins: int = 0
    offline_twins: int = 0
    total_messages: int = 0
    total_commands: int = 0
    total_errors: int = 0
    messages_per_second: float = 0.0
    average_latency_ms: float = 0.0
    uptime_seconds: int = 0


# ============================================================================
# Response Models
# ============================================================================

@dataclass
class APIResponse(BaseModel):
    """Standard API response wrapper"""
    status: str  # "success" or "error"
    message: str
    timestamp: str
    data: Optional[Any] = None

    def __post_init__(self):
        """Ensure timestamp is set"""
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + 'Z'


@dataclass
class ErrorResponse(BaseModel):
    """Error response model"""
    status: str = "error"
    error: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[str] = None

    def __post_init__(self):
        """Ensure timestamp is set"""
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + 'Z'

    @classmethod
    def create(cls, message: str, code: Optional[str] = None):
        """Create error response"""
        error_data = {"message": message}
        if code:
            error_data["code"] = code
        return cls(error=error_data)


@dataclass
class PaginatedResponse(BaseModel):
    """Paginated response model"""
    count: int
    total: int
    offset: int
    limit: int
    items: List[Any] = field(default_factory=list)
    has_more: bool = False

    def __post_init__(self):
        """Calculate has_more flag"""
        self.has_more = (self.offset + self.count) < self.total


# ============================================================================
# Validation Schemas
# ============================================================================

class ValidationSchema:
    """JSON schema definitions for validation"""

    TELEMETRY_SCHEMA = {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
            "timestamp": {"type": "string"},
            "data": {"type": "object"}
        },
        "required": ["device_id", "data"]
    }

    COMMAND_SCHEMA = {
        "type": "object",
        "properties": {
            "action": {"type": "string"},
            "parameters": {"type": "object"}
        },
        "required": ["action"]
    }

    TWIN_CREATE_SCHEMA = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "type": {"type": "string", "minLength": 1},
            "metadata": {"type": "object"},
            "properties": {"type": "object"}
        },
        "required": ["id", "type"]
    }

    STATE_UPDATE_SCHEMA = {
        "type": "object",
        "minProperties": 1
    }


# ============================================================================
# Model Factory Functions
# ============================================================================

def create_twin(twin_id: str, device_type: str,
                metadata: Optional[Dict] = None,
                properties: Optional[Dict] = None) -> DigitalTwin:
    """Factory function to create a new digital twin"""
    twin_metadata = TwinMetadata(**(metadata or {}))
    twin_properties = TwinProperties(**(properties or {}))

    return DigitalTwin(
        id=twin_id,
        type=device_type,
        metadata=twin_metadata,
        properties=twin_properties,
        status=TwinStatus.PENDING.value
    )


def create_command(device_id: str, action: str,
                   parameters: Optional[Dict] = None,
                   command_id: Optional[str] = None) -> Command:
    """Factory function to create a new command"""
    import uuid

    if command_id is None:
        command_id = f"cmd-{uuid.uuid4().hex[:8]}"

    cmd_params = CommandParameters(params=parameters or {})

    return Command(
        command_id=command_id,
        device_id=device_id,
        action=action,
        parameters=cmd_params
    )


def create_telemetry(device_id: str, data: Dict[str, Any],
                     timestamp: Optional[str] = None) -> TelemetryData:
    """Factory function to create telemetry data"""
    if timestamp is None:
        timestamp = datetime.utcnow().isoformat() + 'Z'

    return TelemetryData(
        device_id=device_id,
        timestamp=timestamp,
        data=data
    )


# ============================================================================
# Utility Functions
# ============================================================================

def validate_twin_id(twin_id: str) -> bool:
    """Validate twin ID format"""
    if not twin_id:
        return False
    if len(twin_id) > 128:
        return False
    # Check for invalid characters
    invalid_chars = [' ', '/', '\\', '#', '+', '*']
    return not any(char in twin_id for char in invalid_chars)


def validate_topic(topic: str) -> bool:
    """Validate MQTT topic format"""
    if not topic:
        return False
    if len(topic) > 256:
        return False
    # Check for invalid characters in publish topics
    invalid_chars = ['#', '+'] if '/' in topic else []
    return not any(char in topic for char in invalid_chars)


def parse_topic(topic: str) -> Dict[str, str]:
    """Parse MQTT topic into components"""
    parts = topic.split('/')
    if len(parts) < 3:
        return {}

    return {
        "root": parts[0],
        "device_id": parts[1],
        "message_type": parts[2]
    }


def calculate_uptime(created_at: str, current_time: Optional[str] = None) -> int:
    """Calculate uptime in seconds"""
    try:
        created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        if current_time:
            current = datetime.fromisoformat(current_time.replace('Z', '+00:00'))
        else:
            current = datetime.utcnow()

        delta = current - created
        return int(delta.total_seconds())
    except Exception:
        return 0


def is_online(last_seen: Optional[str], timeout_seconds: int = 60) -> bool:
    """Check if device is considered online based on last_seen timestamp"""
    if not last_seen:
        return False

    try:
        last_seen_dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
        current_dt = datetime.utcnow()
        delta = current_dt - last_seen_dt

        return delta.total_seconds() < timeout_seconds
    except Exception:
        return False


# ============================================================================
# Export All Models
# ============================================================================

__all__ = [
    # Enums
    'TwinStatus',
    'CommandStatus',
    'DeviceType',
    'MessageType',

    # Base
    'BaseModel',

    # Twin Models
    'TwinMetadata',
    'TwinProperties',
    'TwinState',
    'DigitalTwin',

    # Device Models
    'DeviceInfo',
    'DeviceHealth',

    # Telemetry Models
    'TelemetryData',
    'TelemetryBatch',
    'SensorReading',

    # Command Models
    'CommandParameters',
    'CommandResult',
    'Command',

    # Message Models
    'MQTTMessage',
    'TelemetryMessage',
    'CommandMessage',
    'AckMessage',
    'ErrorMessage',

    # Statistics Models
    'TwinStatistics',
    'SystemStatistics',

    # Response Models
    'APIResponse',
    'ErrorResponse',
    'PaginatedResponse',

    # Validation
    'ValidationSchema',

    # Factory Functions
    'create_twin',
    'create_command',
    'create_telemetry',

    # Utility Functions
    'validate_twin_id',
    'validate_topic',
    'parse_topic',
    'calculate_uptime',
    'is_online'
]