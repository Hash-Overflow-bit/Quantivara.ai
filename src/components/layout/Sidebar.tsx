import { 
  LayoutDashboard, 
  BarChart2, 
  Radar, 
  Newspaper, 
  PieChart, 
  Briefcase,
  Settings,
  LogOut
} from "lucide-react";
import { Link, useLocation } from "react-router-dom";

const menuItems = [
  { icon: LayoutDashboard, label: "Market Dashboard", path: "/" },
  { icon: BarChart2, label: "Stock Analysis", path: "/analysis" },
  { icon: Radar, label: "Opportunity Scanner", path: "/scanner" },
  { icon: Newspaper, label: "News Intelligence", path: "/news" },
  { icon: PieChart, label: "Sector Momentum", path: "/sectors" },
  { icon: Briefcase, label: "Portfolio AI", path: "/portfolio" },
];

export default function Sidebar() {
  const location = useLocation();

  return (
    <div className="w-64 bg-background-accent border-r border-border h-screen fixed left-0 top-0 flex flex-col pt-8">
      <div className="px-6 mb-10">
        <h1 className="text-xl font-bold tracking-tight flex items-center gap-2">
          <span className="text-bullish">PSX</span>
          <span className="text-white">INSIDER</span>
        </h1>
      </div>

      <nav className="flex-1 px-4 space-y-1">
        {menuItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 group ${
                isActive 
                  ? "bg-bullish/10 text-bullish font-semibold border border-bullish/20" 
                  : "text-content-secondary hover:bg-white/5 hover:text-white"
              }`}
            >
              <item.icon size={20} className={isActive ? "text-bullish" : "group-hover:text-white"} />
              <span className="text-sm">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-border mt-auto">
        <button className="w-full flex items-center gap-3 px-4 py-3 text-content-secondary hover:text-white transition-colors">
          <Settings size={20} />
          <span className="text-sm">Settings</span>
        </button>
        <button className="w-full flex items-center gap-3 px-4 py-3 text-bearish hover:text-bearish/80 transition-colors">
          <LogOut size={20} />
          <span className="text-sm font-semibold">Log Out</span>
        </button>
      </div>
    </div>
  );
}
