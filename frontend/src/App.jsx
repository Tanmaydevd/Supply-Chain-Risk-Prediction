import { BrowserRouter, Routes, Route, NavLink, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { LayoutDashboard, Map, TrendingUp, Zap, Package, ShieldAlert, Activity } from "lucide-react";
import Dashboard from "./pages/Dashboard";
import MapPage   from "./pages/MapPage";
import Predict   from "./pages/Predict";
import Simulate  from "./pages/Simulate";
import Analytics from "./pages/Analytics";
import Shipments from "./pages/Shipments";

const NAV = [
  { to: "/",          icon: LayoutDashboard, label: "Dashboard"  },
  { to: "/map",       icon: Map,             label: "Global Map" },
  { to: "/shipments", icon: Package,         label: "Shipments"  },
  { to: "/predict",   icon: TrendingUp,      label: "Predict"    },
  { to: "/simulate",  icon: Zap,             label: "Simulate"   },
  { to: "/analytics", icon: Activity,        label: "Analytics"  },
];

function Sidebar() {
  return (
    <aside className="fixed top-0 left-0 h-screen w-56 bg-[#111827] border-r border-[#1f2937] flex flex-col z-50">
      <div className="flex items-center gap-2 px-5 py-5 border-b border-[#1f2937]">
        <ShieldAlert className="text-blue-400" size={22} />
        <span className="font-bold text-white text-lg">SupplyGuard</span>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all
               ${isActive ? "bg-blue-600/20 text-blue-400" : "text-gray-400 hover:bg-white/5 hover:text-gray-200"}`}>
            <Icon size={17}/>{label}
          </NavLink>
        ))}
      </nav>
      <div className="px-4 py-4 border-t border-[#1f2937]">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse"/>
          API Live
        </div>
      </div>
    </aside>
  );
}

function PageWrapper({ children }) {
  const loc = useLocation();
  return (
    <AnimatePresence mode="wait">
      <motion.div key={loc.pathname}
        initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.22 }}>
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex bg-[#0d1117] min-h-screen">
        <Sidebar />
        <main className="ml-56 flex-1 p-6 overflow-auto">
          <PageWrapper>
            <Routes>
              <Route path="/"          element={<Dashboard />} />
              <Route path="/map"       element={<MapPage />}   />
              <Route path="/shipments" element={<Shipments />} />
              <Route path="/predict"   element={<Predict />}   />
              <Route path="/simulate"  element={<Simulate />}  />
              <Route path="/analytics" element={<Analytics />} />
            </Routes>
          </PageWrapper>
        </main>
      </div>
    </BrowserRouter>
  );
}
