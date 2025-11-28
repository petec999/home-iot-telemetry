# 🏠 Home IoT Telemetry  
**Heat Pump Analysis • Modbus Telemetry • Home Assistant • ESPHome • InfluxDB • Grafana**

This repository collects all configuration, automation and analysis tools used for full telemetry of a Haier heat pump, floor heating, Zamel power meter, and ESP32 Modbus monitoring.  
It serves as a complete end-to-end system combining **data acquisition**, **signal processing**, **automation**, and **visual analytics**.

---

## 📦 Features

### ✔ Real-time telemetry
- Water IN / Water OUT temperatures  
- Compressor frequency (FACT Hz)  
- Outdoor temperature  
- Internal room temperatures  
- Flow & ΔT analysis  
- Zamel Liw-01 electricity meter (power draw)  
- COP calculation (real energy-based)  

### ✔ Automations
- Defrost event detection  
- Alerts (HA + mobile notifications)  
- Heat curve tuning  
- Flow stability checks  

### ✔ Visualization & Analysis
- Grafana dashboards  
- Custom Home Assistant dashboards  
- Jupyter notebooks for deep analysis  
- CSV exports of raw time series  

### ✔ Hardware
- Haier Heat Pump (PAN + indoor unit)  
- Zamel Liw-01 energy meter  
- ESP32 Modbus monitoring node  
- MQTT, InfluxDB, Grafana stack  
- Home Assistant integrations  

---

# 📁 Repository Structure

```text
home-iot-telemetry/
├── home_assistant/
│   ├── configuration.yaml
│   ├── templates/
│   │   ├── sensor_deltaT.yaml
│   │   ├── sensor_cop.yaml
│   │   ├── sensor_defrost_detector.yaml
│   ├── automations/
│   │   └── alert_defrost.yaml
│   └── dashboards/
│       └── heat_pump_dashboard.yaml
│
├── esp32_modbus/
│   ├── esp32_modbus_monitor.yaml
│   └── wiring_diagram.png
│
├── haier/
│   ├── twi.yaml
│   ├── two.yaml
│   ├── frequency.yaml
│   └── tao.yaml
│
├── zamel/
│   └── electricity_meter.yaml
│
├── analysis/
│   ├── graphs/
│   │   ├── modulation-pattern.png
│   │   ├── deltaT-stability.png
│   │   ├── defrosts.png
│   │   └── cop_vs_temp.png
│   ├── deltaT_analysis.ipynb
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
```

---

# 📊 Data Analysis Modules

### 🔧 Compressor Modulation Analysis  
Tracking FACT Hz over time allows detecting:
- stable modulation  
- micro-cycling  
- aggressive cycles  
- defrost events  
- curve mismatch  
- flow restrictions  

### 🧮 COP Calculation  
COP = Heating Power / Electric Power (Zamel Liw-01)  
This repository uses a **sensor template** in Home Assistant to calculate real COP based on instantaneous power readings.

---

# 🧰 ESPHome Modbus Node

The ESP32 Modbus monitor provides access to additional registers unavailable via the standard Haier API:

- superheat / subcool  
- internal sensors  
- valve position  
- compressor load estimate  
- detailed defrost state  

ESPHome YAML and wiring diagrams are included.

---

# 🔌 Docker Stack

This repo includes full docker-compose services:

- **MQTT (Mosquitto)**  
- **InfluxDB 2.x**  
- **Grafana**  
- automatic provisioning templates  
- sample `.env` file  

---

# 📈 Dashboards

### Home Assistant Dashboard  
A complete dashboard for monitoring:
- temperatures  
- compressor frequency  
- defrosts  
- heating curve  
- energy usage  

### Grafana Dashboard  
Time-series analysis including:
- ΔT stability  
- power draw  
- COP over time  
- modulation patterns  
- seasonal performance  

---

# 🚀 Roadmap

- ESPHome UART → more Modbus registers  
- Automatic defrost classifier (AI model)  
- Full heating curve auto-optimizer  
- MQTT → TimescaleDB exporter  
- Cloud sync (optional)  

---

# 🤝 Contributing

Pull requests with:
- new sensors  
- dashboards  
- reverse-engineered registers  
- analysis notebooks  

…are very welcome.

---

# 📜 License

MIT License – feel free to reuse any parts for your own heat pump / IoT telemetry setup.

