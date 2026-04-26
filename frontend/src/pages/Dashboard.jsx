import { useEffect, useState, useRef } from "react";
import { motion } from "framer-motion";
import { MapContainer, TileLayer, CircleMarker, Polyline, Tooltip } from "react-leaflet";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from "recharts";
import { TrendingUp, TrendingDown, AlertTriangle, DollarSign, Package, Shield } from "lucide-react";
import { api, WS_URL } from "../api";

// ── animated counter ──────────────────────────────────────────────────────────
function Counter({ value, prefix = "", suffix = "", decimals = 0 }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let start = 0;
    const step = value / 40;
    const t = setInterval(() => {
      start += step;
      if (start >= value) { setDisplay(value); clearInterval(t); }
      else setDisplay(start);
    }, 30);
    return () => clearInterval(t);
  }, [value]);
  return <span>{prefix}{decimals ? display.toFixed(decimals) : Math.round(display)}{suffix}</span>;
}

// ── KPI card ─────────────────────────────────────────────────────────────────
function KPI({ label, value, prefix = "", suffix = "", color, icon: Icon, decimals = 0, delay = 0 }) {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className="bg-[#161b27] border border-[#1f2937] rounded-xl p-5">
      <div className="flex justify-between items-start mb-3">
        <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">{label}</span>
        <div className="p-2 rounded-lg bg-white/5"><Icon size={15} className={color}/></div>
      </div>
      <div className={`text-3xl font-bold ${color}`}>
        <Counter value={value} prefix={prefix} suffix={suffix} decimals={decimals}/>
      </div>
    </motion.div>
  );
}

// ── threat card ───────────────────────────────────────────────────────────────
const SEV = {
  Critical: { bg:"bg-red-950", text:"text-red-300", badge:"bg-red-900 text-red-300" },
  High:     { bg:"bg-red-950/60", text:"text-orange-300", badge:"bg-orange-900 text-orange-300" },
  Medium:   { bg:"bg-amber-950/50", text:"text-amber-300", badge:"bg-amber-900 text-amber-300" },
  Low:      { bg:"bg-green-950/50", text:"text-green-300", badge:"bg-green-900 text-green-300" },
};
const ACT_COLOR = { Rerouted:"text-purple-400", Delayed:"text-red-400", "At Risk":"text-yellow-400" };

function ThreatCard({ t, i }) {
  const s = SEV[t.severity] || SEV.Medium;
  return (
    <motion.div initial={{ opacity:0, x:20 }} animate={{ opacity:1, x:0 }}
      transition={{ delay: i*0.1 }}
      className={`${s.bg} border border-[#1f2937] rounded-lg p-3 mb-2`}>
      <div className="flex justify-between items-center mb-1">
        <span className="text-sm font-semibold text-gray-100">{t.title}</span>
        <span className={`text-xs px-2 py-0.5 rounded font-bold uppercase ${s.badge}`}>{t.severity}</span>
      </div>
      <div className="text-xs text-gray-400 mb-1">📍 {t.location}</div>
      {t.detail && <div className="text-xs text-gray-500 mb-2">{t.detail}</div>}
      <div className="flex justify-between text-xs">
        <span className="text-gray-400">🚚 {t.orders} orders</span>
        <span className={`font-semibold ${ACT_COLOR[t.action] || "text-gray-400"}`}>{t.action}</span>
      </div>
    </motion.div>
  );
}

// ── risk colour ───────────────────────────────────────────────────────────────
const riskColor = (r) => r < 0.33 ? "#22c55e" : r < 0.66 ? "#f97316" : "#ef4444";

