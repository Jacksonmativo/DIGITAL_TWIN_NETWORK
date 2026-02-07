#!/usr/bin/env python3
"""
Digital Twin Network - REST API Server
Flask application providing HTTP interface for digital twin operations
"""

import os
import sys
import json
import logging
from datetime import datetime
from functools import wraps
from typing import Dict, List, Optional

from flask import Flask, request, jsonify, Response
from flask_cors import CORS

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configuration
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# In-memory storage for twins (replace with database in production)
twins_store: Dict[str, dict] = {}
commands_store: Dict[str, dict] = {}
telemetry_store: Dict[str, List[dict]] = {}

# Global twin manager reference (will be set when manager starts)
twin_manager = None


# ============================================================================
# Utility Functions
# ============================================================================

def get_timestamp() -> str:
    """Return current timestamp in ISO format"""
    return datetime.utcnow().isoformat() + 'Z'


def generate_command_id() -> str:
    """Generate unique command ID"""
    import uuid
    return f"cmd-{uuid.uuid4().hex[:8]}"


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


# ============================================================================
# Decorators
# ============================================================================

def validate_json(f):
    """Validate that request contains JSON data"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return error_response("Content-Type must be application/json", "INVALID_CONTENT_TYPE", 415)
        return f(*args, **kwargs)
    return decorated_function


def twin_exists(f):
    """Validate that twin exists before processing request"""
    @wraps(f)
    def decorated_function(twin_id, *args, **kwargs):
        if twin_id not in twins_store:
            return error_response(
                f"Twin with ID '{twin_id}' not found",
                "TWIN_NOT_FOUND",
                404
            )
        return f(twin_id, *args, **kwargs)
    return decorated_function


# ============================================================================
# Health & System Endpoints
# ============================================================================

@app.route('/health', methods=['GET'])
@app.route('/api/v1/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    Returns system health status
    """
    health_data = {
        "status": "healthy",
        "service": "digital-twin-api",
        "version": "1.0.0",
        "uptime_seconds": 0,  # TODO: Calculate actual uptime
        "twins_count": len(twins_store),
        "timestamp": get_timestamp()
    }
    return success_response(health_data)


@app.route('/api/v1/system/status', methods=['GET'])
def system_status():
    """
    Get detailed system status
    """
    status_data = {
        "twins": {
            "total": len(twins_store),
            "active": sum(1 for t in twins_store.values() if t.get("status") == "online"),
            "offline": sum(1 for t in twins_store.values() if t.get("status") == "offline")
        },
        "commands": {
            "total": len(commands_store),
            "pending": sum(1 for c in commands_store.values() if c.get("status") == "pending"),
            "completed": sum(1 for c in commands_store.values() if c.get("status") == "completed")
        },
        "telemetry": {
            "devices_reporting": len(telemetry_store),
            "total_messages": sum(len(v) for v in telemetry_store.values())
        }
    }
    return success_response(status_data)


@app.route('/api/v1/system/metrics', methods=['GET'])
def system_metrics():
    """
    Get system performance metrics
    """
    metrics = {
        "memory_usage_mb": 0,  # TODO: Calculate actual memory usage
        "cpu_usage_percent": 0,  # TODO: Calculate actual CPU usage
        "message_rate": 0,  # TODO: Calculate message rate
        "api_requests_total": 0,  # TODO: Track API requests
        "errors_total": 0  # TODO: Track errors
    }
    return success_response(metrics)


# ============================================================================
# Twin Management Endpoints
# ============================================================================

@app.route('/api/v1/twins', methods=['GET'])
def get_twins():
    """
    Get all twins with optional filtering
    Query parameters:
    - type: Filter by device type
    - status: Filter by status (online/offline)
    - limit: Maximum number of results (default: 100)
    - offset: Pagination offset (default: 0)
    """
    # Extract query parameters
    device_type = request.args.get('type')
    status = request.args.get('status')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))

    # Get all twins
    all_twins = list(twins_store.values())

    # Apply filters
    filtered_twins = all_twins
    if device_type:
        filtered_twins = [t for t in filtered_twins if t.get('type') == device_type]
    if status:
        filtered_twins = [t for t in filtered_twins if t.get('status') == status]

    # Apply pagination
    total_count = len(filtered_twins)
    paginated_twins = filtered_twins[offset:offset + limit]

    response_data = {
        "count": len(paginated_twins),
        "total": total_count,
        "offset": offset,
        "limit": limit,
        "twins": paginated_twins
    }

    return success_response(response_data)


