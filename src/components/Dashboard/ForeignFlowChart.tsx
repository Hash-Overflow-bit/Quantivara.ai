import { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  AreaSeries,
  HistogramSeries,
  LineSeries,
  LineStyle,
} from "lightweight-charts";
import {
  Activity,
  TrendingUp,
  TrendingDown,
  Info,
} from "lucide-react";
import {
  onSnapshot,
  collection,
  query,
  orderBy,
  limit,
} from "firebase/firestore";
import { db } from "../../firebase";

interface FlowPoint {
  date: string;
  net: number;
  rolling_5d: number;
  rolling_30d: number;
  signal_state?: string;
  confidence?: number;
}

interface IndexPoint {
  time: string;
  value: number;
}

interface ForeignFlowData {
  flow_data: FlowPoint[];
  index_data: IndexPoint[];
  summary: {
    last_5d_net: number;
    last_30d_net: number;
    current_bias: string;
    confidence?: number;
  };
  last_updated?: string;
}

const InfoTooltip = ({ text }: { text: string }) => (
  <div className="relative group ml-1.5 inline-flex items-center">
    <Info className="w-3 h-3 text-content-muted hover:text-white transition-colors cursor-help" />
    <div className="absolute left-1/2 -translate-x-1/2 top-full mt-2 w-64 p-3 bg-[#111318] border border-white/10 rounded-xl text-[10px] text-content-secondary leading-relaxed opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all shadow-2xl z-[99999] pointer-events-none font-medium backdrop-blur-2xl">
      {text}
      <div className="absolute left-1/2 -translate-x-1/2 bottom-full w-0 h-0 border-l-[6px] border-r-[6px] border-b-[6px] border-l-transparent border-r-transparent border-b-white/10"></div>
    </div>
  </div>
);

