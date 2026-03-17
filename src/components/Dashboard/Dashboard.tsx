import { useState, useEffect, useMemo } from "react";
import { doc, onSnapshot } from "firebase/firestore";
import { db } from "../../firebase";
import {
  Search,
  TrendingUp,
  TrendingDown,
  Activity,
  ExternalLink,
  Info,
  Clock,
  Lock,
} from "lucide-react";
import MarketInsights from "./MarketInsights";
import KSEChart from "./KSEChart";

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
  <div className="relative group ml-1.5 inline-flex items-center">
    <Info className="w-3 h-3 text-content-muted hover:text-white transition-colors cursor-help" />
    <div className="absolute left-1/2 -translate-x-1/2 top-full mt-2 w-64 p-3 bg-[#111318] border border-white/10 rounded-xl text-[10px] text-content-secondary leading-relaxed opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all shadow-[0_20px_50px_rgba(0,0,0,0.5)] z-[99999] pointer-events-none font-medium backdrop-blur-2xl">
      {text}
      <div className="absolute left-1/2 -translate-x-1/2 bottom-full w-0 h-0 border-l-[6px] border-r-[6px] border-b-[6px] border-l-transparent border-r-transparent border-b-white/10"></div>
    </div>
  </div>
);

export default function Dashboard() {
  const [marketData, setMarketData] = useState<MarketData | null>(null);
  const [gainers, setGainers] = useState<Stock[]>([]);
  const [losers, setLosers] = useState<Stock[]>([]);
  const [allStocks, setAllStocks] = useState<Stock[]>([]);
  const [volumeSpikes, setVolumeSpikes] = useState<VolumeSpike[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [predictionTimeframe, setPredictionTimeframe] = useState<
    "day" | "week" | "month"
  >("day");
  const [predictions, setPredictions] = useState<any[]>([]);
  const [predictionUpdated, setPredictionUpdated] = useState<string>("");

  const MarketStatusBanner = () => {
    const phase = marketData?.phase || "CLOSED";
    const date =
      marketData?.final_data_date ||
      new Date().toLocaleTimeString([], { day: "2-digit", month: "short" });

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
    const unsubMovers = onSnapshot(
      doc(db, "market_movers", "latest"),
      (doc) => {
        if (doc.exists()) {
          const data = doc.data();
          setGainers(data?.top_gainers || []);
          setLosers(data?.top_losers || []);
        }
      },
    );



    // Expanded Market Watch
    const unsubAllStocks = onSnapshot(
      doc(db, "market_watch", "latest"),
      (doc) => {
        if (doc.exists()) setAllStocks(doc.data()?.stocks || []);
      },
    );

    // Volume Spike Screener
    const unsubSpikes = onSnapshot(
      doc(db, "volume_spikes", "latest"),
      (doc) => {
        if (doc.exists()) {
          setVolumeSpikes(doc.data()?.spikes || []);
        }
      },
    );

    // AI Prediction Engine (Day/Week/Month)
    const unsubDayPred = onSnapshot(
      doc(db, "predictions", "latest_day"),
      (doc) => {
        if (predictionTimeframe === "day" && doc.exists()) {
          const data = doc.data();
          setPredictions(data.data || []);
          setPredictionUpdated(data.updated_at);
        }
      },
    );

    const unsubWeekPred = onSnapshot(
      doc(db, "predictions", "latest_week"),
      (doc) => {
        if (predictionTimeframe === "week" && doc.exists()) {
          const data = doc.data();
          setPredictions(data.data || []);
          setPredictionUpdated(data.updated_at);
        }
      },
    );

    const unsubMonthPred = onSnapshot(
      doc(db, "predictions", "latest_month"),
      (doc) => {
        if (predictionTimeframe === "month" && doc.exists()) {
          const data = doc.data();
          setPredictions(data.data || []);
          setPredictionUpdated(data.updated_at);
        }
      },
    );

    return () => {
      unsubData();
      unsubMovers();

      unsubAllStocks();
      unsubSpikes();
      unsubDayPred();
      unsubWeekPred();
      unsubMonthPred();
    };
  }, [predictionTimeframe]);

  const filteredStocks = useMemo(() => {
    if (!searchQuery) return allStocks;
    return allStocks.filter((s) =>
      s.symbol.toLowerCase().includes(searchQuery.toLowerCase()),
    );
  }, [allStocks, searchQuery]);

  return (
    <div className="space-y-6 pb-12">
      <MarketStatusBanner />

      {/* Index Performance Sections */}
      {/* New Advanced KSE-100 Chart API Implementation */}
      <KSEChart symbol="KSE100" />
      

      <MarketInsights />

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
                Last updated:{" "}
                {new Date().toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
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
              {volumeSpikes.length > 0 ? (
                volumeSpikes.slice(0, 10).map((spike) => (
                  <tr
                    key={spike.symbol}
                    className="hover:bg-white/5 transition-all group"
                  >
                    <td className="py-4 px-6">
                      <span className="font-black text-white group-hover:text-bullish transition-colors">
                        {spike.symbol}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-right font-mono text-xs text-white">
                      {spike.today_vol >= 1000000
                        ? `${(spike.today_vol / 1000000).toFixed(1)}M`
                        : `${(spike.today_vol / 1000).toFixed(1)}K`}
                    </td>
                    <td className="py-4 px-6 text-right font-mono text-xs text-content-muted">
                      {spike.avg_vol >= 1000000
                        ? `${(spike.avg_vol / 1000000).toFixed(1)}M`
                        : `${(spike.avg_vol / 1000).toFixed(1)}K`}
                    </td>
                    <td className="py-4 px-6 text-center">
                      <div className="flex justify-center">
                        <span
                          className={`px-3 py-1 rounded-lg font-black text-xs ${
                            spike.spike_ratio >= 4
                              ? "bg-bearish/20 text-bearish border border-bearish/30"
                              : spike.spike_ratio >= 3
                                ? "bg-orange-500/20 text-orange-500 border border-orange-500/30"
                                : "bg-bullish/20 text-bullish border border-bullish/30"
                          }`}
                        >
                          {spike.spike_ratio}x
                        </span>
                      </div>
                    </td>
                    <td className="py-4 px-6 text-right font-mono font-bold text-white text-sm">
                      {spike.price?.toFixed(2) || "0.00"}
                    </td>
                    <td className="py-4 px-6 text-right">
                      <span
                        className={`font-mono font-black text-xs ${(spike.change || 0) >= 0 ? "text-bullish" : "text-bearish"}`}
                      >
                        {(spike.change || 0) >= 0 ? "+" : ""}
                        {(spike.change || 0).toFixed(2)}%
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={6}
                    className="py-12 text-center text-content-muted text-xs font-bold uppercase tracking-[0.2em] opacity-50"
                  >
                    No significant volume spikes detected so far...
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <div className="px-6 py-3 bg-white/5 border-t border-border/50">
            <p className="text-[9px] text-content-muted font-bold leading-relaxed max-w-3xl">
              <span className="text-bullish">PROJECTION LOGIC:</span> Volume is
              projected based on time elapsed since market open (9:30 AM PKT).
              Spike ratio ={" "}
              <span className="text-white">
                Projected Day Volume / 30-Day Avg Volume
              </span>
              . Filtering out stocks with average volume below 500K for
              high-reliability signals.
            </p>
          </div>
        </div>
      </div>

      {/* Multi-Timeframe Signal Scoring Engine */}
      <div className="bg-background-accent/30 border border-border rounded-xl p-0 backdrop-blur-md shadow-2xl relative">
        <div className="px-6 py-5 border-b border-border bg-white/[0.02] flex justify-between items-center">
          <div className="flex items-center space-x-4">
            <h3 className="text-sm font-black tracking-[0.2em] text-white uppercase flex items-center">
              <Activity className="w-5 h-5 mr-3 text-bullish animate-pulse" />
              Signal Scoring Engine
              <InfoTooltip text="Automated scoring system weights stocks across 15+ technical and fundamental signals (RSI, Vol Accumulation, MA Crosses, and PSX Announcements) to predict probability of move." />
            </h3>

            <div className="flex bg-white/5 p-1 rounded-lg border border-white/5 ml-4">
              {(["day", "week", "month"] as const).map((tf) => (
                <button
                  key={tf}
                  onClick={() => setPredictionTimeframe(tf)}
                  className={`px-4 py-1.5 rounded-md text-[10px] font-black uppercase tracking-widest transition-all ${
                    predictionTimeframe === tf
                      ? "bg-bullish text-black shadow-lg"
                      : "text-content-muted hover:text-white"
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-[10px] text-content-muted font-bold uppercase tracking-tighter">
              Updated:
            </span>
            <span className="text-[11px] font-mono text-white font-bold">
              {predictionUpdated
                ? new Date(predictionUpdated).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "--:--"}{" "}
              PKT
            </span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="text-[10px] text-content-secondary bg-white/[0.03] uppercase tracking-tighter border-b border-border/50">
                <th className="py-4 px-6 font-black">Symbol</th>
                <th className="py-4 px-6 font-black text-center">
                  Score
                  <InfoTooltip text="Aggregate points (0-100) based on technical setup + fundamental catalysts. >60 is considered high probability." />
                </th>
                <th className="py-4 px-6 font-black text-center">
                  Bias
                  <InfoTooltip text="The overall market sentiment for this stock based on its score: Strong Bullish, Bullish, Watch, Neutral, etc." />
                </th>
                <th className="py-4 px-6 font-black">
                  Active Signals Fired
                  <InfoTooltip text="The underlying logic that triggered this score (e.g., RSI zone, Volume Accumulation, Sector rotation)." />
                </th>
                <th className="py-4 px-6 font-black text-right">
                  Run Price
                  <InfoTooltip text="The nominal market price of the stock at the moment the AI scoring engine was executed (9:00 AM PKT)." />
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/10">
              {predictions.length > 0 ? (
                predictions.map((pred, idx) => (
                  <tr
                    key={idx}
                    className="hover:bg-white/[0.02] transition-colors group"
                  >
                    <td className="py-4 px-6">
                      <span className="text-sm font-black text-white group-hover:text-bullish transition-colors">
                        {pred.symbol}
                      </span>
                    </td>
                    <td className="py-4 px-6">
                      <div className="flex flex-col items-center justify-center">
                        <div className="w-16 h-1 w-full bg-white/5 rounded-full overflow-hidden mb-1">
                          <div
                            className={`h-full transition-all duration-1000 ${
                              pred.score >= 75
                                ? "bg-bullish shadow-[0_0_8px_rgba(34,197,94,0.5)]"
                                : pred.score >= 50
                                  ? "bg-bullish/60"
                                  : "bg-content-muted"
                            }`}
                            style={{ width: `${pred.score}%` }}
                          />
                        </div>
                        <span className="text-xs font-black font-mono text-white">
                          {pred.score}
                        </span>
                      </div>
                    </td>
                    <td className="py-4 px-6 text-center">
                      <div className="flex items-center justify-center space-x-2">
                        <div
                          className={`w-2 h-2 rounded-full animate-pulse ${
                            pred.bias?.includes("BULLISH")
                              ? "bg-bullish"
                              : pred.bias?.includes("WATCH")
                                ? "bg-yellow-400"
                                : "bg-content-muted"
                          }`}
                        />
                        <span
                          className={`text-[10px] font-black tracking-widest uppercase ${
                            pred.bias?.includes("BULLISH")
                              ? "text-bullish"
                              : pred.bias?.includes("WATCH")
                                ? "text-yellow-400"
                                : "text-content-muted"
                          }`}
                        >
                          {pred.bias?.replace("_", " ")}
                        </span>
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      <div className="flex flex-wrap gap-1.5">
                        {pred.signals_fired?.map(
                          (sig: string, sIdx: number) => (
                            <span
                              key={sIdx}
                              className="px-2 py-0.5 rounded-md bg-white/5 border border-white/5 text-[9px] font-bold text-content-secondary group-hover:text-white transition-colors"
                            >
                              {sig}
                            </span>
                          ),
                        )}
                      </div>
                    </td>
                    <td className="py-4 px-6 text-right">
                      <span className="text-xs font-mono font-bold text-white italic">
                        Rs. {pred.price_at_run?.toLocaleString()}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="py-20 text-center">
                    <div className="flex flex-col items-center space-y-3 opacity-30">
                      <Lock className="w-8 h-8 text-content-muted" />
                      <span className="text-xs font-black tracking-widest uppercase">
                        Syncing Cloud Intelligence...
                      </span>
                      <span className="text-[10px] font-bold text-content-muted italic">
                        Scoring engine runs daily at 9:00 AM PKT
                      </span>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Engine Methodology & Legend */}
        <div className="px-6 py-5 bg-white/[0.03] border-t border-border/50">
          <div className="grid grid-cols-3 gap-8">
            <div className="space-y-2">
              <h4 className="text-[10px] font-black text-white uppercase tracking-widest">
                Aggregate scoring (0-100)
              </h4>
              <p className="text-[9px] text-content-muted leading-relaxed">
                Our AI weights 15+ indicators.{" "}
                <span className="text-bullish font-bold">Technicals</span> (RSI
                Trend, MA Crosses, Vol Accumulation) provide 60% of the weight,
                while <span className="text-bullish font-bold">Catalysts</span>{" "}
                (PSX Announcements, Sector Rotation) provide the remaining 40%.
              </p>
            </div>
            <div className="space-y-2">
              <h4 className="text-[10px] font-black text-white uppercase tracking-widest">
                Bias Thresholds
              </h4>
              <div className="flex flex-wrap gap-2 pt-1">
                <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-bullish text-black">
                  75+ STRONG BULLISH
                </span>
                <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-bullish/40 text-white">
                  60+ BULLISH
                </span>
                <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-white/10 text-white">
                  45+ WATCH
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <h4 className="text-[10px] font-black text-white uppercase tracking-widest">
                Price Re-anchoring
              </h4>
              <p className="text-[9px] text-content-muted leading-relaxed">
                <span className="text-white font-bold italic">Run Price</span>{" "}
                is the actual nominal price from PSX. We automatically re-anchor
                historical 6-month adjusted data to this nominal price to ensure
                MA20/MA50 and RSI calculations are mathematically precise.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Top Level Metrics */}
      <div className="grid grid-cols-4 gap-4">
        {[
          {
            label: "Market Volume",
            value: marketData?.volume || "---",
            sub: "Shares traded today",
            color: "text-white",
          },
          {
            label: "USD / PKR",
            value: marketData?.usdPkr?.toFixed(2) || "---.--",
            sub: "Interbank Rate",
            color: "text-bearish",
          },
          {
            label: "Gold (10g)",
            value: marketData?.gold?.toLocaleString() || "---,---",
            sub: "PKR",
            color: "text-bullish",
          },
          {
            label: "6M T-Bill Yield",
            value: marketData?.tBillYield
              ? `${marketData.tBillYield}%`
              : "---%",
            sub: "Latest SBP Auction",
            color: "text-white",
          },
        ].map((m, i) => (
          <div
            key={i}
            className="panel p-4 flex flex-col justify-between border-white/5 bg-white/5 hover:bg-white/10 transition-colors"
          >
            <span className="data-label">{m.label}</span>
            <div
              className={`mt-2 text-2xl font-bold font-mono tracking-tight ${m.color}`}
            >
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
                            REGULAR{" "}
                            <ExternalLink className="w-2 h-2 ml-1 opacity-0 group-hover:opacity-100" />
                          </span>
                        </div>
                      </td>
                      <td className="py-4 px-6 text-right font-mono font-bold text-white text-sm">
                        {stock.price.toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                        })}
                      </td>
                      <td className="py-4 px-6 text-right">
                        <span
                          className={`font-mono font-black text-sm ${stock.change >= 0 ? "text-bullish" : "text-bearish"}`}
                        >
                          {stock.change >= 0 ? "+" : ""}
                          {stock.change.toFixed(2)}%
                        </span>
                      </td>
                      <td className="py-4 px-6 text-right font-mono text-xs text-content-secondary">
                        {stock.volume || "0"}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td
                      colSpan={4}
                      className="text-center py-20 text-content-muted text-sm font-bold tracking-widest uppercase opacity-50 animate-pulse"
                    >
                      Syncing Bloomberg Terminal Data...
                    </td>
                  </tr>
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
                  {gainers.slice(0, 5).map((s) => (
                    <tr
                      key={s.symbol}
                      className="border-b border-border/30 last:border-0 hover:bg-bullish/10 transition-colors"
                    >
                      <td className="py-3 px-5 font-bold text-white">
                        {s.symbol}
                      </td>
                      <td className="py-3 px-5 text-right font-mono text-content-secondary">
                        {s.price.toFixed(2)}
                      </td>
                      <td className="py-3 px-5 text-right font-mono text-bullish font-bold">
                        +{s.change.toFixed(2)}%
                      </td>
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
                  {losers.slice(0, 5).map((s) => (
                    <tr
                      key={s.symbol}
                      className="border-b border-border/30 last:border-0 hover:bg-bearish/10 transition-colors"
                    >
                      <td className="py-3 px-5 font-bold text-white">
                        {s.symbol}
                      </td>
                      <td className="py-3 px-5 text-right font-mono text-content-secondary">
                        {s.price.toFixed(2)}
                      </td>
                      <td className="py-3 px-5 text-right font-mono text-bearish font-bold">
                        {s.change.toFixed(2)}%
                      </td>
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
