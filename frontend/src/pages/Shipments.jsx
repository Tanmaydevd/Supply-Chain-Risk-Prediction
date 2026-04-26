import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "../api";

const STATUS_STYLE = {
  "In Transit":    "bg-blue-900/50 text-blue-300 border-blue-800",
  "At Risk":       "bg-yellow-900/50 text-yellow-300 border-yellow-800",
  "Delayed":       "bg-red-900/50 text-red-300 border-red-800",
  "Rerouted":      "bg-purple-900/50 text-purple-300 border-purple-800",
  "InTransit":     "bg-blue-900/50 text-blue-300 border-blue-800",
  "OutForDelivery":"bg-green-900/50 text-green-300 border-green-800",
  "AttemptFail":   "bg-red-900/50 text-red-300 border-red-800",
  "Exception":     "bg-red-900/50 text-red-300 border-red-800",
};

const riskColor = r => r < 0.33 ? "#22c55e" : r < 0.66 ? "#f97316" : "#ef4444";

function Badge({ status }) {
  const cls = STATUS_STYLE[status] || "bg-gray-800 text-gray-300 border-gray-700";
  return <span className={`text-xs px-2 py-0.5 rounded border font-medium ${cls}`}>{status}</span>;
}

export default function Shipments() {
  const [tab,       setTab]       = useState("synthetic");
  const [synthetic, setSynthetic] = useState([]);
  const [aftership, setAfterShip] = useState([]);
  const [shiprocket,setShiprocket]= useState([]);
  const [search,    setSearch]    = useState("");
  const [loading,   setLoading]   = useState({});

  useEffect(() => {
    api.shipments().then(d => setSynthetic(d.shipments||[])).catch(console.error);
  }, []);

  const loadAfterShip = () => {
    setLoading(l=>({...l,aftership:true}));
    api.aftership().then(d=>setAfterShip(d.shipments||[])).finally(()=>setLoading(l=>({...l,aftership:false})));
  };
  const loadShiprocket = () => {
    setLoading(l=>({...l,shiprocket:true}));
    api.shiprocket().then(d=>setShiprocket(d.shipments||[])).finally(()=>setLoading(l=>({...l,shiprocket:false})));
  };

  const active = tab==="synthetic" ? synthetic : tab==="aftership" ? aftership : shiprocket;
  const filtered = active.filter(s =>
    !search || JSON.stringify(s).toLowerCase().includes(search.toLowerCase())
  );

  const TABS = [
    { id:"synthetic",  label:"Model Shipments",  sub:"ML-ranked from graph" },
    { id:"aftership",  label:"AfterShip Live",   sub:"800+ carrier tracking", load:loadAfterShip,  loading:loading.aftership },
    { id:"shiprocket", label:"Shiprocket Live",   sub:"Indian e-commerce",    load:loadShiprocket, loading:loading.shiprocket },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Active Shipments</h1>
      <p className="text-gray-400 text-sm mb-6">Real-time tracking from ML model, AfterShip (800+ carriers), and Shiprocket (Indian e-commerce)</p>

      {/* Tabs */}
      <div className="flex gap-2 mb-4">
        {TABS.map(t => (
          <button key={t.id}
            onClick={() => { setTab(t.id); if(t.load && (t.id==="aftership"&&!aftership.length || t.id==="shiprocket"&&!shiprocket.length)) t.load(); }}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all border
              ${tab===t.id ? "bg-blue-600 border-blue-500 text-white" : "bg-[#161b27] border-[#1f2937] text-gray-400 hover:text-white"}`}>
            {t.label}
            <span className="ml-1.5 text-xs opacity-60">{t.sub}</span>
          </button>
        ))}
      </div>

      {/* Real-data setup banner */}
      {(tab==="aftership"||tab==="shiprocket") && (
        <motion.div initial={{opacity:0}} animate={{opacity:1}}
          className="bg-blue-950/40 border border-blue-800 rounded-xl p-4 mb-4 text-sm">
          <div className="text-blue-300 font-semibold mb-1">
            {tab==="aftership" ? "🌐 AfterShip — 800+ carriers including Delhivery, DTDC, Blue Dart, Ekart"
                               : "🇮🇳 Shiprocket — India's #1 e-commerce shipping (Flipkart, Amazon, Meesho sellers)"}
          </div>
          <div className="text-blue-400 text-xs">
            {tab==="aftership"
              ? "Set AFTERSHIP_API_KEY env var for live data. Free tier: 100 trackings/month → aftership.com/signup"
              : "Set SHIPROCKET_EMAIL + SHIPROCKET_PASSWORD env vars → app.shiprocket.in/register (free)"}
          </div>
        </motion.div>
      )}

      {/* Search + refresh */}
      <div className="flex gap-3 mb-4">
        <input value={search} onChange={e=>setSearch(e.target.value)}
          placeholder="Search order ID, city, carrier…"
          className="flex-1 bg-[#161b27] border border-[#1f2937] text-white rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 placeholder:text-gray-600"/>
        {TABS.find(t=>t.id===tab)?.load && (
          <button onClick={TABS.find(t=>t.id===tab).load}
            className="px-4 py-2.5 bg-[#161b27] border border-[#1f2937] text-gray-300 rounded-xl text-sm hover:text-white transition-all">
            {loading[tab] ? "Loading…" : "↻ Refresh"}
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-[#161b27] border border-[#1f2937] rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1f2937]">
              {["Order ID","Carrier","Product / Title","Source","Destination","Status","Risk","ETA","Data Source"].map(h=>(
                <th key={h} className="text-left px-4 py-3 text-xs text-gray-500 font-semibold uppercase tracking-wider whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={9} className="text-center py-12 text-gray-500">
                {loading[tab] ? "Fetching live data…" : "No shipments. Click Refresh to load."}
              </td></tr>
            ) : filtered.map((s,i) => (
              <motion.tr key={s.id} initial={{opacity:0}} animate={{opacity:1}}
                transition={{delay:i*0.03}}
                className="border-b border-[#1a2030] hover:bg-white/[0.02] transition-colors">
                <td className="px-4 py-3 text-blue-400 font-semibold whitespace-nowrap">{s.id}</td>
                <td className="px-4 py-3 text-gray-300 whitespace-nowrap">{s.carrier||"—"}</td>
                <td className="px-4 py-3 text-gray-300 max-w-[150px] truncate">{s.product||s.title||"—"}</td>
                <td className="px-4 py-3 text-gray-400 whitespace-nowrap">{s.source}</td>
                <td className="px-4 py-3 text-gray-400 whitespace-nowrap">{s.destination}</td>
                <td className="px-4 py-3"><Badge status={s.status}/></td>
                <td className="px-4 py-3">
                  <span className="font-bold text-xs" style={{color:riskColor(s.risk||0)}}>
                    {Math.round((s.risk||0)*100)}%
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">{s.eta||"—"}</td>
                <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">{s.data_source||"ML Graph"}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="text-xs text-gray-500 mt-2 text-right">{filtered.length} shipments shown</div>
    </div>
  );
}
