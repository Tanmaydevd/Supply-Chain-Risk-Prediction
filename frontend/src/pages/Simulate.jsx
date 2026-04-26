import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MapContainer, TileLayer, CircleMarker, Polyline, Tooltip, Marker } from "react-leaflet";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, ReferenceLine } from "recharts";
import { api } from "../api";

const riskColor = r => r < 0.33 ? "#22c55e" : r < 0.66 ? "#f97316" : "#ef4444";

export default function Simulate() {
  const [nodes,     setNodes]     = useState([]);
  const [failed,    setFailed]    = useState("");
  const [extraLoad, setExtraLoad] = useState(0.15);
  const [result,    setResult]    = useState(null);
  const [graphData, setGraphData] = useState(null);
  const [loading,   setLoading]   = useState(false);

  useEffect(() => {
    api.nodes().then(d => { setNodes(d.nodes||[]); setFailed(d.nodes?.[0]||""); });
    api.graph().then(setGraphData);
  }, []);

  const run = async () => {
    setLoading(true);
    try {
      const r = await api.simulate({ failed_node: failed, extra_load: extraLoad });
      setResult(r);
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  };

  // build post-failure map positions
  const failedNode    = graphData?.nodes.find(n => n.id === (result?.failed_node || failed));
  const cascadedNodes = new Set(result?.secondary_failures || []);

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Cascading Failure Simulation</h1>
      <p className="text-gray-400 text-sm mb-6">Remove a hub and see the cascade through the network with ML risk re-prediction</p>

      {/* Controls */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-[#161b27] border border-[#1f2937] rounded-xl p-4">
          <label className="text-xs text-gray-400 mb-2 block uppercase tracking-wider">Node to Fail</label>
          <select value={failed} onChange={e=>setFailed(e.target.value)}
            className="w-full bg-[#0d1117] border border-[#1f2937] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
            {nodes.map(n=><option key={n}>{n}</option>)}
          </select>
        </div>
        <div className="bg-[#161b27] border border-[#1f2937] rounded-xl p-4">
          <label className="text-xs text-gray-400 mb-2 block uppercase tracking-wider">
            Extra Load — <span className="text-white font-semibold">{Math.round(extraLoad*100)}%</span>
          </label>
          <input type="range" min={0.05} max={0.4} step={0.05} value={extraLoad}
            onChange={e=>setExtraLoad(+e.target.value)} className="w-full mt-2 accent-blue-500"/>
        </div>
        <div className="flex items-end">
          <motion.button onClick={run} disabled={loading}
            whileHover={{ scale:1.02 }} whileTap={{ scale:0.98 }}
            className="w-full py-3 bg-red-600 hover:bg-red-500 text-white font-bold rounded-xl transition-all disabled:opacity-50">
            {loading ? "Simulating…" : "💥 Run Simulation"}
          </motion.button>
        </div>
      </div>

      <AnimatePresence>
      {result && (
        <motion.div key="result" initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }}>
          {/* KPI row */}
          <div className="grid grid-cols-5 gap-3 mb-6">
            {[
              ["Lost Edges",       result.lost_edges,              "text-red-400"],
              ["Secondary Failures",result.secondary_failures.length,"text-orange-400"],
              ["Remaining Nodes",  result.remaining_nodes,          "text-white"],
              ["Remaining Edges",  result.remaining_edges,          "text-white"],
              ["Cascade Steps",    result.cascade_order.length,     "text-purple-400"],
            ].map(([l,v,c]) => (
              <div key={l} className="bg-[#161b27] border border-[#1f2937] rounded-xl p-4">
                <div className="text-xs text-gray-400 mb-1">{l}</div>
                <div className={`text-2xl font-bold ${c}`}>{v}</div>
              </div>
            ))}
          </div>

          {/* Cascade alert */}
          {result.secondary_failures.length > 0 ? (
            <div className="bg-red-950/50 border border-red-800 rounded-xl p-4 mb-6">
              <div className="text-red-400 font-bold mb-1">⛓ Cascade: {result.cascade_order.join(" → ")}</div>
              <div className="text-red-300 text-sm">
                Secondary failures cut off from network: {result.secondary_failures.join(", ")}
              </div>
            </div>
          ) : (
            <div className="bg-green-950/50 border border-green-800 rounded-xl p-4 mb-6">
              <div className="text-green-400 font-semibold">
                ✓ No cascade — network remains connected after removing {result.failed_node}
              </div>
            </div>
          )}

          {/* Map + risk impact */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            {/* Post-failure map */}
            <div className="bg-[#161b27] border border-[#1f2937] rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-[#1f2937] text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Network After Failure
              </div>
              {graphData && (
                <MapContainer center={[22,80]} zoom={5} style={{height:320}} attributionControl={false}>
                  <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"/>
                  {/* failed node */}
                  {failedNode && (
                    <CircleMarker center={[failedNode.lat,failedNode.lon]}
                      radius={12} color="#ef4444" fillColor="#ef4444" fillOpacity={0.8}>
                      <Tooltip permanent>❌ {failedNode.id}</Tooltip>
                    </CircleMarker>
                  )}
                  {/* surviving nodes */}
                  {graphData.nodes
                    .filter(n => n.id !== result.failed_node && !cascadedNodes.has(n.id))
                    .map(n => (
                      <CircleMarker key={n.id} center={[n.lat,n.lon]}
                        radius={7} color="#1d4ed8" fillColor="#60a5fa" fillOpacity={0.9}>
                        <Tooltip>{n.id}</Tooltip>
                      </CircleMarker>
                    ))}
                  {/* cascaded nodes */}
                  {graphData.nodes.filter(n=>cascadedNodes.has(n.id)).map(n=>(
                    <CircleMarker key={n.id} center={[n.lat,n.lon]}
                      radius={10} color="#f97316" fillColor="#f97316" fillOpacity={0.7}>
                      <Tooltip>⚠ {n.id} (cascaded)</Tooltip>
                    </CircleMarker>
                  ))}
                  {/* surviving edges */}
                  {result.surviving_edges.map((e,i)=>{
                    const s=graphData.nodes.find(n=>n.id===e.source);
                    const t=graphData.nodes.find(n=>n.id===e.target);
                    if(!s||!t) return null;
                    return (
                      <Polyline key={i} positions={[[s.lat,s.lon],[t.lat,t.lon]]}
                        color={riskColor(e.risk)} weight={2} opacity={0.75}>
                        <Tooltip>{e.source}→{e.target} {Math.round(e.risk*100)}%</Tooltip>
                      </Polyline>
                    );
                  })}
                </MapContainer>
              )}
            </div>

            {/* Risk impact chart */}
            <div className="bg-[#161b27] border border-[#1f2937] rounded-xl p-4">
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">
                Delay Risk Increase on Surviving Routes
              </div>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={result.risk_impact?.slice(0,10).map(r=>({
                  route: r.route.replace(" -> ","→").substring(0,15),
                  delta: +(r.delta*100).toFixed(1),
                  risk:  r.risk_after,
                }))} margin={{left:-10}}>
                  <XAxis dataKey="route" tick={{fill:"#6b7280",fontSize:10}} axisLine={false} tickLine={false}
                    angle={-35} textAnchor="end" height={55}/>
                  <YAxis tick={{fill:"#6b7280",fontSize:11}} axisLine={false} tickLine={false}
                    tickFormatter={v=>`+${v}%`}/>
                  <ReferenceLine y={0} stroke="#374151"/>
                  <Bar dataKey="delta" radius={[4,4,0,0]}>
                    {result.risk_impact?.slice(0,10).map((_,i)=>(
                      <Cell key={i} fill={_.delta>0.2?"#ef4444":_.delta>0.1?"#f97316":"#22c55e"}/>
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Affected routes */}
          <div className="bg-[#161b27] border border-[#1f2937] rounded-xl p-4">
            <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Affected Routes ({result.affected_routes.length})
            </div>
            <div className="flex flex-wrap gap-2">
              {result.affected_routes.map((r,i)=>(
                <span key={i} className="text-xs bg-red-950/50 border border-red-900 text-red-300 px-2 py-1 rounded">
                  {r.from} → {r.to}
                </span>
              ))}
            </div>
          </div>
        </motion.div>
      )}
      </AnimatePresence>

      {!result && !loading && (
        <div className="flex items-center justify-center h-48 text-gray-500 border border-dashed border-[#1f2937] rounded-xl">
          Select a node and click Run Simulation
        </div>
      )}
    </div>
  );
}