@app.route('/api/v1/twins/<twin_id>', methods=['GET'])
@twin_exists
def get_twin(twin_id):
    """
    Get detailed information about a specific twin
    """
    twin = twins_store[twin_id]
    return success_response(twin)


@app.route('/api/v1/twins', methods=['POST'])
@validate_json
def create_twin():
    """
    Create a new digital twin
    Request body:
    {
        "id": "sensor-001",
        "type": "temperature_sensor",
        "metadata": {
            "location": "Room A",
            "manufacturer": "SensorCorp"
        }
    }
    """
    data = request.get_json()

    # Validate required fields
    if 'id' not in data:
        return error_response("Field 'id' is required", "MISSING_FIELD")
    if 'type' not in data:
        return error_response("Field 'type' is required", "MISSING_FIELD")

    twin_id = data['id']

    # Check if twin already exists
    if twin_id in twins_store:
        return error_response(
            f"Twin with ID '{twin_id}' already exists",
            "TWIN_ALREADY_EXISTS",
            409
        )

    # Create twin
    twin = {
        "id": twin_id,
        "type": data['type'],
        "state": {},
        "properties": data.get('properties', {}),
        "metadata": data.get('metadata', {}),
        "status": "offline",
        "created_at": get_timestamp(),
        "last_updated": get_timestamp()
    }

    twins_store[twin_id] = twin
    logger.info(f"Created twin: {twin_id}")

    return success_response(twin, "Twin created successfully", 201)


@app.route('/api/v1/twins/<twin_id>', methods=['PUT'])
@twin_exists
@validate_json
def update_twin(twin_id):
    """
    Update twin metadata and properties (not state)
    """
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


@app.route('/api/v1/twins/<twin_id>', methods=['DELETE'])
@twin_exists
def delete_twin(twin_id):
    """
    Delete a twin
    """
    twin = twins_store.pop(twin_id)

    # Clean up associated data
    if twin_id in telemetry_store:
        del telemetry_store[twin_id]

    logger.info(f"Deleted twin: {twin_id}")
    return success_response({"id": twin_id}, "Twin deleted successfully")


# ============================================================================
# Twin State Endpoints
# ============================================================================

@app.route('/api/v1/twins/<twin_id>/state', methods=['GET'])
@twin_exists
def get_twin_state(twin_id):
    """
    Get current state of a twin
    """
    twin = twins_store[twin_id]
    state_data = {
        "twin_id": twin_id,
        "state": twin.get('state', {}),
        "status": twin.get('status', 'unknown'),
        "last_updated": twin.get('last_updated')
    }
    return success_response(state_data)


@app.route('/api/v1/twins/<twin_id>/state', methods=['PUT'])
@twin_exists
@validate_json
def update_twin_state(twin_id):
    """
    Update twin state (typically called by twin manager, not external clients)
    Request body:
    {
        "temperature": 23.5,
        "humidity": 65
    }
    """
    data = request.get_json()
    twin = twins_store[twin_id]

    # Update state
    twin['state'].update(data)
    twin['last_updated'] = get_timestamp()
    twin['status'] = 'online'

    logger.info(f"Updated state for twin: {twin_id}")
    return success_response(twin['state'], "State updated successfully")


# ============================================================================
# Telemetry Endpoints
# ============================================================================

@app.route('/api/v1/twins/<twin_id>/telemetry', methods=['GET'])
@twin_exists
def get_telemetry(twin_id):
    """
    Get telemetry history for a twin
    Query parameters:
    - start: Start timestamp (ISO format)
    - end: End timestamp (ISO format)
    - limit: Maximum number of records (default: 100)
    """
    limit = int(request.args.get('limit', 100))
    start = request.args.get('start')
    end = request.args.get('end')

    # Get telemetry data
    telemetry = telemetry_store.get(twin_id, [])

    # Apply time filtering (simplified - in production use proper datetime comparison)
    filtered_telemetry = telemetry[-limit:]

    response_data = {
        "twin_id": twin_id,
        "count": len(filtered_telemetry),
        "telemetry": filtered_telemetry
    }

    return success_response(response_data)


