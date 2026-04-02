# 🌳 GIS_Projekts: 3 Billion Trees Tracker

A spatial data visualization platform designed to represent the progress of the EU's **3 Billion Trees** initiative. This project integrates modern WebGIS technologies to map afforestation and reforestation efforts across Europe.

---

## 🎯 Project Overview
The goal of this project is to provide a spatial representation of trees planted under the [3 Billion Trees Pledge](https://forest.eea.europa.eu/policy-and-reporting/3-billion-trees). By 2030, the EU aims to plant 3 billion additional trees to boost biodiversity and climate resilience. 

This application serves as a dashboard to visualize:
* **Planting Action Sites:** Specific locations where trees have been added.
* **Regional Progress:** Density of planting per country/NUTS regions.
* **Ecological Data:** Species diversity and land use types.

---

## 🛠️ Technical Stack
The project is containerized for easy deployment and uses a robust geospatial backend:

* **Docker:** Orchestrates the entire environment (Python, DB, Server).
* **Python:** Used for data processing, scraping official EEA data, and automation.
* **PostGIS:** The spatial database (PostgreSQL extension) for storing tree coordinates and polygons.
* **GeoServer:** The map server that publishes the data as OGC Web Services (WMS/WFS).

---

## 🏗️ System Architecture
1.  **Data Ingestion:** Python scripts fetch data from the EEA's Forest Information System.
2.  **Storage:** Cleaned spatial data is pushed into a **PostGIS** database.
3.  **Publishing:** **GeoServer** connects to PostGIS to serve map tiles.
4.  **Frontend:** A web map (Leaflet/OpenLayers) displays the GeoServer layers.

---

## 🚀 Getting Started

### 1. Prerequisites
* Docker & Docker Compose installed.
* Basic understanding of SQL and GIS.

* clone repo and run docker
