# Docker Stack for Home IoT Telemetry

This directory contains a complete Docker Compose stack for running
the core telemetry infrastructure:

### Included services:
- **Mosquitto (MQTT broker)** – IoT message transport
- **InfluxDB 2.x** – time-series database for metrics and sensor data
- **Grafana** – dashboards and visualization

### Usage

Start the stack:

```bash
docker compose up -d