@app.route('/api/v1/twins/<twin_id>/telemetry', methods=['POST'])
@twin_exists
@validate_json
def add_telemetry(twin_id):
    """
    Add telemetry data for a twin (typically used by twin manager)
    Request body:
    {
        "temperature": 23.5,
        "humidity": 65,
        "timestamp": "2024-02-05T10:30:00Z"
    }
    """
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

    # Keep only last 1000 records per twin (memory management)
    if len(telemetry_store[twin_id]) > 1000:
        telemetry_store[twin_id] = telemetry_store[twin_id][-1000:]

    return success_response(telemetry_record, "Telemetry added successfully", 201)


# ============================================================================
# Command Endpoints
# ============================================================================

@app.route('/api/v1/twins/<twin_id>/command', methods=['POST'])
@twin_exists
@validate_json
def send_command(twin_id):
    """
    Send a command to a device via its twin
    Request body:
    {
        "action": "set_temperature",
        "parameters": {
            "value": 25,
            "unit": "celsius"
        }
    }
    """
    data = request.get_json()

    # Validate required fields
    if 'action' not in data:
        return error_response("Field 'action' is required", "MISSING_FIELD")

    # Generate command ID
    command_id = generate_command_id()

    # Create command record
    command = {
        "command_id": command_id,
        "twin_id": twin_id,
        "action": data['action'],
        "parameters": data.get('parameters', {}),
        "status": "pending",
        "created_at": get_timestamp(),
        "updated_at": get_timestamp()
    }

    # Store command
    commands_store[command_id] = command

    # TODO: Publish command to MQTT for device to receive
    # This would require access to the MQTT client
    # mqtt_client.publish(f"device/{twin_id}/command", json.dumps(command))

    logger.info(f"Created command {command_id} for twin {twin_id}")

    return success_response(command, "Command created successfully", 201)


@app.route('/api/v1/twins/<twin_id>/commands', methods=['GET'])
@twin_exists
def get_twin_commands(twin_id):
    """
    Get all commands sent to a twin
    """
    twin_commands = [
        cmd for cmd in commands_store.values()
        if cmd['twin_id'] == twin_id
    ]

    response_data = {
        "twin_id": twin_id,
        "count": len(twin_commands),
        "commands": twin_commands
    }

    return success_response(response_data)


@app.route('/api/v1/commands/<command_id>', methods=['GET'])
def get_command(command_id):
    """
    Get command status by command ID
    """
    if command_id not in commands_store:
        return error_response(
            f"Command with ID '{command_id}' not found",
            "COMMAND_NOT_FOUND",
            404
        )

    command = commands_store[command_id]
    return success_response(command)


@app.route('/api/v1/commands/<command_id>', methods=['PUT'])
@validate_json
def update_command_status(command_id):
    """
    Update command status (typically called by device or twin manager)
    Request body:
    {
        "status": "completed",
        "result": {
            "success": true,
            "execution_time": 0.5
        }
    }
    """
    if command_id not in commands_store:
        return error_response(
            f"Command with ID '{command_id}' not found",
            "COMMAND_NOT_FOUND",
            404
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

    return success_response(command, "Command status updated")


# ============================================================================
# Device Management Endpoints
# ============================================================================

@app.route('/api/v1/devices', methods=['GET'])
def get_devices():
    """
    Get list of all connected devices
    (In this implementation, devices are the same as twins)
    """
    devices = [
        {
            "device_id": twin['id'],
            "type": twin['type'],
            "status": twin.get('status', 'unknown'),
            "last_seen": twin.get('last_updated')
        }
        for twin in twins_store.values()
    ]

    response_data = {
        "count": len(devices),
        "devices": devices
    }

    return success_response(response_data)


@app.route('/api/v1/devices/<device_id>/health', methods=['GET'])
@twin_exists
def get_device_health(device_id):
    """
    Get device health status
    """
    twin = twins_store[device_id]

    health_data = {
        "device_id": device_id,
        "status": twin.get('status', 'unknown'),
        "last_updated": twin.get('last_updated'),
        "uptime_seconds": 0,  # TODO: Calculate actual uptime
        "message_count": len(telemetry_store.get(device_id, [])),
        "error_count": 0  # TODO: Track errors
    }

    return success_response(health_data)


# ============================================================================
# Statistics & Analytics Endpoints
# ============================================================================

@app.route('/api/v1/twins/<twin_id>/statistics', methods=['GET'])
@twin_exists
def get_twin_statistics(twin_id):
    """
    Get statistical summary for a twin
    """
    telemetry = telemetry_store.get(twin_id, [])

    # Calculate basic statistics (simplified)
    stats = {
        "twin_id": twin_id,
        "message_count": len(telemetry),
        "first_message": telemetry[0]['timestamp'] if telemetry else None,
        "last_message": telemetry[-1]['timestamp'] if telemetry else None,
        "average_values": {},  # TODO: Calculate averages
        "min_values": {},  # TODO: Calculate minimums
        "max_values": {}  # TODO: Calculate maximums
    }

    return success_response(stats)


# ============================================================================
# Batch Operations
# ============================================================================

@app.route('/api/v1/twins/batch', methods=['POST'])
@validate_json
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
    data = request.get_json()

    if 'twins' not in data or not isinstance(data['twins'], list):
        return error_response("Field 'twins' must be a list", "INVALID_FORMAT")

    created = []
    errors = []

    for twin_data in data['twins']:
        try:
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
                "status": "offline",
                "created_at": get_timestamp(),
                "last_updated": get_timestamp()
            }

            twins_store[twin_id] = twin
            created.append(twin_id)

        except KeyError as e:
            errors.append({
                "id": twin_data.get('id', 'unknown'),
                "error": f"Missing required field: {e}"
            })

    response_data = {
        "created_count": len(created),
        "error_count": len(errors),
        "created": created,
        "errors": errors
    }

    status_code = 201 if created else 400
    return success_response(response_data, "Batch operation completed", status_code)


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return error_response("Resource not found", "NOT_FOUND", 404)


