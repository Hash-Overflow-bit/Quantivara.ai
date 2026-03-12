import { useState, useEffect, useMemo } from "react";
import { doc, onSnapshot } from "firebase/firestore";
import { db } from "../../firebase";
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts';
import { Search, TrendingUp, TrendingDown, Activity, ExternalLink, Info, Clock, Lock } from "lucide-react";

interface MarketData {
  kse100: { value: number; change: number };
  kse30: { value: number; change: number };
  volume: string;
  usdPkr: number;
  gold: number;
  tBillYield: number;
  status: string;
  phase?: string;
  final_data_date?: string;
}

interface Stock {
  symbol: string;
  price: number;
  change: number;
  volume?: string;
}

interface SectorData {
  name: string;
  change: number;
}

interface ChartPoint {
  time: string;
  value: number;
}

interface PredictedMover {
  symbol: string;
  reason: string;
  sentiment: 'bullish' | 'bearish' | 'neutral';
  confidence: number;
  entry_price: number;
  target_price: number;
  stop_loss: number;
  risk_reward: string;
  risk_percentage: number;
  entry_time: string;
}

interface VolumeSpike {
  symbol: string;
  today_vol: number;
  avg_vol: number;
  spike_ratio: number;
  price: number;
  change: number;
  projected_vol: number;
}

