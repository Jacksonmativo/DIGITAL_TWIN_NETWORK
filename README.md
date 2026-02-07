# Digital Twin Network - Research Project Summary

A comprehensive guide to building an IoT Digital Twin Network using MQTT, Python, and Flask on Linux with Visual Studio Code.

## 📋 Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Running the System](#running-the-system)
- [Usage Examples](#usage-examples)
- [API Documentation](#api-documentation)
- [Troubleshooting](#troubleshooting)
- [Next Steps](#next-steps)
 - [Project Phases](#project-phases)
---

## 🧭 Project Phases

See [PHASE.MD](PHASE.MD) for full details. Summary:

- **Phase 1 (Now)**
   - MQTT → Twin Engine
   - Flask API

- **Phase 2**
   - Twin Engine → Kafka (telemetry + events)

- **Phase 3**
   - Kafka → DB → Grafana dashboards

---

## 🧠 Network Behavior Modeling for AI Security

A core objective of this project is to **twin real and simulated networks** in order to generate high-quality behavioral data for **training AI models to detect malicious and anomalous network activity**.

Instead of inspecting packet payloads, the system focuses on **traffic behavior and metadata**, which is safer, scalable, and aligned with modern defensive security practices.

---

### 🔹 Normal Network Behavior (Baseline)

The Digital Twin learns and models what *healthy* network traffic looks like, including:

- **Packet rate** – Average and peak packets per second
- **Protocol distribution** – Typical ratios of TCP / UDP / ICMP traffic
- **Session duration** – Normal connection lifetimes
- **Latency & jitter** – Expected response times and variation
- **Retry patterns** – Normal retransmission behavior
- **DNS request frequency** – Standard domain resolution patterns
- **TLS handshake behavior** – Legitimate encrypted session setup characteristics

These metrics form the **baseline profile** used by the AI model.

---

### 🔹 Abnormal / Suspicious Network Behavior

The system also models and simulates deviations from the baseline, which may indicate malicious or misconfigured activity:

- **Sudden traffic spikes** – Abnormal surges in packet rate
- **Unusual protocol mix** – Unexpected protocol ratios
- **Repeated failed connections** – Authentication or connection failures
- **High entropy payload sizes** – Indicators of obfuscation or tunneling
- **Timing anomalies** – Irregular or unnatural traffic intervals
- **Connection floods** – Excessive simultaneous connections
- **Beacon-like periodic traffic** – Repeated, timed outbound signals

These behaviors are used to **label events**, **train anomaly-detection models**, and **evaluate AI predictions**.

---

### 🧪 Why Digital Network Twins Matter

By using Digital Network Twins, the project enables:

- Safe and controlled simulation of abnormal traffic
- Accurate labeling of normal vs suspicious behavior
- Repeatable experiments for AI training and evaluation
- Continuous retraining as network conditions evolve

This approach supports **behavior-based threat detection**, which is more resilient than traditional signature-based systems.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Digital Twin Network                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐         ┌──────────────┐                  │
│  │   Physical   │         │   Physical   │                  │
│  │   Device 1   │         │   Device 2   │                  │
│  │  (Simulated) │         │  (Simulated) │                  │
│  └──────┬───────┘         └──────┬───────┘                  │
│         │                        │                           │
│         │    MQTT Publish        │                           │
│         ▼                        ▼                           │
│  ┌─────────────────────────────────────┐                    │
│  │     MQTT Broker (Mosquitto)         │                    │
│  │   Topics: device/+/telemetry        │                    │
│  │           device/+/command          │                    │
│  └─────────────┬───────────────────────┘                    │
│                │                                             │
│                │    MQTT Subscribe                           │
│                ▼                                             │
│  ┌─────────────────────────────────────┐                    │
│  │      Digital Twin Engine            │                    │
│  │   - State synchronization           │                    │
│  │   - Data validation                 │                    │
│  │   - Twin model management           │                    │
│  └─────────────┬───────────────────────┘                    │
│                │                                             │
│                │    REST API                                 │
│                ▼                                             │
│  ┌─────────────────────────────────────┐                    │
│  │        Flask REST API               │                    │
│  │   - GET /twins                      │                    │
│  │   - GET /twins/{id}                 │                    │
│  │   - POST /twins/{id}/command        │                    │
│  └─────────────┬───────────────────────┘                    │
│                │                                             │
│                │    HTTP                                     │
│                ▼                                             │
│  ┌─────────────────────────────────────┐                    │
│  │      Web Dashboard                  │                    │
│  │   - Real-time monitoring            │                    │
│  │   - Device control                  │                    │
│  │   - Data visualization              │                    │
│  └─────────────────────────────────────┘                    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Prerequisites

### System Requirements

- **Operating System**: Linux (Ubuntu 20.04+ / Debian 10+ recommended)
- **RAM**: Minimum 2GB
- **Disk Space**: 500MB free space
- **Network**: Internet connection for initial setup

### Required Software

- **Python**: Version 3.8 or higher
- **pip**: Python package manager
- **VS Code**: Latest stable version
- **Git**: For version control (optional)

---

## 🚀 Installation

### Step 1: Update System Packages

Open your terminal and update the package list:

```bash
sudo apt update
sudo apt upgrade -y
```

### Step 2: Install Core Dependencies

Install Python, pip, and the Mosquitto MQTT broker:

```bash
# Install Python and pip
sudo apt install python3 python3-pip -y

# Install Mosquitto MQTT Broker and clients
sudo apt install mosquitto mosquitto-clients -y

# Verify installations
python3 --version
pip3 --version
mosquitto -h
```

### Step 3: Install Python Libraries

Install required Python packages:

```bash
# Core libraries
pip3 install paho-mqtt flask

# Additional useful libraries
pip3 install flask-cors requests python-dotenv
```

### Step 4: Configure Mosquitto MQTT Broker

Enable and start the Mosquitto service:

```bash
# Start Mosquitto service
sudo systemctl start mosquitto

# Enable Mosquitto to start on boot
sudo systemctl enable mosquitto

# Check service status
sudo systemctl status mosquitto
```

Create a basic Mosquitto configuration (optional):

```bash
sudo nano /etc/mosquitto/conf.d/custom.conf
```

Add the following content:

```conf
listener 1883
allow_anonymous true
```

Restart Mosquitto:

```bash
sudo systemctl restart mosquitto
```

### Step 5: Install VS Code Extensions

Open VS Code and install these extensions:

1. **Python** (ms-python.python)
   - Provides Python language support
   - IntelliSense, linting, debugging

2. **Docker** (ms-azuretools.vscode-docker)
   - Container management
   - Dockerfile support

3. **Remote - SSH** (ms-vscode-remote.remote-ssh)
   - Connect to remote Linux servers
   - Remote development

4. **IoT Device Simulator** (vsciot-vscode.vscode-iot-device-cube-sdk)
   - Simulate IoT devices
   - Test MQTT connections

**Installation Methods:**

**Via VS Code UI:**
- Press `Ctrl+Shift+X`
- Search for each extension
- Click "Install"

**Via Command Line:**

```bash
code --install-extension ms-python.python
code --install-extension ms-azuretools.vscode-docker
code --install-extension ms-vscode-remote.remote-ssh
code --install-extension vsciot-vscode.vscode-iot-device-cube-sdk
```

---

## 📁 Project Structure

Create the project directory structure:

```bash
mkdir -p digital-twin-network/{devices,twins,broker,api,dashboard}
cd digital-twin-network
```

### Complete Directory Layout

```
digital-twin-network/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables
├── .gitignore               # Git ignore file
│
├── devices/                 # Physical device simulators
│   ├── __init__.py
│   ├── device_simulator.py  # Main device simulator
│   ├── sensor_device.py     # Temperature sensor example
│   └── actuator_device.py   # Light control example
│
├── twins/                   # Digital twin models
│   ├── __init__.py
│   ├── twin_model.py        # Twin data model
│   ├── twin_manager.py      # Twin lifecycle management
│   └── schemas/             # JSON schemas for twins
│       ├── sensor_twin.json
│       └── actuator_twin.json
│
├── broker/                  # MQTT configuration
│   ├── mqtt_client.py       # MQTT client wrapper
│   ├── topic_manager.py     # Topic routing logic
│   └── mosquitto.conf       # Custom Mosquitto config
│
├── api/                     # REST API
│   ├── __init__.py
│   ├── app.py              # Flask application
│   ├── routes.py           # API endpoints
│   └── models.py           # Data models
│
└── dashboard/              # Visualization
    ├── index.html          # Main dashboard page
    ├── static/
    │   ├── css/
    │   │   └── style.css
    │   └── js/
    │       └── app.js      # Frontend logic
    └── templates/
        └── base.html
```

### File Purposes

| Directory | Purpose |
|-----------|---------|
| `devices/` | Simulates physical IoT devices sending telemetry data |
| `twins/` | Manages digital twin models and state synchronization |
| `broker/` | Handles MQTT communication and message routing |
| `api/` | Provides REST API for external applications |
| `dashboard/` | Web interface for monitoring and control |

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
nano .env
```

Add the following configuration:

```env
# MQTT Broker Configuration
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_KEEPALIVE=60

# Flask API Configuration
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=True

# Digital Twin Configuration
TWIN_UPDATE_INTERVAL=5
MAX_TWINS=100
DATA_RETENTION_DAYS=30

# Logging
LOG_LEVEL=INFO
LOG_FILE=digital_twin.log
```

### Requirements File

Create `requirements.txt`:

```bash
nano requirements.txt
```

Add dependencies:

```
paho-mqtt==1.6.1
flask==2.3.0
flask-cors==4.0.0
requests==2.31.0
python-dotenv==1.0.0
```

Install all requirements:

```bash
pip3 install -r requirements.txt
```

---

## 🏃 Running the System

### Step 1: Verify MQTT Broker

Test the MQTT broker is running:

```bash
# Subscribe to test topic (Terminal 1)
mosquitto_sub -h localhost -t "test/topic"

# Publish to test topic (Terminal 2)
mosquitto_pub -h localhost -t "test/topic" -m "Hello Digital Twin!"
```

You should see "Hello Digital Twin!" appear in Terminal 1.

### Step 2: Start the Digital Twin Engine

```bash
cd digital-twin-network
python3 twins/twin_manager.py
```

### Step 3: Launch Device Simulators

In a new terminal:

```bash
python3 devices/device_simulator.py
```

### Step 4: Start the REST API

In another terminal:

```bash
python3 api/app.py
```

The API will be available at `http://localhost:5000`

### Step 5: Open the Dashboard

```bash
cd dashboard
python3 -m http.server 8080
```

Access the dashboard at `http://localhost:8080`

---

## 💡 Usage Examples

### Monitoring a Device Twin via API

```bash
# Get all twins
curl http://localhost:5000/twins

# Get specific twin
curl http://localhost:5000/twins/sensor-001

# Send command to device
curl -X POST http://localhost:5000/twins/light-001/command \
  -H "Content-Type: application/json" \
  -d '{"action": "turn_on", "brightness": 75}'
```

### Publishing Device Data via MQTT

```bash
# Publish temperature reading
mosquitto_pub -h localhost \
  -t "device/sensor-001/telemetry" \
  -m '{"temperature": 23.5, "humidity": 65, "timestamp": 1234567890}'

# Subscribe to device commands
mosquitto_sub -h localhost -t "device/+/command"
```

### Python Client Example

```python
import paho.mqtt.client as mqtt
import json

# Connect to broker
client = mqtt.Client()
client.connect("localhost", 1883, 60)

# Publish telemetry
data = {
    "device_id": "sensor-001",
    "temperature": 24.3,
    "humidity": 62
}
client.publish("device/sensor-001/telemetry", json.dumps(data))
```

---

## 📚 API Documentation

### Base URL
```
http://localhost:5000/api/v1
```

### Endpoints

#### Get All Twins
```
GET /twins
```
**Response:**
```json
{
  "count": 2,
  "twins": [
    {
      "id": "sensor-001",
      "type": "temperature_sensor",
      "state": {
        "temperature": 23.5,
        "humidity": 65
      },
      "last_updated": "2024-02-05T10:30:00Z"
    }
  ]
}
```

#### Get Single Twin
```
GET /twins/{twin_id}
```

#### Send Command
```
POST /twins/{twin_id}/command
Content-Type: application/json

{
  "action": "set_temperature",
  "value": 25
}
```

#### Update Twin State
```
PUT /twins/{twin_id}/state
Content-Type: application/json

{
  "temperature": 24.0,
  "humidity": 68
}
```

---

## 🔧 Troubleshooting

### Common Issues

**1. Mosquitto fails to start**
```bash
# Check service status
sudo systemctl status mosquitto

# View logs
sudo journalctl -u mosquitto -f

# Verify port is not in use
sudo netstat -tlnp | grep 1883
```

**2. Python module not found**
```bash
# Reinstall packages
pip3 install --upgrade -r requirements.txt

# Check Python path
python3 -c "import sys; print(sys.path)"
```

**3. Permission denied errors**
```bash
# Add user to required groups
sudo usermod -aG dialout $USER
sudo usermod -aG mosquitto $USER

# Re-login to apply changes
```

**4. Port already in use**
```bash
# Find process using port 5000
sudo lsof -i :5000

# Kill process if needed
kill -9 <PID>
```

### Testing Connectivity

```bash
# Test MQTT connection
mosquitto_sub -h localhost -t "#" -v

# Test API
curl http://localhost:5000/health

# Check Python imports
python3 -c "import paho.mqtt.client; import flask; print('OK')"
```

---

## 🎓 Next Steps

### Enhancements to Implement

1. **Security**
   - Add MQTT authentication
   - Implement JWT tokens for API
   - Enable TLS/SSL encryption

2. **Database Integration**
   - Store historical data (PostgreSQL/MongoDB)
   - Implement time-series analytics
   - Add data persistence layer

3. **Advanced Features**
   - Real-time WebSocket updates
   - Predictive analytics using ML
   - Automated device discovery
   - Alert and notification system

4. **Scalability**
   - Docker containerization
   - Kubernetes orchestration
   - Load balancing for API
   - Distributed MQTT brokers

5. **Monitoring**
   - Add Prometheus metrics
   - Grafana dashboards
   - System health checks
   - Performance monitoring

### Learning Resources

- [MQTT Protocol Specification](http://mqtt.org/)
- [Eclipse Mosquitto Documentation](https://mosquitto.org/documentation/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Digital Twin Consortium](https://www.digitaltwinconsortium.org/)

---

## 📄 License

MIT License - Feel free to use and modify for your projects.

## 🤝 Contributing

Contributions welcome! Please submit pull requests or open issues for improvements.


*Last Updated: February 2026*# DIGITAL_TWIN_NETWORK
# DIGITAL_TWIN_NETWORK
