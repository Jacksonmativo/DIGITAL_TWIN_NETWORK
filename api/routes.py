#!/usr/bin/env python3
"""
Digital Twin Network - API Routes
Organized route handlers using Flask Blueprints
"""

import logging
from typing import Dict, List, Optional
from flask import Blueprint, request, jsonify
from datetime import datetime

# Import models
from models import (
    DigitalTwin, Command, TelemetryData,
    TwinStatus, CommandStatus,
    create_twin, create_command, create_telemetry,
    validate_twin_id, APIResponse, ErrorResponse
)

# Configure logging
logger = logging.getLogger(__name__)

# ============================================================================
# Blueprints Definition
# ============================================================================

# Create blueprints for different resource groups
twins_bp = Blueprint('twins', __name__, url_prefix='/api/v1/twins')
commands_bp = Blueprint('commands', __name__, url_prefix='/api/v1/commands')
devices_bp = Blueprint('devices', __name__, url_prefix='/api/v1/devices')
system_bp = Blueprint('system', __name__, url_prefix='/api/v1/system')
telemetry_bp = Blueprint('telemetry', __name__, url_prefix='/api/v1/telemetry')

# ============================================================================
# Data Storage References (will be injected from app.py)
# ============================================================================

twins_store: Dict[str, dict] = {}
commands_store: Dict[str, dict] = {}
telemetry_store: Dict[str, List[dict]] = {}
mqtt_client = None  # Reference to MQTT client


# ============================================================================
# Helper Functions
# ============================================================================

def get_timestamp() -> str:
    """Return current timestamp in ISO format"""
    return datetime.utcnow().isoformat() + 'Z'


def success_response(data=None, message="Success", status_code=200):
    """Create standardized success response"""
    response = {
        "status": "success",
        "message": message,
        "timestamp": get_timestamp()
    }
    if data is not None:
        response["data"] = data
    return jsonify(response), status_code


def error_response(message, error_code=None, status_code=400):
    """Create standardized error response"""
    response = {
        "status": "error",
        "error": {
            "message": message,
            "timestamp": get_timestamp()
        }
    }
    if error_code:
        response["error"]["code"] = error_code
    return jsonify(response), status_code


def validate_required_fields(data: dict, required_fields: list) -> tuple:
    """
    Validate that required fields exist in data
    Returns (is_valid, error_message)
    """
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"
    return True, None


def paginate_list(items: list, offset: int = 0, limit: int = 100) -> dict:
    """
    Paginate a list of items
    Returns dict with pagination metadata
    """
    total = len(items)
    paginated = items[offset:offset + limit]

    return {
        "count": len(paginated),
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": (offset + len(paginated)) < total,
        "items": paginated
    }


# ============================================================================
# TWINS ROUTES
# ============================================================================