const InfoTooltip = ({ text }: { text: string }) => (
  <div className="relative group ml-2 inline-flex items-center">
    <Info className="w-3.5 h-3.5 text-content-muted hover:text-white transition-colors cursor-help" />
    <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 w-64 p-3 bg-[#15181E] border border-border/50 rounded-xl text-xs text-content-secondary leading-relaxed opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all shadow-2xl z-[1000] pointer-events-none font-medium">
      {text}
      <div className="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0 border-l-[6px] border-r-[6px] border-t-[6px] border-l-transparent border-r-transparent border-t-border/50"></div>
    </div>
  </div>
);

export default function Dashboard() {
  const [marketData, setMarketData] = useState<MarketData | null>(null);
  const [gainers, setGainers] = useState<Stock[]>([]);
  const [losers, setLosers] = useState<Stock[]>([]);
  const [sectors, setSectors] = useState<SectorData[]>([]);
  const [kse100Chart, setKse100Chart] = useState<ChartPoint[]>([]);
  const [kse30Chart, setKse30Chart] = useState<ChartPoint[]>([]);
  const [allStocks, setAllStocks] = useState<Stock[]>([]);
  const [expectedGainers, setExpectedGainers] = useState<PredictedMover[]>([]);
  const [expectedLosers, setExpectedLosers] = useState<PredictedMover[]>([]);
  const [volumeSpikes, setVolumeSpikes] = useState<VolumeSpike[]>([]);
  const [searchQuery, setSearchQuery] = useState("");

  const MarketStatusBanner = () => {
    const phase = marketData?.phase || "CLOSED";
    const date = marketData?.final_data_date || new Date().toLocaleTimeString([], { day: '2-digit', month: 'short' });
    
    if (phase === "PRE_OPEN") {
      return (
        <div className="bg-bullish/10 border border-bullish/20 rounded-lg p-3 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Clock className="w-4 h-4 text-bullish animate-pulse" />
            <span className="text-xs font-black uppercase tracking-widest text-bullish">
              PRE-OPEN • Market opens at 9:30 AM
            </span>
          </div>
          <span className="text-[10px] text-content-muted font-bold uppercase">
            Spike cache cleared for new session
          </span>
        </div>
      );
    }
    
    if (phase === "OPEN") {
       return (
        <div className="bg-bullish/10 border border-bullish/20 rounded-lg p-3 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4 text-bullish animate-pulse" />
            <span className="text-xs font-black uppercase tracking-widest text-bullish">
              MARKET OPEN • Live Data • 15-min delayed
            </span>
          </div>
        </div>
      );
    }

    return (
      <div className="bg-white/5 border border-white/10 rounded-lg p-3 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Lock className="w-4 h-4 text-content-muted" />
          <span className="text-xs font-black uppercase tracking-widest text-content-muted">
            MARKET CLOSED • Final data from {date}
          </span>
        </div>
        <span className="text-[10px] text-content-muted font-bold uppercase italic">
          Spikes persistent for overnight review
        </span>
      </div>
    );
  };

  useEffect(() => {
    // Basic Market Metrics
    const unsubData = onSnapshot(doc(db, "market_data", "latest"), (doc) => {
      if (doc.exists()) setMarketData(doc.data() as MarketData);
    });

    // Top Movers
    const unsubMovers = onSnapshot(doc(db, "market_movers", "latest"), (doc) => {
      if (doc.exists()) {
        const data = doc.data();
        setGainers(data?.top_gainers || []);
        setLosers(data?.top_losers || []);
      }
    });

    // Sector Heatmap
    const unsubSectors = onSnapshot(doc(db, "market_sectors", "latest"), (doc) => {
      if (doc.exists()) setSectors(doc.data()?.sectors || []);
    });

    // Charts
    const unsub100Chart = onSnapshot(doc(db, "charts", "kse100"), (doc) => {
      if (doc.exists()) setKse100Chart(doc.data()?.points || []);
    });
    const unsub30Chart = onSnapshot(doc(db, "charts", "kse30"), (doc) => {
      if (doc.exists()) setKse30Chart(doc.data()?.points || []);
    });

    // Expanded Market Watch
    const unsubAllStocks = onSnapshot(doc(db, "market_watch", "latest"), (doc) => {
      if (doc.exists()) setAllStocks(doc.data()?.stocks || []);
    });

    // Market Opening Predictions
    const unsubPredictions = onSnapshot(doc(db, "expected_movers", "latest"), (doc) => {
      if (doc.exists()) {
        const data = doc.data();
        setExpectedGainers(data?.expected_gainers || []);
        setExpectedLosers(data?.expected_losers || []);
      }
    });

    // Volume Spike Screener
    const unsubSpikes = onSnapshot(doc(db, "volume_spikes", "latest"), (doc) => {
      if (doc.exists()) {
        setVolumeSpikes(doc.data()?.spikes || []);
      }
    });

    return () => {
      unsubData();
      unsubMovers();
      unsubSectors();
      unsub100Chart();
      unsub30Chart();
      unsubAllStocks();
      unsubPredictions();
      unsubSpikes();
    };
  }, []);

  const filteredStocks = useMemo(() => {
    if (!searchQuery) return allStocks;
    return allStocks.filter(s => 
      s.symbol.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [allStocks, searchQuery]);

  return (
    <div className="space-y-6 pb-12">
      <MarketStatusBanner />

      {/* Index Performance Sections */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-background-accent/40 border border-border/50 rounded-xl p-6 backdrop-blur-sm shadow-lg">
          <div className="flex justify-between items-start mb-6">
            <div>
              <h2 className="text-content-secondary text-xs font-bold uppercase tracking-widest mb-1 flex items-center">
                <Activity className="w-4 h-4 mr-2 text-bullish" />
                KSE-100 Index
                <InfoTooltip text="Tracks the performance of the top 100 companies listed on the Pakistan Stock Exchange by market capitalization." />
              </h2>
              <div className="flex items-baseline space-x-3">
                <span className="text-4xl font-black font-mono tracking-tighter text-white">
                  {marketData?.kse100?.value?.toLocaleString() || "---,---"}
                </span>
                <span className={`text-sm font-bold flex items-center ${(marketData?.kse100?.change || 0) >= 0 ? "text-bullish" : "text-bearish"}`}>
                  {(marketData?.kse100?.change || 0) >= 0 ? <TrendingUp className="w-4 h-4 mr-1" /> : <TrendingDown className="w-4 h-4 mr-1" />}
                  {Math.abs(marketData?.kse100?.change || 0)}%
                </span>
              </div>
            </div>
            <div className="text-right flex flex-col items-end space-y-1">
              <div className={`px-3 py-1 rounded-full text-[10px] font-black tracking-widest uppercase border ${marketData?.status === "OPEN" ? "bg-bullish/10 text-bullish border-bullish/20 animate-pulse" : "bg-white/5 text-content-muted border-white/5"}`}>
                {marketData?.status || "CLOSED"}
              </div>
              <div className="text-[8px] font-black text-content-muted uppercase tracking-tighter bg-white/5 px-2 py-0.5 rounded border border-white/5">
                Data Delayed 15m
              </div>
            </div>
          </div>
          
          <div className="h-[180px] w-full mt-4 min-h-[180px]">
            <ResponsiveContainer width="100%" height="100%" minHeight={180}>
              <AreaChart data={kse100Chart}>
                <defs>
                  <linearGradient id="colorValue100" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#272A30" />
                <XAxis dataKey="time" hide />
                <YAxis hide domain={['auto', 'auto']} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#15181E', border: '1px solid #272A30', borderRadius: '8px' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Area 
                  type="monotone" 
                  dataKey="value" 
                  stroke="#10b981" 
                  strokeWidth={3}
                  fillOpacity={1} 
                  fill="url(#colorValue100)" 
                  animationDuration={1500}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-background-accent/40 border border-border/50 rounded-xl p-6 backdrop-blur-sm shadow-lg">
          <div className="flex justify-between items-start mb-6">
            <div>
              <h2 className="text-content-secondary text-xs font-bold uppercase tracking-widest mb-1 flex items-center">
                <Activity className="w-4 h-4 mr-2 text-bullish" />
                KSE-30 Index
                <InfoTooltip text="Tracks the performance of the top 30 most liquid companies listed on the PSX." />
              </h2>
              <div className="flex items-baseline space-x-3">
                <span className="text-4xl font-black font-mono tracking-tighter text-white">
                  {marketData?.kse30?.value?.toLocaleString() || "---,---"}
                </span>
                <span className={`text-sm font-bold flex items-center ${(marketData?.kse30?.change || 0) >= 0 ? "text-bullish" : "text-bearish"}`}>
                  {(marketData?.kse30?.change || 0) >= 0 ? <TrendingUp className="w-4 h-4 mr-1" /> : <TrendingDown className="w-4 h-4 mr-1" />}
                  {Math.abs(marketData?.kse30?.change || 0)}%
                </span>
              </div>
            </div>
          </div>
          
          <div className="h-[180px] w-full mt-4 min-h-[180px]">
            <ResponsiveContainer width="100%" height="100%" minHeight={180}>
              <AreaChart data={kse30Chart}>
                <defs>
                  <linearGradient id="colorValue30" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#272A30" />
                <XAxis dataKey="time" hide />
                <YAxis hide domain={['auto', 'auto']} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#15181E', border: '1px solid #272A30', borderRadius: '8px' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Area 
                  type="monotone" 
                  dataKey="value" 
                  stroke="#10b981" 
                  strokeWidth={3}
                  fillOpacity={1} 
                  fill="url(#colorValue30)" 
                  animationDuration={1500}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="bg-background-accent/40 border border-border/50 rounded-xl backdrop-blur-sm shadow-xl">
        <div className="px-6 py-4 border-b border-border/50 bg-white/5 flex justify-between items-center">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-bullish/10 rounded-lg">
              <Activity className="w-5 h-5 text-bullish animate-pulse" />
            </div>
            <div>
              <h3 className="text-sm font-black tracking-[0.2em] text-white uppercase flex items-center">
                Volume Spike Screener
                <InfoTooltip text="Surfaces stocks with unusually high trading volume. Calculated by comparing today's projected volume against the historical 30-day average. A ratio ≥ 2.0x suggests strong institutional or retail momentum. Spikes remain visible after close for review." />
              </h3>
              <p className="text-[10px] text-content-muted font-bold tracking-tight mt-0.5">
                Surfacing stocks with abnormal volume compared to 30-day average
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <div className="text-[9px] font-black text-bearish bg-bearish/10 px-2 py-1 rounded border border-bearish/20 uppercase tracking-tight">
              15m Delay
            </div>
            <div className="px-3 py-1 bg-white/5 rounded-full border border-white/10">
              <span className="text-[10px] font-black text-content-muted uppercase tracking-widest">
                Last updated: {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          </div>
        </div>
        
        <div className="p-0">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="text-[10px] text-content-muted bg-background/50 border-b border-border/30 uppercase font-black tracking-widest">
                <th className="py-4 px-6">Symbol</th>
                <th className="py-4 px-6 text-right">Today Vol</th>
                <th className="py-4 px-6 text-right">Avg Vol</th>
                <th className="py-4 px-6 text-center">Spike Ratio</th>
                <th className="py-4 px-6 text-right">Price</th>
                <th className="py-4 px-6 text-right">Change</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/20">
              {volumeSpikes.length > 0 ? volumeSpikes.slice(0, 10).map((spike) => (
                <tr key={spike.symbol} className="hover:bg-white/5 transition-all group">
                  <td className="py-4 px-6">
                    <span className="font-black text-white group-hover:text-bullish transition-colors">
                      {spike.symbol}
                    </span>
                  </td>
                  <td className="py-4 px-6 text-right font-mono text-xs text-white">
                    {spike.today_vol >= 1000000 ? `${(spike.today_vol/1000000).toFixed(1)}M` : `${(spike.today_vol/1000).toFixed(1)}K`}
                  </td>
                  <td className="py-4 px-6 text-right font-mono text-xs text-content-muted">
                    {spike.avg_vol >= 1000000 ? `${(spike.avg_vol/1000000).toFixed(1)}M` : `${(spike.avg_vol/1000).toFixed(1)}K`}
                  </td>
                  <td className="py-4 px-6 text-center">
                    <div className="flex justify-center">
                      <span className={`px-3 py-1 rounded-lg font-black text-xs ${
                        spike.spike_ratio >= 4 ? "bg-bearish/20 text-bearish border border-bearish/30" :
                        spike.spike_ratio >= 3 ? "bg-orange-500/20 text-orange-500 border border-orange-500/30" :
                        "bg-bullish/20 text-bullish border border-bullish/30"
                      }`}>
                        {spike.spike_ratio}x
                      </span>
                    </div>
                  </td>
                  <td className="py-4 px-6 text-right font-mono font-bold text-white text-sm">
                    {spike.price?.toFixed(2) || "0.00"}
                  </td>
                  <td className="py-4 px-6 text-right">
                    <span className={`font-mono font-black text-xs ${(spike.change || 0) >= 0 ? "text-bullish" : "text-bearish"}`}>
                      {(spike.change || 0) >= 0 ? "+" : ""}{(spike.change || 0).toFixed(2)}%
                    </span>
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-content-muted text-xs font-bold uppercase tracking-[0.2em] opacity-50">
                    No significant volume spikes detected so far...
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <div className="px-6 py-3 bg-white/5 border-t border-border/50">
            <p className="text-[9px] text-content-muted font-bold leading-relaxed max-w-3xl">
              <span className="text-bullish">PROJECTION LOGIC:</span> Volume is projected based on time elapsed since market open (9:30 AM PKT). 
              Spike ratio = <span className="text-white">Projected Day Volume / 30-Day Avg Volume</span>. 
              Filtering out stocks with average volume below 500K for high-reliability signals.
            </p>
          </div>
        </div>
      </div>

      {/* Market Opening Predictions - NEW FEATURE */}
      <div className="bg-background-accent/30 border border-bullish/20 rounded-xl p-6 backdrop-blur-md shadow-2xl relative">
        <div className="absolute top-0 right-0 p-3">
          <div className="px-2 py-0.5 rounded text-[8px] font-black tracking-tighter bg-bullish text-black uppercase">
            AI PREDICTIONS
          </div>
        </div>
        
        <h3 className="text-sm font-black tracking-[0.2em] text-white uppercase mb-6 flex items-center">
          <Activity className="w-5 h-5 mr-3 text-bullish animate-pulse" />
          Market Opening Predictions
          <InfoTooltip text="AI-powered intraday trade setups generated by analyzing pre-market financial results, corporate announcements, and regulatory filings." />
          <span className="ml-3 text-[10px] text-content-muted font-normal tracking-normal capitalize">(Based on Latest Corporate Announcements)</span>
        </h3>

        <div className="grid grid-cols-2 gap-8">
          <div className="space-y-4">
            <h4 className="text-[10px] font-black text-bullish tracking-widest uppercase flex items-center border-b border-bullish/10 pb-2">
              <TrendingUp className="w-4 h-4 mr-2" />
              Expected Gainers
            </h4>
            <div className="grid gap-3">
              {expectedGainers.length > 0 ? expectedGainers.map((pred, idx) => (
                <div key={idx} className="bg-white/5 border border-white/5 rounded-lg p-3 hover:bg-bullish/5 transition-all group">
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-lg font-black text-white group-hover:text-bullish">{pred.symbol}</span>
                    <span className="text-[10px] font-bold text-bullish bg-bullish/10 px-2 py-0.5 rounded italic">POSITIVE SENTIMENT</span>
                  </div>
                  <p className="text-[11px] text-content-secondary leading-tight line-clamp-2 italic opacity-80 group-hover:opacity-100 mb-3">
                    "{pred.reason}"
                  </p>
                  <div className="grid grid-cols-2 gap-2 mt-2 border-t border-white/5 pt-2">
                    <div className="flex flex-col">
                      <span className="text-[9px] text-content-muted font-bold uppercase">Entry ({pred.entry_time})</span>
                      <span className="text-xs font-mono font-bold text-white">Rs. {pred.entry_price?.toLocaleString() || "---"}</span>
                    </div>
                    <div className="flex flex-col text-right">
                      <span className="text-[9px] text-content-muted font-bold uppercase">Target (EP +5%)</span>
                      <span className="text-xs font-mono font-bold text-bullish">Rs. {pred.target_price?.toLocaleString() || "---"}</span>
                    </div>
                    <div className="flex flex-col">
                      <span className="text-[9px] text-content-muted font-bold uppercase">Stop Loss (-2%)</span>
                      <span className="text-xs font-mono font-bold text-bearish">Rs. {pred.stop_loss?.toLocaleString() || "---"}</span>
                    </div>
                    <div className="flex flex-col text-right">
                      <span className="text-[9px] text-content-muted font-bold uppercase">Risk ({pred.risk_percentage}%)</span>
                      <span className="text-xs font-mono font-bold text-white">{pred.risk_reward} R/R</span>
                    </div>
                  </div>
                </div>
              )) : (
                <div className="text-content-muted text-xs italic py-4 border border-dashed border-white/5 rounded-lg text-center">No significant bullish announcements found...</div>
              )}
            </div>
          </div>

          <div className="space-y-4">
            <h4 className="text-[10px] font-black text-bearish tracking-widest uppercase flex items-center border-b border-bearish/10 pb-2">
              <TrendingDown className="w-4 h-4 mr-2" />
              Expected Losers
            </h4>
            <div className="grid gap-3">
              {expectedLosers.length > 0 ? expectedLosers.map((pred, idx) => (
                <div key={idx} className="bg-white/5 border border-white/5 rounded-lg p-3 hover:bg-bearish/5 transition-all group">
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-lg font-black text-white group-hover:text-bearish">{pred.symbol}</span>
                    <span className="text-[10px] font-bold text-bearish bg-bearish/10 px-2 py-0.5 rounded italic">NEGATIVE SENTIMENT</span>
                  </div>
                  <p className="text-[11px] text-content-secondary leading-tight line-clamp-2 italic opacity-80 group-hover:opacity-100 mb-3">
                    "{pred.reason}"
                  </p>
                  <div className="grid grid-cols-2 gap-2 mt-2 border-t border-white/5 pt-2">
                    <div className="flex flex-col">
                      <span className="text-[9px] text-content-muted font-bold uppercase">Entry ({pred.entry_time})</span>
                      <span className="text-xs font-mono font-bold text-white">Rs. {pred.entry_price?.toLocaleString() || "---"}</span>
                    </div>
                    <div className="flex flex-col text-right">
                      <span className="text-[9px] text-content-muted font-bold uppercase">Target (EP -5%)</span>
                      <span className="text-xs font-mono font-bold text-bearish">Rs. {pred.target_price?.toLocaleString() || "---"}</span>
                    </div>
                    <div className="flex flex-col">
                      <span className="text-[9px] text-content-muted font-bold uppercase">Stop Loss (+2%)</span>
                      <span className="text-xs font-mono font-bold text-bullish">Rs. {pred.stop_loss?.toLocaleString() || "---"}</span>
                    </div>
                    <div className="flex flex-col text-right">
                      <span className="text-[9px] text-content-muted font-bold uppercase">Risk ({pred.risk_percentage}%)</span>
                      <span className="text-xs font-mono font-bold text-white">{pred.risk_reward} R/R</span>
                    </div>
                  </div>
                </div>
              )) : (
                <div className="text-content-muted text-xs italic py-4 border border-dashed border-white/5 rounded-lg text-center">No significant bearish announcements found...</div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Top Level Metrics */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Market Volume", value: marketData?.volume || "---", sub: "Shares traded today", color: "text-white" },
          { label: "USD / PKR", value: marketData?.usdPkr?.toFixed(2) || "---.--", sub: "Interbank Rate", color: "text-bearish" },
          { label: "Gold (10g)", value: marketData?.gold?.toLocaleString() || "---,---", sub: "PKR", color: "text-bullish" },
          { label: "6M T-Bill Yield", value: marketData?.tBillYield ? `${marketData.tBillYield}%` : "---%", sub: "Latest SBP Auction", color: "text-white" }
        ].map((m, i) => (
          <div key={i} className="panel p-4 flex flex-col justify-between border-white/5 bg-white/5 hover:bg-white/10 transition-colors">
            <span className="data-label">{m.label}</span>
            <div className={`mt-2 text-2xl font-bold font-mono tracking-tight ${m.color}`}>
              {m.value}
            </div>
            <span className="text-content-secondary text-[10px] mt-1 uppercase tracking-tighter opacity-60">
              {m.sub}
            </span>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Expanded Market Watch */}
        <div className="panel flex flex-col col-span-2 shadow-2xl">
          <div className="px-5 py-4 border-b border-border bg-background-accent/50 flex justify-between items-center relative z-10 rounded-t-xl">
            <div className="flex items-center space-x-4">
              <h3 className="text-sm font-black tracking-widest text-white uppercase flex items-center">
                <Search className="w-4 h-4 mr-2 text-content-secondary" />
                Market Watch
                <InfoTooltip text="A comprehensive, real-time view of all trading activity on the KSE-100 index. Use the search bar to find specific ticker symbols instantly." />
              </h3>
              <div className="relative">
                <input 
                  type="text" 
                  placeholder="Search Symbols..."
                  className="bg-background/80 border border-border/50 rounded-lg px-3 py-1.5 text-xs text-white placeholder:text-content-muted focus:outline-none focus:ring-1 focus:ring-bullish/50 w-48 transition-all"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>
            <span className="text-[10px] text-content-muted font-bold tracking-widest uppercase">
              {filteredStocks.length} Stocks Live
            </span>
          </div>
          <div className="p-0 flex-1 max-h-[480px] overflow-y-auto custom-scrollbar">
            <table className="w-full text-left border-collapse">
              <thead className="sticky top-0 z-10">
                <tr className="text-[10px] text-content-secondary bg-background/95 border-b border-border/50 uppercase tracking-tighter shadow-sm">
                  <th className="py-3 px-6 font-black">Symbol</th>
                  <th className="py-3 px-6 font-black text-right">Price</th>
                  <th className="py-3 px-6 font-black text-right">Change</th>
                  <th className="py-3 px-6 font-black text-right">Volume</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {filteredStocks.length > 0 ? (
                  filteredStocks.map((stock) => (
                    <tr
                      key={stock.symbol}
                      className="hover:bg-bullish/5 transition-all group border-l-2 border-transparent hover:border-bullish"
                    >
                      <td className="py-4 px-6">
                        <div className="flex flex-col">
                          <span className="font-black text-sm text-white group-hover:text-bullish transition-colors">
                            {stock.symbol}
                          </span>
                          <span className="text-[9px] text-content-muted font-bold flex items-center">
                            REGULAR <ExternalLink className="w-2 h-2 ml-1 opacity-0 group-hover:opacity-100" />
                          </span>
                        </div>
                      </td>
                      <td className="py-4 px-6 text-right font-mono font-bold text-white text-sm">
                        {stock.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-4 px-6 text-right">
                        <span className={`font-mono font-black text-sm ${stock.change >= 0 ? "text-bullish" : "text-bearish"}`}>
                          {stock.change >= 0 ? "+" : ""}{stock.change.toFixed(2)}%
                        </span>
                      </td>
                      <td className="py-4 px-6 text-right font-mono text-xs text-content-secondary">
                        {stock.volume || "0"}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr><td colSpan={4} className="text-center py-20 text-content-muted text-sm font-bold tracking-widest uppercase opacity-50 animate-pulse">Syncing Bloomberg Terminal Data...</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="flex flex-col space-y-6">
          {/* Movers Mini Tables */}
          <div className="panel overflow-hidden backdrop-blur-xl bg-bullish/5 border-bullish/10">
            <div className="px-5 py-3 border-b border-bullish/20 bg-bullish/10 flex justify-between items-center">
              <h3 className="text-[10px] font-black tracking-widest text-bullish uppercase">
                TOP ADVANCERS
              </h3>
              <TrendingUp className="w-4 h-4 text-bullish" />
            </div>
            <div className="p-0">
              <table className="w-full text-xs">
                <tbody>
                  {gainers.slice(0, 5).map(s => (
                    <tr key={s.symbol} className="border-b border-border/30 last:border-0 hover:bg-bullish/10 transition-colors">
                      <td className="py-3 px-5 font-bold text-white">{s.symbol}</td>
                      <td className="py-3 px-5 text-right font-mono text-content-secondary">{s.price.toFixed(2)}</td>
                      <td className="py-3 px-5 text-right font-mono text-bullish font-bold">+{s.change.toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel overflow-hidden backdrop-blur-xl bg-bearish/5 border-bearish/10">
            <div className="px-5 py-3 border-b border-bearish/20 bg-bearish/10 flex justify-between items-center">
              <h3 className="text-[10px] font-black tracking-widest text-bearish uppercase">
                TOP DECLINERS
              </h3>
              <TrendingDown className="w-4 h-4 text-bearish" />
            </div>
            <div className="p-0">
              <table className="w-full text-xs">
                <tbody>
                  {losers.slice(0, 5).map(s => (
                    <tr key={s.symbol} className="border-b border-border/30 last:border-0 hover:bg-bearish/10 transition-colors">
                      <td className="py-3 px-5 font-bold text-white">{s.symbol}</td>
                      <td className="py-3 px-5 text-right font-mono text-content-secondary">{s.price.toFixed(2)}</td>
                      <td className="py-3 px-5 text-right font-mono text-bearish font-bold">{s.change.toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
