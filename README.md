🏡 Home IoT Telemetry – DevOps/SRE Portfolio Project

Author: Piotr Czerewko
Tech stack: Linux • Docker • MQTT • ESPHome • Modbus • ESP32 • InfluxDB • Grafana • Home Assistant • YAML • Jinja • GitHub Actions • IaC • Observability

🚀 Project Overview

This repository documents my practical work as a DevOps/SRE engineer using a real home automation environment.
I use my heat pump system (Haier/Kaisai), energy meters, ESP32 devices and Home Assistant as a real-world platform for:

Telemetry ingestion

Monitoring & alerting

Data analytics

Edge computing (ESP32/Modbus)

Infrastructure-as-Code (IaC)

CI/CD automation

This is a living project — continuously expanding and used as my DevOps portfolio.

📦 Key Features
🧊 Heat Pump Telemetry

Supply temperature (TWO)

Return temperature (TWI)

Compressor frequency (FACT Hz)

Outdoor temperature

ΔT (TWO – TWI)

Heat output estimation (kW)

COP (instant, daily, seasonal)

Defrost event detection

Modulation stability analysis

⚡ Energy Monitoring

Energy consumption from Zamel LIW-01

Power usage charts

InfluxDB storage

Grafana dashboards

Cost estimation & trends

🔧 Edge Computing (ESP32 + Modbus)

RS485/UART communication

Reading Modbus registers from heat pump

Real-time monitoring (power, flow, internal temps)

Publishing data to HA & InfluxDB

ESPHome-based firmware

🔥 Home Assistant Automations (IoT SRE)

Defrost alarm

Low COP alarm

ΔT instability detector

Missing data alerts

Automations built as IaC (YAML/Jinja)

🐳 DevOps Tooling

Docker Compose stack (Influx, Grafana, MQTT, Proxy)

YAML-based configuration (IaC)

GitHub Actions CI pipeline:

YAML validation

Home Assistant config check

ESPHome config test

Markdown linting

📂 Repository Structure
home-iot-telemetry/
│
├── home_assistant/
│   ├── configuration.yaml
│   ├── templates/
│   │   ├── sensor_deltaT.yaml
│   │   ├── sensor_cop.yaml
│   │   └── sensor_defrost_detector.yaml
│   ├── automations/
│   │   └── alert_defrost.yaml
│   └── dashboards/
│       └── heat_pump_dashboard.yaml
│
├── esp32_modbus/
│   ├── esp32_modbus_monitor.yaml
│   ├── wiring_diagram.png
│   └── README.md
│
├── ha_sensor_definitions/
│   ├── haier/
│   │   ├── twi.yaml
│   │   ├── two.yaml
│   │   ├── frequency.yaml
│   │   └── tao.yaml
│   └── zamel/
│       └── electricity_meter.yaml
│
├── analysis/
│   ├── graphs/
│   │   ├── modulation-pattern.png
│   │   ├── deltaT-stability.png
│   │   ├── defrosts.png
│   │   └── cop_vs_temp.png
│   ├── notebooks/
│   │   └── deltaT_analysis.ipynb
│   └── raw_exports/
│       └── history.csv
│
├── docker/
│   ├── docker-compose.influx.yml
│   ├── docker-compose.grafana.yml
│   ├── docker-compose.mqtt.yml
│   └── env.sample
│
└── README.md

📈 Data Analysis Modules
🔹 Compressor Modulation Analysis

Tracking FACT Hz over time to detect:

stable modulation

micro-taktowanie

overdrive cycles

post-defrost behavior

🔹 ΔT Stability Analysis

Monitoring hydraulic conditions and flow efficiency.

🔹 COP Calculation

Instant COP

Daily COP

Heating vs outdoor temperature curve

🔹 Defrost Event Detection

Built using:

FACT jump → 80 Hz

sudden drop of TWO & TWI

rise in Tao

characteristic ΔT pattern

🔧 ESP32 Modbus Module

This module will expose:

Heat pump live electrical power (W)

Flow rate (L/min)

Internal coil temperatures

Four-way valve status

Defrost mode status

Error codes

Firmware: ESPHome
Transport: UART → RS485 → Modbus RTU

🧪 CI/CD – GitHub Actions (Planned)

YAML syntax checker

Home Assistant configuration linter

ESPHome firmware validator (esphome config)

Markdown linter

Automated deployment of Grafana dashboards

🧭 Roadmap
✔ Phase 1 – Telemetry (in progress)

HA sensors

COP calculation

ΔT logic

CSV-based analytics

⬜ Phase 2 – ESP32 Modbus Integration

Reading HP registers

Power measurement

InfluxDB ingestion

⬜ Phase 3 – Full Grafana Monitoring

Master dashboard

Alerting

⬜ Phase 4 – CI/CD Automation

GitHub Actions

Validation pipeline

⬜ Phase 5 – Predictive COP Model (optional)

ML model for COP prediction based on weather

📬 Notes

This repository grows continuously as I expand my home automation system and use it as a practical playground for DevOps/SRE concepts.

If you’re a recruiter, engineer, or colleague viewing this — welcome!
This project reflects my approach to observability, automation, and system thinking in the IoT/devops space.

🔥 END OF README 🔥
