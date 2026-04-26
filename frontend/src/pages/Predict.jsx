import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { RadialBarChart, RadialBar, PolarAngleAxis } from "recharts";
import { api } from "../api";

const WEATHER_OPTS = [["Sunny",0],["Cloudy",0],["Rain",1],["Storm",2]];
const TRAFFIC_OPTS = [["Low",0],["Medium",1],["High",2]];

function RiskGauge({ value }) {
  const color = value >= 66 ? "#ef4444" : value >= 33 ? "#f97316" : "#22c55e";
  return (
    <div className="relative flex items-center justify-center">
      <RadialBarChart width={200} height={200} innerRadius="70%" outerRadius="90%"
        data={[{ value, fill: color }]} startAngle={180} endAngle={0}>
        <PolarAngleAxis type="number" domain={[0,100]} tick={false}/>
        <RadialBar dataKey="value" cornerRadius={8} background={{ fill:"#1f2937" }}/>
      </RadialBarChart>
      <div className="absolute text-center">
        <div className="text-3xl font-bold" style={{ color }}>{value}%</div>
        <div className="text-xs text-gray-400">delay risk</div>
      </div>
    </div>
  );
}

export default function Predict() {
  const [nodes, setNodes]     = useState([]);
  const [origin, setOrigin]   = useState("");
  const [dest, setDest]       = useState("");
  const [weather, setWeather] = useState(1);
  const [traffic, setTraffic] = useState(1);
  const [load, setLoad]       = useState(0.7);
  const [result, setResult]   = useState(null);
  const [liveW, setLiveW]     = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.nodes().then(d => {
      setNodes(d.nodes || []);
      if (d.nodes?.length > 0) { setOrigin(d.nodes[0]); setDest(d.nodes[1]||d.nodes[0]); }
    });
  }, []);

  // fetch live weather when origin changes
  useEffect(() => {
    if (!origin) return;
    api.weather(origin).then(w => {
      setLiveW(w);
      setWeather(w.score);
    }).catch(()=>{});
  }, [origin]);

  const run = async () => {
    setLoading(true);
    try {
      const r = await api.predict({ origin, destination: dest,
        weather_score: weather, traffic_score: traffic, warehouse_load: load });
      setResult(r);
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  };

  const riskLabel = (p) => p>=66?"High":p>=33?"Medium":"Low";
  const riskColor = (p) => p>=66?"text-red-400":p>=33?"text-orange-400":"text-green-400";

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Delay Prediction</h1>
      <p className="text-gray-400 text-sm mb-6">AI-powered shipment delay probability using Random Forest + live conditions</p>

      <div className="grid grid-cols-2 gap-6">
        {/* Controls */}
        <div className="space-y-4">
          {/* Route */}
          <div className="bg-[#161b27] border border-[#1f2937] rounded-xl p-5 space-y-4">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">Route</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Origin</label>
                <select value={origin} onChange={e=>setOrigin(e.target.value)}
                  className="w-full bg-[#0d1117] border border-[#1f2937] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
                  {nodes.map(n=><option key={n}>{n}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Destination</label>
                <select value={dest} onChange={e=>setDest(e.target.value)}
                  className="w-full bg-[#0d1117] border border-[#1f2937] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
                  {nodes.filter(n=>n!==origin).map(n=><option key={n}>{n}</option>)}
                </select>
              </div>
            </div>
          </div>

          {/* Conditions */}
          <div className="bg-[#161b27] border border-[#1f2937] rounded-xl p-5 space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">Conditions</h3>
              {liveW && (
                <span className="text-xs text-green-400 bg-green-950 px-2 py-0.5 rounded-full">
                  🌐 Live: {liveW.label}
                </span>
              )}
            </div>
            {/* Weather */}
            <div>
              <label className="text-xs text-gray-400 mb-2 block">Weather</label>
              <div className="flex gap-2">
                {WEATHER_OPTS.map(([lbl,val]) => (
                  <button key={lbl} onClick={()=>setWeather(val)}
                    className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all
                      ${weather===val ? "bg-blue-600 text-white" : "bg-[#0d1117] text-gray-400 border border-[#1f2937] hover:border-gray-500"}`}>
                    {lbl}
                  </button>
                ))}
              </div>
            </div>
            {/* Traffic */}
            <div>
              <label className="text-xs text-gray-400 mb-2 block">Traffic</label>
              <div className="flex gap-2">
                {TRAFFIC_OPTS.map(([lbl,val]) => (
                  <button key={lbl} onClick={()=>setTraffic(val)}
                    className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all
                      ${traffic===val ? "bg-blue-600 text-white" : "bg-[#0d1117] text-gray-400 border border-[#1f2937] hover:border-gray-500"}`}>
                    {lbl}
                  </button>
                ))}
              </div>
            </div>
            {/* Load slider */}
            <div>
              <label className="text-xs text-gray-400 mb-2 block">
                Warehouse Load — <span className="text-white font-semibold">{Math.round(load*100)}%</span>
              </label>
              <input type="range" min={0} max={1} step={0.05} value={load}
                onChange={e=>setLoad(+e.target.value)}
                className="w-full accent-blue-500"/>
            </div>
          </div>

          <motion.button onClick={run} disabled={loading}
            whileHover={{ scale:1.02 }} whileTap={{ scale:0.98 }}
            className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl transition-all disabled:opacity-50">
            {loading ? "Predicting…" : "Predict Delay Risk"}
          </motion.button>
        </div>

        {/* Result */}
        <div className="bg-[#161b27] border border-[#1f2937] rounded-xl p-6 flex flex-col items-center justify-center">
          <AnimatePresence mode="wait">
            {!result ? (
              <motion.div key="empty" className="text-center text-gray-500">
                <div className="text-5xl mb-3">🔮</div>
                <div>Configure a route and click Predict</div>
              </motion.div>
            ) : (
              <motion.div key="result" initial={{ opacity:0, scale:0.9 }}
                animate={{ opacity:1, scale:1 }} className="text-center w-full">
                <RiskGauge value={result.risk_score}/>
                <div className={`text-xl font-bold mt-2 ${riskColor(result.risk_score)}`}>
                  {riskLabel(result.risk_score)} Risk
                </div>
                <div className="text-gray-400 text-sm mt-1">
                  {result.origin} → {result.destination}
                </div>
                <div className="grid grid-cols-2 gap-3 mt-6 w-full">
                  {[
                    ["Delay Probability", `${Math.round(result.delay_probability*100)}%`],
                    ["Distance", `${result.distance_km?.toFixed(0)} km`],
                  ].map(([l,v])=>(
                    <div key={l} className="bg-[#0d1117] rounded-lg p-3">
                      <div className="text-xs text-gray-400">{l}</div>
                      <div className="text-lg font-bold text-white">{v}</div>
                    </div>
                  ))}
                </div>
                {result.risk_score >= 66 && (
                  <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }}
                    className="mt-4 w-full p-3 bg-red-950/50 border border-red-800 rounded-lg text-left">
                    <div className="text-red-400 font-semibold text-sm mb-1">⚠ High Risk Alert</div>
                    <div className="text-red-300 text-xs">Consider alternate routing or departure window adjustment.</div>
                  </motion.div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
