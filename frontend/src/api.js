import axios from "axios";

const BASE = "http://localhost:8000";

export const api = {
  metrics:    ()          => axios.get(`${BASE}/api/metrics`).then(r => r.data),
  graph:      ()          => axios.get(`${BASE}/api/graph`).then(r => r.data),
  nodes:      ()          => axios.get(`${BASE}/api/nodes`).then(r => r.data),
  shipments:  ()          => axios.get(`${BASE}/api/shipments`).then(r => r.data),
  threats:    ()          => axios.get(`${BASE}/api/threats`).then(r => r.data),
  analytics:  ()          => axios.get(`${BASE}/api/analytics`).then(r => r.data),
  weather:    (city)      => axios.get(`${BASE}/api/weather/${city}`).then(r => r.data),
  aftership:  ()          => axios.get(`${BASE}/api/realdata/aftership`).then(r => r.data),
  shiprocket: ()          => axios.get(`${BASE}/api/realdata/shiprocket`).then(r => r.data),
  predict:    (body)      => axios.post(`${BASE}/api/predict`, body).then(r => r.data),
  simulate:   (body)      => axios.post(`${BASE}/api/simulate`, body).then(r => r.data),
};

export const WS_URL = "ws://localhost:8000/ws/live";