@twins_bp.route('', methods=['GET'])
def get_all_twins():
    """
    Get all twins with optional filtering
    Query parameters:
    - type: Filter by device type
    - status: Filter by status (online/offline)
    - limit: Maximum number of results (default: 100)
    - offset: Pagination offset (default: 0)
    - sort: Sort field (default: created_at)
    - order: Sort order (asc/desc, default: desc)
    """
    try:
        # Extract query parameters
        device_type = request.args.get('type')
        status = request.args.get('status')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        sort_field = request.args.get('sort', 'created_at')
        sort_order = request.args.get('order', 'desc')

        # Validate parameters
        if limit > 1000:
            return error_response("Limit cannot exceed 1000", "INVALID_LIMIT")
        if limit < 1:
            return error_response("Limit must be at least 1", "INVALID_LIMIT")

        # Get all twins
        all_twins = list(twins_store.values())

        # Apply filters
        filtered_twins = all_twins
        if device_type:
            filtered_twins = [t for t in filtered_twins if t.get('type') == device_type]
        if status:
            filtered_twins = [t for t in filtered_twins if t.get('status') == status]

        # Apply sorting
        reverse = (sort_order.lower() == 'desc')
        try:
            filtered_twins.sort(
                key=lambda x: x.get(sort_field, ''),
                reverse=reverse
            )
        except Exception as e:
            logger.warning(f"Sort failed: {e}, using default order")

        # Apply pagination
        pagination_result = paginate_list(filtered_twins, offset, limit)

        return success_response(pagination_result)

    except ValueError as e:
        return error_response(f"Invalid parameter: {e}", "INVALID_PARAMETER")
    except Exception as e:
        logger.error(f"Error getting twins: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


@twins_bp.route('/<twin_id>', methods=['GET'])
def get_twin_by_id(twin_id):
    """Get detailed information about a specific twin"""
    try:
        if twin_id not in twins_store:
            return error_response(
                f"Twin with ID '{twin_id}' not found",
                "TWIN_NOT_FOUND",
                404
            )

        twin = twins_store[twin_id]

        # Add additional computed fields
        twin_data = {
            **twin,
            "is_online": twin.get('status') == 'online',
            "message_count": len(telemetry_store.get(twin_id, [])),
            "command_count": sum(1 for c in commands_store.values() if c['twin_id'] == twin_id)
        }

        return success_response(twin_data)

    except Exception as e:
        logger.error(f"Error getting twin {twin_id}: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


@twins_bp.route('', methods=['POST'])
def create_new_twin():
    """
    Create a new digital twin
    Request body:
    {
        "id": "sensor-001",
        "type": "temperature_sensor",
        "metadata": {
            "location": "Room A",
            "manufacturer": "SensorCorp"
        },
        "properties": {
            "update_interval_seconds": 5
        }
    }
    """
    try:
        if not request.is_json:
            return error_response(
                "Content-Type must be application/json",
                "INVALID_CONTENT_TYPE",
                415
            )

        data = request.get_json()

        # Validate required fields
        is_valid, error_msg = validate_required_fields(data, ['id', 'type'])
        if not is_valid:
            return error_response(error_msg, "MISSING_FIELD")

        twin_id = data['id']

        # Validate twin ID format
        if not validate_twin_id(twin_id):
            return error_response(
                "Invalid twin ID format",
                "INVALID_TWIN_ID"
            )

        # Check if twin already exists
        if twin_id in twins_store:
            return error_response(
                f"Twin with ID '{twin_id}' already exists",
                "TWIN_ALREADY_EXISTS",
                409
            )

        # Create twin using factory function
        twin = {
            "id": twin_id,
            "type": data['type'],
            "state": {},
            "properties": data.get('properties', {}),
            "metadata": data.get('metadata', {}),
            "status": TwinStatus.OFFLINE.value,
            "created_at": get_timestamp(),
            "last_updated": get_timestamp(),
            "error_count": 0,
            "message_count": 0
        }

        # Store twin
        twins_store[twin_id] = twin

        logger.info(f"Created twin: {twin_id} of type {data['type']}")

        # TODO: Subscribe to device MQTT topics
        # if mqtt_client:
        #     mqtt_client.subscribe(f"device/{twin_id}/telemetry")
        #     mqtt_client.subscribe(f"device/{twin_id}/ack")

        return success_response(twin, "Twin created successfully", 201)

    except Exception as e:
        logger.error(f"Error creating twin: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


@twins_bp.route('/<twin_id>', methods=['PUT'])
def update_twin(twin_id):
    """
    Update twin metadata and properties
    Request body can include: metadata, properties
    """
    try:
        if twin_id not in twins_store:
            return error_response(
                f"Twin with ID '{twin_id}' not found",
                "TWIN_NOT_FOUND",
                404
            )

        if not request.is_json:
            return error_response(
                "Content-Type must be application/json",
                "INVALID_CONTENT_TYPE",
                415
            )

        data = request.get_json()
        twin = twins_store[twin_id]

        # Update allowed fields
        if 'metadata' in data:
            twin['metadata'].update(data['metadata'])

        if 'properties' in data:
            twin['properties'].update(data['properties'])

        twin['last_updated'] = get_timestamp()

        logger.info(f"Updated twin: {twin_id}")

        return success_response(twin, "Twin updated successfully")

    except Exception as e:
        logger.error(f"Error updating twin {twin_id}: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


@twins_bp.route('/<twin_id>', methods=['DELETE'])
def delete_twin(twin_id):
    """Delete a twin and all associated data"""
    try:
        if twin_id not in twins_store:
            return error_response(
                f"Twin with ID '{twin_id}' not found",
                "TWIN_NOT_FOUND",
                404
            )

        # Remove twin
        twin = twins_store.pop(twin_id)

        # Clean up associated data
        if twin_id in telemetry_store:
            del telemetry_store[twin_id]

        # Remove associated commands
        commands_to_remove = [
            cmd_id for cmd_id, cmd in commands_store.items()
            if cmd['twin_id'] == twin_id
        ]
        for cmd_id in commands_to_remove:
            del commands_store[cmd_id]

        logger.info(f"Deleted twin: {twin_id}")

        # TODO: Unsubscribe from MQTT topics
        # if mqtt_client:
        #     mqtt_client.unsubscribe(f"device/{twin_id}/telemetry")
        #     mqtt_client.unsubscribe(f"device/{twin_id}/ack")

        return success_response(
            {"id": twin_id, "deleted_at": get_timestamp()},
            "Twin deleted successfully"
        )

    except Exception as e:
        logger.error(f"Error deleting twin {twin_id}: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


@twins_bp.route('/batch', methods=['POST'])
def batch_create_twins():
    """
    Create multiple twins in one request
    Request body:
    {
        "twins": [
            {"id": "sensor-001", "type": "temperature"},
            {"id": "sensor-002", "type": "humidity"}
        ]
    }
    """
    try:
        if not request.is_json:
            return error_response(
                "Content-Type must be application/json",
                "INVALID_CONTENT_TYPE",
                415
            )

        data = request.get_json()

        if 'twins' not in data or not isinstance(data['twins'], list):
            return error_response(
                "Field 'twins' must be a list",
                "INVALID_FORMAT"
            )

        created = []
        errors = []

        for twin_data in data['twins']:
            try:
                # Validate required fields
                is_valid, error_msg = validate_required_fields(twin_data, ['id', 'type'])
                if not is_valid:
                    errors.append({
                        "id": twin_data.get('id', 'unknown'),
                        "error": error_msg
                    })
                    continue

                twin_id = twin_data['id']

                # Skip if exists
                if twin_id in twins_store:
                    errors.append({
                        "id": twin_id,
                        "error": "Twin already exists"
                    })
                    continue

                # Create twin
                twin = {
                    "id": twin_id,
                    "type": twin_data['type'],
                    "state": {},
                    "properties": twin_data.get('properties', {}),
                    "metadata": twin_data.get('metadata', {}),
                    "status": TwinStatus.OFFLINE.value,
                    "created_at": get_timestamp(),
                    "last_updated": get_timestamp(),
                    "error_count": 0,
                    "message_count": 0
                }

                twins_store[twin_id] = twin
                created.append(twin_id)

            except Exception as e:
                errors.append({
                    "id": twin_data.get('id', 'unknown'),
                    "error": str(e)
                })

        response_data = {
            "created_count": len(created),
            "error_count": len(errors),
            "created": created,
            "errors": errors
        }

        status_code = 201 if created else 400
        message = f"Created {len(created)} twins" if created else "No twins created"

        return success_response(response_data, message, status_code)

    except Exception as e:
        logger.error(f"Error in batch create: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


# ============================================================================
# TWIN STATE ROUTES
# ============================================================================

@twins_bp.route('/<twin_id>/state', methods=['GET'])
def get_twin_state(twin_id):
    """Get current state of a twin"""
    try:
        if twin_id not in twins_store:
            return error_response(
                f"Twin with ID '{twin_id}' not found",
                "TWIN_NOT_FOUND",
                404
            )

        twin = twins_store[twin_id]
        state_data = {
            "twin_id": twin_id,
            "state": twin.get('state', {}),
            "status": twin.get('status', 'unknown'),
            "last_updated": twin.get('last_updated'),
            "version": twin.get('state_version', 0)
        }

        return success_response(state_data)

    except Exception as e:
        logger.error(f"Error getting state for twin {twin_id}: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


@twins_bp.route('/<twin_id>/state', methods=['PUT'])
def update_twin_state(twin_id):
    """
    Update twin state
    Request body: { "temperature": 23.5, "humidity": 65 }
    """
    try:
        if twin_id not in twins_store:
            return error_response(
                f"Twin with ID '{twin_id}' not found",
                "TWIN_NOT_FOUND",
                404
            )

        if not request.is_json:
            return error_response(
                "Content-Type must be application/json",
                "INVALID_CONTENT_TYPE",
                415
            )

        data = request.get_json()
        twin = twins_store[twin_id]

        # Update state
        twin['state'].update(data)
        twin['last_updated'] = get_timestamp()
        twin['status'] = TwinStatus.ONLINE.value
        twin['message_count'] = twin.get('message_count', 0) + 1
        twin['state_version'] = twin.get('state_version', 0) + 1

        logger.info(f"Updated state for twin: {twin_id}")

        return success_response(twin['state'], "State updated successfully")

    except Exception as e:
        logger.error(f"Error updating state for twin {twin_id}: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


@twins_bp.route('/<twin_id>/state/history', methods=['GET'])
def get_state_history(twin_id):
    """
    Get state change history for a twin
    Query parameters:
    - limit: Maximum number of records (default: 100)
    - since: Timestamp to get history since
    """
    try:
        if twin_id not in twins_store:
            return error_response(
                f"Twin with ID '{twin_id}' not found",
                "TWIN_NOT_FOUND",
                404
            )

        limit = int(request.args.get('limit', 100))
        since = request.args.get('since')

        # Get telemetry data as state history
        history = telemetry_store.get(twin_id, [])

        # Filter by timestamp if provided
        if since:
            history = [h for h in history if h.get('timestamp', '') >= since]

        # Apply limit
        history = history[-limit:]

        response_data = {
            "twin_id": twin_id,
            "count": len(history),
            "history": history
        }

        return success_response(response_data)

    except ValueError as e:
        return error_response(f"Invalid parameter: {e}", "INVALID_PARAMETER")
    except Exception as e:
        logger.error(f"Error getting state history for twin {twin_id}: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


# ============================================================================
# TELEMETRY ROUTES
# ============================================================================

@twins_bp.route('/<twin_id>/telemetry', methods=['GET'])
def get_twin_telemetry(twin_id):
    """
    Get telemetry history for a twin
    Query parameters:
    - start: Start timestamp (ISO format)
    - end: End timestamp (ISO format)
    - limit: Maximum number of records (default: 100)
    """
    try:
        if twin_id not in twins_store:
            return error_response(
                f"Twin with ID '{twin_id}' not found",
                "TWIN_NOT_FOUND",
                404
            )

        limit = int(request.args.get('limit', 100))
        start = request.args.get('start')
        end = request.args.get('end')

        # Get telemetry data
        telemetry = telemetry_store.get(twin_id, [])

        # Apply time filtering
        if start:
            telemetry = [t for t in telemetry if t.get('timestamp', '') >= start]
        if end:
            telemetry = [t for t in telemetry if t.get('timestamp', '') <= end]

        # Apply limit (get most recent)
        telemetry = telemetry[-limit:]

        response_data = {
            "twin_id": twin_id,
            "count": len(telemetry),
            "telemetry": telemetry,
            "start": start,
            "end": end
        }

        return success_response(response_data)

    except ValueError as e:
        return error_response(f"Invalid parameter: {e}", "INVALID_PARAMETER")
    except Exception as e:
        logger.error(f"Error getting telemetry for twin {twin_id}: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


@twins_bp.route('/<twin_id>/telemetry', methods=['POST'])
def add_twin_telemetry(twin_id):
    """
    Add telemetry data for a twin
    Request body: { "temperature": 23.5, "humidity": 65 }
    """
    try:
        if twin_id not in twins_store:
            return error_response(
                f"Twin with ID '{twin_id}' not found",
                "TWIN_NOT_FOUND",
                404
            )

        if not request.is_json:
            return error_response(
                "Content-Type must be application/json",
                "INVALID_CONTENT_TYPE",
                415
            )

        data = request.get_json()

        # Create telemetry record
        telemetry_record = {
            **data,
            "timestamp": data.get('timestamp', get_timestamp())
        }

        # Store telemetry
        if twin_id not in telemetry_store:
            telemetry_store[twin_id] = []

        telemetry_store[twin_id].append(telemetry_record)

        # Keep only last 1000 records per twin
        if len(telemetry_store[twin_id]) > 1000:
            telemetry_store[twin_id] = telemetry_store[twin_id][-1000:]

        # Update twin state
        twin = twins_store[twin_id]
        twin['state'].update({k: v for k, v in data.items() if k != 'timestamp'})
        twin['last_updated'] = telemetry_record['timestamp']
        twin['status'] = TwinStatus.ONLINE.value

        return success_response(
            telemetry_record,
            "Telemetry added successfully",
            201
        )

    except Exception as e:
        logger.error(f"Error adding telemetry for twin {twin_id}: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


@twins_bp.route('/<twin_id>/statistics', methods=['GET'])
def get_twin_statistics(twin_id):
    """Get statistical summary for a twin"""
    try:
        if twin_id not in twins_store:
            return error_response(
                f"Twin with ID '{twin_id}' not found",
                "TWIN_NOT_FOUND",
                404
            )

        twin = twins_store[twin_id]
        telemetry = telemetry_store.get(twin_id, [])

        # Calculate statistics
        stats = {
            "twin_id": twin_id,
            "message_count": len(telemetry),
            "first_message": telemetry[0]['timestamp'] if telemetry else None,
            "last_message": telemetry[-1]['timestamp'] if telemetry else None,
            "error_count": twin.get('error_count', 0),
            "command_count": sum(1 for c in commands_store.values() if c['twin_id'] == twin_id),
            "uptime_seconds": 0,  # TODO: Calculate actual uptime
            "average_values": {},  # TODO: Calculate averages from telemetry
            "min_values": {},
            "max_values": {}
        }

        return success_response(stats)

    except Exception as e:
        logger.error(f"Error getting statistics for twin {twin_id}: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


# ============================================================================
# COMMAND ROUTES
# ============================================================================

@twins_bp.route('/<twin_id>/command', methods=['POST'])
def send_twin_command(twin_id):
    """
    Send a command to a device via its twin
    Request body:
    {
        "action": "set_temperature",
        "parameters": { "value": 25 }
    }
    """
    try:
        if twin_id not in twins_store:
            return error_response(
                f"Twin with ID '{twin_id}' not found",
                "TWIN_NOT_FOUND",
                404
            )

        if not request.is_json:
            return error_response(
                "Content-Type must be application/json",
                "INVALID_CONTENT_TYPE",
                415
            )

        data = request.get_json()

        # Validate required fields
        is_valid, error_msg = validate_required_fields(data, ['action'])
        if not is_valid:
            return error_response(error_msg, "MISSING_FIELD")

        # Generate command
        import uuid
        command_id = f"cmd-{uuid.uuid4().hex[:8]}"

        command = {
            "command_id": command_id,
            "twin_id": twin_id,
            "device_id": twin_id,  # Assuming twin_id == device_id
            "action": data['action'],
            "parameters": data.get('parameters', {}),
            "status": CommandStatus.PENDING.value,
            "created_at": get_timestamp(),
            "updated_at": get_timestamp(),
            "timeout_seconds": data.get('timeout', 30),
            "retries": 0
        }

        # Store command
        commands_store[command_id] = command

        logger.info(f"Created command {command_id} for twin {twin_id}")

        # TODO: Publish command to MQTT
        # if mqtt_client:
        #     mqtt_client.publish(
        #         f"device/{twin_id}/command",
        #         json.dumps(command),
        #         qos=2
        #     )

        return success_response(command, "Command created successfully", 201)

    except Exception as e:
        logger.error(f"Error sending command to twin {twin_id}: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


@twins_bp.route('/<twin_id>/commands', methods=['GET'])
def get_twin_commands(twin_id):
    """Get all commands sent to a twin"""
    try:
        if twin_id not in twins_store:
            return error_response(
                f"Twin with ID '{twin_id}' not found",
                "TWIN_NOT_FOUND",
                404
            )

        # Filter commands for this twin
        twin_commands = [
            cmd for cmd in commands_store.values()
            if cmd['twin_id'] == twin_id
        ]

        # Sort by created_at (most recent first)
        twin_commands.sort(
            key=lambda x: x.get('created_at', ''),
            reverse=True
        )

        response_data = {
            "twin_id": twin_id,
            "count": len(twin_commands),
            "commands": twin_commands
        }

        return success_response(response_data)

    except Exception as e:
        logger.error(f"Error getting commands for twin {twin_id}: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


# ============================================================================
# COMMAND MANAGEMENT ROUTES
# ============================================================================

@commands_bp.route('/<command_id>', methods=['GET'])
def get_command(command_id):
    """Get command status by command ID"""
    try:
        if command_id not in commands_store:
            return error_response(
                f"Command with ID '{command_id}' not found",
                "COMMAND_NOT_FOUND",
                404
            )

        command = commands_store[command_id]
        return success_response(command)

    except Exception as e:
        logger.error(f"Error getting command {command_id}: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


@commands_bp.route('/<command_id>', methods=['PUT'])
def update_command(command_id):
    """
    Update command status
    Request body:
    {
        "status": "completed",
        "result": { "success": true }
    }
    """
    try:
        if command_id not in commands_store:
            return error_response(
                f"Command with ID '{command_id}' not found",
                "COMMAND_NOT_FOUND",
                404
            )

        if not request.is_json:
            return error_response(
                "Content-Type must be application/json",
                "INVALID_CONTENT_TYPE",
                415
            )

        data = request.get_json()
        command = commands_store[command_id]

        # Update status
        if 'status' in data:
            command['status'] = data['status']
        if 'result' in data:
            command['result'] = data['result']

        command['updated_at'] = get_timestamp()

        logger.info(f"Updated command {command_id} status to {command['status']}")

        return success_response(command, "Command updated successfully")

    except Exception as e:
        logger.error(f"Error updating command {command_id}: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


@commands_bp.route('', methods=['GET'])
def get_all_commands():
    """
    Get all commands with optional filtering
    Query parameters:
    - status: Filter by status
    - twin_id: Filter by twin ID
    - limit: Maximum results
    """
    try:
        status = request.args.get('status')
        twin_id = request.args.get('twin_id')
        limit = int(request.args.get('limit', 100))

        # Get all commands
        all_commands = list(commands_store.values())

        # Apply filters
        if status:
            all_commands = [c for c in all_commands if c.get('status') == status]
        if twin_id:
            all_commands = [c for c in all_commands if c.get('twin_id') == twin_id]

        # Sort by created_at
        all_commands.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        # Apply limit
        all_commands = all_commands[:limit]

        response_data = {
            "count": len(all_commands),
            "commands": all_commands
        }

        return success_response(response_data)

    except ValueError as e:
        return error_response(f"Invalid parameter: {e}", "INVALID_PARAMETER")
    except Exception as e:
        logger.error(f"Error getting commands: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


# ============================================================================
# DEVICE ROUTES
# ============================================================================

@devices_bp.route('', methods=['GET'])
def get_all_devices():
    """Get list of all connected devices"""
    try:
        devices = [
            {
                "device_id": twin['id'],
                "type": twin['type'],
                "status": twin.get('status', 'unknown'),
                "last_seen": twin.get('last_updated'),
                "message_count": len(telemetry_store.get(twin['id'], []))
            }
            for twin in twins_store.values()
        ]

        response_data = {
            "count": len(devices),
            "devices": devices
        }

        return success_response(response_data)

    except Exception as e:
        logger.error(f"Error getting devices: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


@devices_bp.route('/<device_id>/health', methods=['GET'])
def get_device_health(device_id):
    """Get device health status"""
    try:
        if device_id not in twins_store:
            return error_response(
                f"Device with ID '{device_id}' not found",
                "DEVICE_NOT_FOUND",
                404
            )

        twin = twins_store[device_id]

        health_data = {
            "device_id": device_id,
            "status": twin.get('status', 'unknown'),
            "last_updated": twin.get('last_updated'),
            "uptime_seconds": 0,  # TODO: Calculate
            "message_count": len(telemetry_store.get(device_id, [])),
            "error_count": twin.get('error_count', 0),
            "last_error": None  # TODO: Track errors
        }

        return success_response(health_data)

    except Exception as e:
        logger.error(f"Error getting device health for {device_id}: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


# ============================================================================
# SYSTEM ROUTES
# ============================================================================

@system_bp.route('/status', methods=['GET'])
def get_system_status():
    """Get detailed system status"""
    try:
        status_data = {
            "twins": {
                "total": len(twins_store),
                "online": sum(1 for t in twins_store.values() if t.get("status") == "online"),
                "offline": sum(1 for t in twins_store.values() if t.get("status") == "offline"),
                "pending": sum(1 for t in twins_store.values() if t.get("status") == "pending")
            },
            "commands": {
                "total": len(commands_store),
                "pending": sum(1 for c in commands_store.values() if c.get("status") == "pending"),
                "completed": sum(1 for c in commands_store.values() if c.get("status") == "completed"),
                "failed": sum(1 for c in commands_store.values() if c.get("status") == "failed")
            },
            "telemetry": {
                "devices_reporting": len(telemetry_store),
                "total_messages": sum(len(v) for v in telemetry_store.values())
            },
            "timestamp": get_timestamp()
        }

        return success_response(status_data)

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


@system_bp.route('/metrics', methods=['GET'])
def get_system_metrics():
    """Get system performance metrics"""
    try:
        metrics = {
            "memory_usage_mb": 0,  # TODO: Implement
            "cpu_usage_percent": 0,  # TODO: Implement
            "message_rate_per_second": 0,  # TODO: Implement
            "api_requests_total": 0,  # TODO: Implement
            "errors_total": sum(t.get('error_count', 0) for t in twins_store.values()),
            "timestamp": get_timestamp()
        }

        return success_response(metrics)

    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


# ============================================================================
# Initialization Function
# ============================================================================

def init_routes(app, twins_data, commands_data, telemetry_data, mqtt_client_ref=None):
    """
    Initialize routes with data store references
    Call this from app.py to inject data stores
    """
    global twins_store, commands_store, telemetry_store, mqtt_client

    twins_store = twins_data
    commands_store = commands_data
    telemetry_store = telemetry_data
    mqtt_client = mqtt_client_ref

    # Register blueprints
    app.register_blueprint(twins_bp)
    app.register_blueprint(commands_bp)
    app.register_blueprint(devices_bp)
    app.register_blueprint(system_bp)

    logger.info("Routes initialized successfully")


# ============================================================================
# Export Blueprints
# ============================================================================

__all__ = [
    'twins_bp',
    'commands_bp',
    'devices_bp',
    'system_bp',
    'telemetry_bp',
    'init_routes'
]