export default function Dashboard() {
  const [metrics,  setMetrics]  = useState(null);
  const [threats,  setThreats]  = useState([]);
  const [graph,    setGraph]    = useState(null);
  const [ships,    setShips]    = useState([]);
  const wsRef = useRef(null);

  useEffect(() => {
    Promise.all([api.metrics(), api.threats(), api.graph(), api.shipments()])
      .then(([m, th, g, s]) => {
        setMetrics(m);
        setThreats(th.threats || []);
        setGraph(g);
        setShips(s.shipments || []);
      })
      .catch(console.error);

    // WebSocket for live updates
    const ws = new WebSocket(WS_URL);
    ws.onmessage = (e) => {
      const d = JSON.parse(e.data);
      if (d.metrics) setMetrics(d.metrics);
      if (d.threats) setThreats(d.threats);
    };
    wsRef.current = ws;
    return () => ws.close();
  }, []);

  if (!metrics) return (
    <div className="flex items-center justify-center h-64 text-gray-500">
      Loading live data…
    </div>
  );

  const statusData = [
    { name:"In Transit", value: ships.filter(s=>s.status==="In Transit").length, color:"#22c55e" },
    { name:"At Risk",    value: ships.filter(s=>s.status==="At Risk").length,    color:"#f97316" },
    { name:"Delayed",    value: ships.filter(s=>s.status==="Delayed").length,    color:"#ef4444" },
    { name:"Rerouted",   value: ships.filter(s=>s.status==="Rerouted").length,   color:"#a78bfa" },
  ];

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">AI Risk Prediction Overview</h1>
          <p className="text-gray-400 text-sm mt-1">Live monitoring of India logistics infrastructure</p>
        </div>
        <motion.div animate={{ opacity:[1,0.5,1] }} transition={{ repeat:Infinity, duration:2 }}
          className="flex items-center gap-2 bg-green-950 border border-green-800 px-3 py-1.5 rounded-full">
          <span className="w-2 h-2 rounded-full bg-green-400"/>
          <span className="text-green-400 text-xs font-semibold">Live · Open-Meteo</span>
        </motion.div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <KPI label="Total Active Shipments" value={metrics.total_active_shipments}
          color="text-white" icon={Package} delay={0}/>
        <KPI label="Shipments at Risk" value={metrics.shipments_at_risk}
          color="text-red-400" icon={AlertTriangle} delay={0.1}/>
        <KPI label="AI Detected Threats" value={metrics.ai_threats}
          color="text-orange-400" icon={Shield} delay={0.2}/>
        <KPI label="Financial Exposure" value={metrics.financial_exposure_m}
          prefix="₹" suffix="M" decimals={1}
          color="text-white" icon={DollarSign} delay={0.3}/>
      </div>

      {/* Map + Threats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {/* Map — 2/3 width */}
        <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }} transition={{ delay:0.2 }}
          className="col-span-2 bg-[#161b27] border border-[#1f2937] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-[#1f2937] text-xs font-semibold text-gray-400 uppercase tracking-wider">
            🗺 India Logistics Network
          </div>
          {graph && (
            <MapContainer center={[22, 80]} zoom={5} style={{ height:380 }}
              zoomControl={false} attributionControl={false}>
              <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"/>
              {graph.edges.map((e,i) => {
                const src = graph.nodes.find(n=>n.id===e.source);
                const tgt = graph.nodes.find(n=>n.id===e.target);
                if (!src||!tgt) return null;
                return (
                  <Polyline key={i}
                    positions={[[src.lat,src.lon],[tgt.lat,tgt.lon]]}
                    color={riskColor(e.risk)} weight={2} opacity={0.75}>
                    <Tooltip sticky>{e.source}→{e.target} · {(e.risk*100).toFixed(0)}% risk</Tooltip>
                  </Polyline>
                );
              })}
              {graph.nodes.map(n => (
                <CircleMarker key={n.id} center={[n.lat,n.lon]}
                  radius={7} color="#60a5fa" fillColor="#60a5fa" fillOpacity={0.9}>
                  <Tooltip>{n.id} ({n.type})</Tooltip>
                </CircleMarker>
              ))}
            </MapContainer>
          )}
        </motion.div>

        {/* Threats — 1/3 width */}
        <div className="bg-[#161b27] border border-[#1f2937] rounded-xl flex flex-col">
          <div className="px-4 py-3 border-b border-[#1f2937] text-xs font-semibold text-gray-400 uppercase tracking-wider">
            ⚠ Live AI Threat Feed
          </div>
          <div className="flex-1 p-3 overflow-auto">
            {threats.map((t,i) => <ThreatCard key={t.id||i} t={t} i={i}/>)}
          </div>
          {/* Network health */}
          <div className="border-t border-[#1f2937] p-4 space-y-2">
            {[
              ["Cities online",  metrics.n_nodes, "text-white"],
              ["Active routes",  metrics.n_edges, "text-white"],
              ["Avg delay risk", `${Math.round(metrics.avg_risk*100)}%`,
                metrics.avg_risk < 0.33 ? "text-green-400" : metrics.avg_risk < 0.66 ? "text-orange-400" : "text-red-400"],
            ].map(([lbl,val,cls]) => (
              <div key={lbl} className="flex justify-between text-sm">
                <span className="text-gray-400">{lbl}</span>
                <span className={`font-semibold ${cls}`}>{val}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Shipments table + bar chart */}
      <div className="grid grid-cols-3 gap-4">
        {/* Table */}
        <div className="col-span-2 bg-[#161b27] border border-[#1f2937] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-[#1f2937] text-xs font-semibold text-gray-400 uppercase tracking-wider">
            📦 Active Shipments
          </div>
          <div className="overflow-auto max-h-64">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#1f2937]">
                  {["Order ID","Product","Source","Destination","Status","Risk","ETA"].map(h => (
                    <th key={h} className="text-left px-4 py-2 text-xs text-gray-500 font-semibold uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ships.map((s,i) => {
                  const sc = { "In Transit":"text-green-400","At Risk":"text-yellow-400",
                    "Delayed":"text-red-400","Rerouted":"text-purple-400" };
                  return (
                    <motion.tr key={s.id} initial={{ opacity:0 }} animate={{ opacity:1 }}
                      transition={{ delay: i*0.05 }}
                      className="border-b border-[#1a2030] hover:bg-white/[0.02] transition-colors">
                      <td className="px-4 py-2.5 text-blue-400 font-semibold">{s.id}</td>
                      <td className="px-4 py-2.5 text-gray-300">{s.product}</td>
                      <td className="px-4 py-2.5 text-gray-400">{s.source}</td>
                      <td className="px-4 py-2.5 text-gray-400">{s.destination}</td>
                      <td className="px-4 py-2.5">
                        <span className={`text-xs font-semibold ${sc[s.status]||"text-gray-400"}`}>{s.status}</span>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className="text-xs font-bold" style={{ color:riskColor(s.risk) }}>
                          {Math.round(s.risk*100)}%
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-gray-400 text-xs">{s.eta}</td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Status bar chart */}
        <div className="bg-[#161b27] border border-[#1f2937] rounded-xl p-4">
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">
            Shipment Status Breakdown
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={statusData} margin={{ left:-20 }}>
              <XAxis dataKey="name" tick={{ fill:"#6b7280", fontSize:11 }} axisLine={false} tickLine={false}/>
              <YAxis tick={{ fill:"#6b7280", fontSize:11 }} axisLine={false} tickLine={false}/>
              <Bar dataKey="value" radius={[4,4,0,0]}>
                {statusData.map((d,i) => <Cell key={i} fill={d.color}/>)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
