import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell,
         RadarChart, Radar, PolarGrid, PolarAngleAxis, Tooltip, Legend } from "recharts";
import { api } from "../api";

const MODEL_COLORS = { logreg:"#60a5fa", rf:"#34d399", xgb:"#f97316", catboost:"#a78bfa" };

export default function Analytics() {
  const [data, setData] = useState(null);
  useEffect(() => { api.analytics().then(setData).catch(console.error); }, []);

  if (!data) return <div className="flex items-center justify-center h-64 text-gray-500">Loading…</div>;

  const models = data.model_metrics?.results ? Object.entries(data.model_metrics.results) : [];
  const best   = data.model_metrics?.best;

  const radarData = models.map(([name, m]) => ({
    model: name, accuracy: +(m.accuracy*100).toFixed(1),
    precision: +(m.precision*100).toFixed(1), recall: +(m.recall*100).toFixed(1),
    f1: +(m.f1*100).toFixed(1), auc: +(m.roc_auc*100).toFixed(1),
  }));

  const shap = data.shap_importances || [];
  const fi   = data.feature_importances || [];

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Analytics</h1>
      <p className="text-gray-400 text-sm mb-6">Model benchmarks + SHAP explainability — aligned with paper §3.4 & §3.5</p>

      {/* Best model banner */}
      {best && (
        <motion.div initial={{opacity:0,y:-10}} animate={{opacity:1,y:0}}
          className="bg-blue-950/50 border border-blue-800 rounded-xl p-4 mb-6 flex items-center gap-3">
          <span className="text-2xl">🏆</span>
          <div>
            <div className="text-blue-300 font-bold">Best Model: {best.toUpperCase()}</div>
            <div className="text-blue-400 text-sm">Selected by highest F1 score</div>
          </div>
        </motion.div>
      )}

      {/* Model comparison bar chart */}
      {models.length > 0 && (
        <div className="grid grid-cols-2 gap-4 mb-6">
          {["f1","roc_auc","accuracy","precision"].map(metric => (
            <div key={metric} className="bg-[#161b27] border border-[#1f2937] rounded-xl p-4">
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                {metric.replace("_"," ").toUpperCase()}
              </div>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={models.map(([n,m])=>({model:n, value: +(m[metric]*100).toFixed(1)}))}
                  margin={{left:-10}}>
                  <XAxis dataKey="model" tick={{fill:"#9ca3af",fontSize:12}} axisLine={false} tickLine={false}/>
                  <YAxis domain={[0,100]} tick={{fill:"#6b7280",fontSize:11}} axisLine={false} tickLine={false}/>
                  <Tooltip formatter={v=>`${v}%`} contentStyle={{background:"#161b27",border:"1px solid #1f2937"}}/>
                  <Bar dataKey="value" radius={[4,4,0,0]}>
                    {models.map(([n],i) => <Cell key={i} fill={MODEL_COLORS[n]||"#60a5fa"}/>)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ))}
        </div>
      )}

      {/* SHAP + native importance side by side */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-[#161b27] border border-[#1f2937] rounded-xl p-4">
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
            SHAP Importance (paper §3.5)
          </div>
          <div className="text-xs text-gray-500 mb-3">Mean |SHAP| — game-theory attribution</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={shap} layout="vertical" margin={{left:40,right:20}}>
              <XAxis type="number" tick={{fill:"#6b7280",fontSize:11}} axisLine={false} tickLine={false}/>
              <YAxis dataKey="feature" type="category" tick={{fill:"#9ca3af",fontSize:12}} axisLine={false} tickLine={false} width={120}/>
              <Tooltip contentStyle={{background:"#161b27",border:"1px solid #1f2937"}}/>
              <Bar dataKey="shap_importance" radius={[0,4,4,0]} fill="#f97316"/>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-[#161b27] border border-[#1f2937] rounded-xl p-4">
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
            Native Feature Importance
          </div>
          <div className="text-xs text-gray-500 mb-3">Tree split frequency</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={fi} layout="vertical" margin={{left:40,right:20}}>
              <XAxis type="number" tick={{fill:"#6b7280",fontSize:11}} axisLine={false} tickLine={false}/>
              <YAxis dataKey="feature" type="category" tick={{fill:"#9ca3af",fontSize:12}} axisLine={false} tickLine={false} width={120}/>
              <Tooltip contentStyle={{background:"#161b27",border:"1px solid #1f2937"}}/>
              <Bar dataKey="importance" radius={[0,4,4,0]} fill="#60a5fa"/>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Model metrics table */}
      {models.length > 0 && (
        <div className="bg-[#161b27] border border-[#1f2937] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-[#1f2937] text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Full Model Comparison (paper §3.4 — LR / RF / XGBoost / CatBoost)
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1f2937]">
                {["Model","Accuracy","Precision","Recall","F1","ROC-AUC"].map(h=>(
                  <th key={h} className="text-left px-4 py-2.5 text-xs text-gray-500 font-semibold uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {models.map(([name,m])=>(
                <tr key={name} className={`border-b border-[#1a2030] ${name===best?"bg-blue-950/20":""}`}>
                  <td className="px-4 py-3">
                    <span className="font-bold" style={{color:MODEL_COLORS[name]||"#9ca3af"}}>
                      {name.toUpperCase()} {name===best?"🏆":""}
                    </span>
                  </td>
                  {["accuracy","precision","recall","f1","roc_auc"].map(k=>(
                    <td key={k} className="px-4 py-3 text-gray-300">{(m[k]*100).toFixed(1)}%</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
