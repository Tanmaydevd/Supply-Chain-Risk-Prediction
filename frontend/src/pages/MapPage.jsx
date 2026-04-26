import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Polyline, Tooltip, Popup } from "react-leaflet";
import { motion } from "framer-motion";
import { api } from "../api";

const riskColor = r => r < 0.33 ? "#22c55e" : r < 0.66 ? "#f97316" : "#ef4444";
const riskLabel = r => r < 0.33 ? "Low" : r < 0.66 ? "Medium" : "High";

export default function MapPage() {
  const [graph, setGraph] = useState(null);
  const [filter, setFilter] = useState("all");

  useEffect(() => { api.graph().then(setGraph).catch(console.error); }, []);

  const filteredEdges = graph?.edges.filter(e => {
    if (filter === "all")    return true;
    if (filter === "high")   return e.risk >= 0.66;
    if (filter === "medium") return e.risk >= 0.33 && e.risk < 0.66;
    if (filter === "low")    return e.risk < 0.33;
    return true;
  }) || [];

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Network Map</h1>
          <p className="text-gray-400 text-sm">ML-predicted delay risk across all routes</p>
        </div>
        <div className="flex gap-2">
          {["all","high","medium","low"].map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase transition-all
                ${filter===f ? "bg-blue-600 text-white" : "bg-[#161b27] text-gray-400 hover:text-white border border-[#1f2937]"}`}>
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex gap-4 mb-4 text-xs text-gray-400">
        {[["#22c55e","Low (<33%)"],["#f97316","Medium (33–66%)"],["#ef4444","High (>66%)"]].map(([c,l])=>(
          <div key={l} className="flex items-center gap-1.5">
            <span className="w-6 h-1.5 rounded-full" style={{background:c}}/>
            {l}
          </div>
        ))}
      </div>

      <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }}
        className="bg-[#161b27] border border-[#1f2937] rounded-xl overflow-hidden">
        {graph ? (
          <MapContainer center={[22, 80]} zoom={5} style={{ height:"calc(100vh - 220px)" }}
            attributionControl={false}>
            <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"/>
            {filteredEdges.map((e,i) => {
              const s = graph.nodes.find(n=>n.id===e.source);
              const t = graph.nodes.find(n=>n.id===e.target);
              if (!s||!t) return null;
              return (
                <Polyline key={i} positions={[[s.lat,s.lon],[t.lat,t.lon]]}
                  color={riskColor(e.risk)} weight={2.5} opacity={0.8}>
                  <Tooltip sticky>
                    <div className="text-xs">
                      <strong>{e.source} → {e.target}</strong><br/>
                      Risk: {Math.round(e.risk*100)}% ({riskLabel(e.risk)})<br/>
                      Distance: {e.distance_km?.toFixed(0)} km
                    </div>
                  </Tooltip>
                </Polyline>
              );
            })}
            {graph.nodes.map(n => (
              <CircleMarker key={n.id} center={[n.lat,n.lon]}
                radius={8} color="#1d4ed8" fillColor="#60a5fa" fillOpacity={0.9} weight={2}>
                <Popup>
                  <div className="text-xs font-semibold">{n.id}</div>
                  <div className="text-xs text-gray-500 capitalize">{n.type}</div>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        ) : (
          <div className="h-96 flex items-center justify-center text-gray-500">Loading map…</div>
        )}
      </motion.div>

      {/* Stats bar */}
      {graph && (
        <div className="grid grid-cols-4 gap-3 mt-4">
          {[
            ["Total routes",  graph.edges.length, "text-white"],
            ["High risk",     graph.edges.filter(e=>e.risk>=0.66).length, "text-red-400"],
            ["Medium risk",   graph.edges.filter(e=>e.risk>=0.33&&e.risk<0.66).length, "text-orange-400"],
            ["Low risk",      graph.edges.filter(e=>e.risk<0.33).length, "text-green-400"],
          ].map(([lbl,val,cls]) => (
            <div key={lbl} className="bg-[#161b27] border border-[#1f2937] rounded-xl p-4">
              <div className="text-xs text-gray-400 mb-1">{lbl}</div>
              <div className={`text-2xl font-bold ${cls}`}>{val}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
