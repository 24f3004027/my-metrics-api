# My Metrics API 📊

Welcome to the **My Metrics API** repository. This project was developed as part of the **TDS Graded Assignment 2**. It provides a robust, scalable backend service designed to collect, process, and analyze system or application performance metrics.

---

## 🚀 Features

* **Real-time Data Ingestion**: Seamlessly receive and log incoming metrics.
* **Performance Analytics**: Built-in calculation modules for averages, percentiles, and error rates.
* **Structured Output**: Returns data in clean, standard JSON formats.
* **Lightweight Architecture**: Optimized for low latency and quick setups.

---

## 🛠️ Technology Stack

* **Language**: Python 3.10+
* **Framework**: FastAPI / Flask *(Update based on your chosen framework)*
* **Data Handling**: Pandas / NumPy

---

## 💻 Getting Started

Follow these steps to get your local development environment up and running.

### 1. Clone the Repository
```bash
git clone https://github.com
cd my-metrics-api
```

### 2. Set Up a Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
```bash
python main.py
```
*The server will typically start at `http://127.0.0.1:8000` or `http://127.0.0.1:5000`.*

---

## 🔌 API Endpoints (Quick Reference)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **GET** | `/` | API health check and welcome message |
| **POST** | `/api/v1/metrics` | Submit a new batch of metric data |
| **GET** | `/api/v1/analytics` | Retrieve calculated summary statistics |

---

## 🧑‍💻 Author

* **Ramrup Satpati**
* Developed on: MacBook Air

---

## 📄 License

This project is submitted for academic evaluation. And is Released under the GNU GPLv3 License
All rights reversed.