export default function ForeignFlowChart() {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const flowContainerRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<ForeignFlowData | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeframe, setTimeframe] = useState<"5d" | "30d">("5d");
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const chartsRef = useRef<{ chart?: any; flowChart?: any }>({});

  // Phase 4: Real-time Firestore listener
  useEffect(() => {
    let unsubscribe: (() => void) | null = null;

    const initializeListener = async () => {
      try {
        // First fetch initial data from API
        const res = await fetch("http://localhost:8000/api/foreign-flow");
        const apiData = await res.json();
        setData(apiData);
        setLastUpdated(
          new Date().toLocaleString("en-PK", { timeZone: "Asia/Karachi" }),
        );

        // Then set up real-time listener
        const q = query(
          collection(db, "foreign_flow"),
          orderBy("date", "desc"),
          limit(100),
        );

        unsubscribe = onSnapshot(q, (snapshot) => {
          const flows: FlowPoint[] = [];
          snapshot.docs.forEach((doc) => {
            const data = doc.data();
            flows.push({
              date: data.date,
              net: data.net || 0,
              rolling_5d: data.rolling_5d || 0,
              rolling_30d: data.rolling_30d || 0,
              signal_state: data.signal_state,
              confidence: data.confidence,
            });
          });

          // Reverse to get chronological order
          flows.reverse();

          setData((prev) =>
            prev
              ? {
                  ...prev,
                  flow_data: flows,
                  summary: {
                    ...prev.summary,
                    confidence: flows[flows.length - 1]?.confidence,
                  },
                }
              : null,
          );

          setLastUpdated(
            new Date().toLocaleString("en-PK", { timeZone: "Asia/Karachi" }),
          );
          setLoading(false);
        });
      } catch (error) {
        console.error("Failed to initialize Firestore listener:", error);
        setLoading(false);
      }
    };

    initializeListener();
    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (!data || !chartContainerRef.current || !flowContainerRef.current)
      return;
    if (!data.flow_data || data.flow_data.length === 0) {
      console.warn("ForeignFlowChart: Empty flow_data received");
      return;
    }
    // index_data is now optional for rendering the flow bars
    const hasIndex = data.index_data && data.index_data.length > 0;
    if (!hasIndex) {
      console.warn("ForeignFlowChart: No index_data available, rendering flow only");
    }

    const containerWidth = chartContainerRef.current.clientWidth || 800;
    const chartOptions = {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "rgba(255, 255, 255, 0.05)" },
        horzLines: { color: "rgba(255, 255, 255, 0.05)" },
      },
      width: containerWidth,
      height: 300,
      timeScale: {
        borderColor: "rgba(255, 255, 255, 0.1)",
      },
      handleScroll: true,
      handleScale: true,
    };

    const chart = createChart(chartContainerRef.current, chartOptions);
    const flowChart = createChart(flowContainerRef.current, {
      ...chartOptions,
      height: 120,
      timeScale: {
        visible: false,
      },
    });

    chartsRef.current = { chart, flowChart };

    try {
      // 1. KSE-100 Price Series
      const mainSeries = chart.addSeries(AreaSeries, {
        lineColor: "#22c55e",
        topColor: "rgba(34, 197, 94, 0.3)",
        bottomColor: "rgba(34, 197, 94, 0.0)",
        lineWidth: 2,
      });
      if (data.index_data && data.index_data.length > 0) {
        mainSeries.setData(data.index_data);
      }

      // 2. Foreign Flow Histogram with green/red coloring
      const flowSeries = flowChart.addSeries(HistogramSeries, {
        priceFormat: {
          type: "volume",
        },
      });

      const flowData = data.flow_data
        .filter((d) => d && d.date && d.net !== undefined)
        .map((d) => ({
          time: d.date,
          value: d.net,
          color: d.net >= 0 ? "#22c55e" : "#ef4444",
        }));

      if (flowData && flowData.length > 0) {
        flowSeries.setData(flowData);
      }

      // 3. Rolling Average Line - switch between 5D/30D based on window state
      const rollingSeries = flowChart.addSeries(LineSeries, {
        color:
          timeframe === "5d"
            ? "rgba(255, 193, 7, 0.8)"
            : "rgba(156, 39, 176, 0.8)",
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
      });

      const rollingData = data.flow_data
        .filter(
          (d) =>
            d &&
            d.date &&
            (timeframe === "5d" ? d.rolling_5d : d.rolling_30d) !== undefined,
        )
        .map((d) => ({
          time: d.date,
          value: timeframe === "5d" ? d.rolling_5d : d.rolling_30d,
        }));

      if (rollingData && rollingData.length > 0) {
        rollingSeries.setData(rollingData);
      }

      // Sync charts
      chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (range) flowChart.timeScale().setVisibleLogicalRange(range);
      });

      flowChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (range) chart.timeScale().setVisibleLogicalRange(range);
      });
    } catch (error) {
      console.error("ForeignFlowChart rendering error:", error);
    }

    const handleResize = () => {
      if (chartContainerRef.current) {
        const newWidth = chartContainerRef.current.clientWidth || 800;
        chart.applyOptions({ width: newWidth });
        flowChart.applyOptions({ width: newWidth });
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      try {
        chart.remove();
        flowChart.remove();
      } catch (e) {
        console.warn("Error cleaning up charts:", e);
      }
    };
  }, [data, timeframe]);

  const getSignalColor = (state?: string) => {
    switch (state) {
      case "ACCUMULATING":
        return "bg-bullish text-black";
      case "DISTRIBUTING":
        return "bg-bearish text-white";
      default:
        return "bg-white/10 text-white";
    }
  };

  const getSignalIcon = (state?: string) => {
    switch (state) {
      case "ACCUMULATING":
        return "📈";
      case "DISTRIBUTING":
        return "📉";
      default:
        return "⏸️";
    }
  };

  if (loading)
    return (
      <div className="h-[420px] flex items-center justify-center opacity-30 text-xs font-black uppercase tracking-widest bg-white/5 rounded-xl border border-white/5 animate-pulse">
        Initializing Flow Intelligence...
      </div>
    );

  if (!data || !data.flow_data || data.flow_data.length === 0)
    return (
      <div className="h-[420px] flex flex-col items-center justify-center opacity-40 text-xs font-black uppercase tracking-widest bg-white/5 rounded-xl border border-white/5">
        <div className="text-content-muted text-center space-y-2">
          <div>No Foreign Flow Data Available</div>
          <div className="text-[9px] opacity-60 font-normal">Backfilling initial data - check again in a moment</div>
        </div>
      </div>
    );

  const latestFlow = data?.flow_data?.[data.flow_data.length - 1];
  const signal = latestFlow?.signal_state || data?.summary?.current_bias;

  return (
    <div className="bg-background-accent/40 border border-border/50 rounded-xl overflow-hidden shadow-2xl backdrop-blur-md">
      {/* Header & Signal Badge */}
      <div className="px-6 py-5 border-b border-white/5 flex justify-between items-start bg-white/[0.02]">
        <div className="flex items-start space-x-4">
          <div>
            <h3 className="text-sm font-black tracking-[0.2em] text-white uppercase flex items-center mb-2">
              <Activity className="w-4 h-4 mr-2 text-bullish" />
              Foreign Flow Overlay
              <InfoTooltip text="Correlates KSE-100 price movement (top pane) with Net Foreign Portfolio Investment flows (bottom pane). Critical for identifying Institutional accumulation vs distribution." />
            </h3>
            {/* Enhanced Signal Badge with Confidence */}
            <div className="flex items-center space-x-2">
              <span
                className={`px-3 py-1.5 rounded-lg text-xs font-black uppercase tracking-widest ${getSignalColor(signal)} shadow-lg flex items-center space-x-2 animate-pulse`}
              >
                <span>{getSignalIcon(signal)}</span>
                <span>{signal || "NEUTRAL"}</span>
                {data?.summary?.confidence && (
                  <span className="opacity-75">
                    ({Math.round(data.summary.confidence * 100)}%)
                  </span>
                )}
              </span>
              {lastUpdated && (
                <div className="text-[9px] text-content-muted font-mono">
                  Updated: {lastUpdated}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-col items-end space-y-3">
          {/* Window Toggle - 5D/30D */}
          <div className="flex space-x-2 bg-white/5 rounded-lg p-1">
            <button
              onClick={() => setTimeframe("5d")}
              className={`px-3 py-1 rounded text-xs font-bold uppercase transition-all ${
                timeframe === "5d"
                  ? "bg-yellow-500/80 text-black shadow-lg"
                  : "text-content-muted hover:text-white"
              }`}
            >
              5D
            </button>
            <button
              onClick={() => setTimeframe("30d")}
              className={`px-3 py-1 rounded text-xs font-bold uppercase transition-all ${
                timeframe === "30d"
                  ? "bg-purple-500/80 text-white shadow-lg"
                  : "text-content-muted hover:text-white"
              }`}
            >
              30D
            </button>
          </div>

          {/* Net Flow Stats */}
          <div className="flex items-center space-x-6">
            <div className="text-right">
              <div className="text-[9px] text-content-muted font-bold uppercase tracking-tighter mb-0.5">
                5D Net
              </div>
              <div
                className={`text-xs font-mono font-black ${data?.summary?.last_5d_net && data.summary.last_5d_net >= 0 ? "text-bullish" : "text-bearish"}`}
              >
                {data?.summary?.last_5d_net
                  ? (data.summary.last_5d_net >= 0 ? "+" : "") +
                    Math.round(data.summary.last_5d_net)
                  : "0"}
                M
              </div>
            </div>
            <div className="text-right border-l border-white/5 pl-6">
              <div className="text-[9px] text-content-muted font-bold uppercase tracking-tighter mb-0.5">
                30D Net
              </div>
              <div
                className={`text-xs font-mono font-black ${data?.summary?.last_30d_net && data.summary.last_30d_net >= 0 ? "text-bullish" : "text-bearish"}`}
              >
                {data?.summary?.last_30d_net
                  ? (data.summary.last_30d_net >= 0 ? "+" : "") +
                    Math.round(data.summary.last_30d_net)
                  : "0"}
                M
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-2">
        {/* Main Chart Pane */}
        <div
          ref={chartContainerRef}
          className="rounded-lg overflow-hidden border border-white/[0.03] w-full"
          style={{ height: "300px", minWidth: "400px" }}
        />

        {/* Flow Pane */}
        <div
          ref={flowContainerRef}
          className="rounded-lg overflow-hidden border border-white/[0.03] w-full"
          style={{ height: "120px", minWidth: "400px" }}
        />
      </div>

      {/* Footer Info */}
      <div className="px-6 py-4 bg-white/[0.03] border-t border-white/5 grid grid-cols-2 gap-8">
        <div className="flex items-start space-x-3">
          <TrendingUp className="w-4 h-4 text-bullish mt-0.5 shrink-0" />
          <div className="space-y-1">
            <h4 className="text-[10px] font-black text-white uppercase tracking-widest">
              Inflow Signal
            </h4>
            <p className="text-[9px] text-content-muted leading-relaxed">
              Green bars show net foreign buying. Sustained inflows
              (ACCUMULATING) often precede major index breakouts.
            </p>
          </div>
        </div>
        <div className="flex items-start space-x-3">
          <TrendingDown className="w-4 h-4 text-bearish mt-0.5 shrink-0" />
          <div className="space-y-1">
            <h4 className="text-[10px] font-black text-white uppercase tracking-widest">
              Outflow Signal
            </h4>
            <div className="text-[9px] text-content-muted leading-relaxed">
              Red bars show net foreign selling. Institutional exits often act
              as a leading indicator for market corrections.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