@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors"""
    return error_response("Method not allowed", "METHOD_NOT_ALLOWED", 405)


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal error: {error}")
    return error_response("Internal server error", "INTERNAL_ERROR", 500)


@app.errorhandler(Exception)
def handle_exception(error):
    """Handle all uncaught exceptions"""
    logger.exception(f"Unhandled exception: {error}")
    return error_response(str(error), "UNHANDLED_EXCEPTION", 500)


# ============================================================================
# Main Entry Point
# ============================================================================

def init_sample_data():
    """Initialize with some sample twins for testing"""
    sample_twins = [
        {
            "id": "sensor-001",
            "type": "temperature_sensor",
            "metadata": {
                "location": "Room A",
                "manufacturer": "SensorCorp"
            }
        },
        {
            "id": "sensor-002",
            "type": "humidity_sensor",
            "metadata": {
                "location": "Room B",
                "manufacturer": "SensorCorp"
            }
        },
        {
            "id": "light-001",
            "type": "smart_light",
            "metadata": {
                "location": "Living Room",
                "manufacturer": "LightTech"
            }
        }
    ]

    for twin_data in sample_twins:
        twin_id = twin_data['id']
        twin = {
            "id": twin_id,
            "type": twin_data['type'],
            "state": {},
            "properties": {},
            "metadata": twin_data['metadata'],
            "status": "offline",
            "created_at": get_timestamp(),
            "last_updated": get_timestamp()
        }
        twins_store[twin_id] = twin

    logger.info(f"Initialized {len(sample_twins)} sample twins")


def main():
    """Main function to run the Flask app"""
    # Load configuration from environment
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

    # Initialize sample data
    init_sample_data()

    # Log startup information
    logger.info("="*60)
    logger.info("Digital Twin Network - REST API Server")
    logger.info("="*60)
    logger.info(f"Host: {host}")
    logger.info(f"Port: {port}")
    logger.info(f"Debug: {debug}")
    logger.info("="*60)
    logger.info("Available endpoints:")
    logger.info("  GET    /health")
    logger.info("  GET    /api/v1/twins")
    logger.info("  POST   /api/v1/twins")
    logger.info("  GET    /api/v1/twins/<twin_id>")
    logger.info("  PUT    /api/v1/twins/<twin_id>")
    logger.info("  DELETE /api/v1/twins/<twin_id>")
    logger.info("  GET    /api/v1/twins/<twin_id>/state")
    logger.info("  PUT    /api/v1/twins/<twin_id>/state")
    logger.info("  POST   /api/v1/twins/<twin_id>/command")
    logger.info("  GET    /api/v1/twins/<twin_id>/telemetry")
    logger.info("="*60)

    # Run the Flask application
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    main()