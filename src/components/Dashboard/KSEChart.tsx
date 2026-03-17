import { useEffect, useRef, useState } from "react";
import { createChart, CrosshairMode, LineSeries, HistogramSeries } from "lightweight-charts";
import "./KSEChart.css"; // Or assume Tailwind classes, but we can generate inline or standard classes

export default function KSEChart({ symbol = "KSE100" }) {
  const chartRef = useRef<HTMLDivElement>(null);
  const flowRef = useRef<HTMLDivElement>(null);
  const [tf, setTf] = useState("3M");
  const [data, setData] = useState<any>(null);
  const [overlays, setOverlays] = useState({
    ma20: true, ma50: true, ma200: false,
    volume: true, flow: true, events: true
  });

  const timeframes = ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y"];

  useEffect(() => {
    fetch(`http://localhost:8000/api/chart/${symbol}?timeframe=${tf}`)
      .then(r => r.json())
      .then(setData)
      .catch(console.error);
  }, [symbol, tf]);

  useEffect(() => {
    if (!data || !chartRef.current) return;

    // Clear previous
    chartRef.current.innerHTML = "";
    if (flowRef.current) flowRef.current.innerHTML = "";

    // Main chart
    const chart = createChart(chartRef.current, {
      height: 420,
      layout: {
        background: { color: "#09090b" }, // Zinc-950 roughly
        textColor: "#a1a1aa" // Zinc-400
      },
      grid: {
        vertLines: { color: "#27272a" }, // Zinc-800
        horzLines: { color: "#27272a" }
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#27272a" },
      timeScale: {
        borderColor: "#27272a",
        timeVisible: true,
      }
    });

    // Check if we have valid OHLCV
    if (!data.ohlcv || data.ohlcv.length === 0) {
      const el = document.createElement('div');
      el.className = 'text-content-muted text-sm flex items-center justify-center h-full w-full';
      el.innerText = 'No chart data available.';
      chartRef.current.appendChild(el);
      return () => { chart.remove(); };
    }

    // Index line
    const line = chart.addSeries(LineSeries, {
      color: "#00c896", lineWidth: 2,
      priceLineVisible: false,
    });
    line.setData(data.ohlcv.map((d: any) => ({
      time: d.time, value: d.close
    })));

    // MA overlays
    if (overlays.ma20 && data.ma20?.length) {
      const s = chart.addSeries(LineSeries, {
        color: "#f0a500", lineWidth: 1,
        lineStyle: 1, priceLineVisible: false,
        title: "MA20"
      });
      s.setData(data.ma20);
    }

    if (overlays.ma50 && data.ma50?.length) {
      const s = chart.addSeries(LineSeries, {
        color: "#4361ee", lineWidth: 1,
        lineStyle: 1, priceLineVisible: false,
        title: "MA50"
      });
      s.setData(data.ma50);
    }

    if (overlays.ma200 && data.ma200?.length) {
      const s = chart.addSeries(LineSeries, {
        color: "#ef5350", lineWidth: 1,
        lineStyle: 2, priceLineVisible: false,
        title: "MA200"
      });
      s.setData(data.ma200);
    }



    // Volume pane
    if (overlays.volume) {
      const volSeries = chart.addSeries(HistogramSeries, {
        color: "#27272a",
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      });
      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 }
      });
      volSeries.setData(data.ohlcv.map((d: any) => ({
        time: d.time, value: d.volume,
        color: d.close >= d.open ? "rgba(0, 200, 150, 0.25)" : "rgba(239, 83, 80, 0.25)"
      })));
    }

    // Foreign flow chart (synced)
    let flowChart: any = null;
    if (overlays.flow && data.foreign_flow?.length && flowRef.current) {
      flowChart = createChart(flowRef.current, {
        height: 100,
        layout: { background: { color: "#09090b" }, textColor: "#a1a1aa" },
        grid: { vertLines: { color: "#27272a" }, horzLines: { color: "#27272a" } },
        timeScale: { visible: false },
        rightPriceScale: { borderColor: "#27272a" },
      });
      const flowBars = flowChart.addSeries(HistogramSeries, { priceLineVisible: false });
      
      const flowData = data.foreign_flow.map((d: any) => {
        const t = typeof d.date === 'string' ? new Date(d.date).getTime() / 1000 : d.date;
        return {
          time: t,
          value: d.value,
          color: d.color
        };
      }).filter((d: any) => !isNaN(d.time)).sort((a: any, b: any) => a.time - b.time);

      // Lightweight charts requires unique time values ascending. We might need to handle duplicates in flowdata
      // We skip it if duplicate
      const uniqueFlowData = [];
      const seenTimes = new Set();
      for (const item of flowData) {
        if (!seenTimes.has(item.time)) {
          seenTimes.add(item.time);
          uniqueFlowData.push(item);
        }
      }
      flowBars.setData(uniqueFlowData);

      // Sync time scales
      chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range && flowChart) flowChart.timeScale().setVisibleLogicalRange(range);
      });
    }

    return () => { 
      chart.remove(); 
      if (flowChart) flowChart.remove();
    };
  }, [data, overlays]);

  if (!data) return (
    <div className="flex h-96 items-center justify-center bg-card-bg border border-white/5 rounded-2xl">
      <div className="animate-pulse flex flex-col items-center">
        <div className="w-8 h-8 rounded-full border-2 border-bullish border-t-transparent animate-spin mb-4" />
        <span className="text-content-muted text-sm">Loading Chart Data...</span>
      </div>
    </div>
  );

  return (
    <div className="kse-chart-wrapper">
      {/* AI Commentary Bar */}
      {data.ai_commentary && (
        <div className="commentary-bar">
          <span className="zain-dot">●</span>
          <span>{data.ai_commentary}</span>
        </div>
      )}

      {/* Index Header */}
      <div className="index-header">
        <div style={{display: 'flex', alignItems: 'center'}}>
          <div className="text-2xl font-bold tracking-tight mr-4">{symbol}</div>
          <div className="index-value">
            {data.stats?.current?.toLocaleString() || "---"}
          </div>
          <div className={`index-change ${(data.stats?.change || 0) >= 0 ? "up" : "down"}`}>
            {(data.stats?.change || 0) >= 0 ? "▲" : "▼"} 
            {Math.abs(data.stats?.change || 0).toLocaleString()} ({data.stats?.change_pct || 0}%)
          </div>
        </div>
        <div className="index-meta">
          <div>O: {data.stats?.open}  H: {data.stats?.high}  L: {data.stats?.low}  PC: {data.stats?.prev_close}</div>
          <div>52w H/L: {data.stats?.["52w_high"]} / {data.stats?.["52w_low"]}</div>
        </div>
      </div>

      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px'}}>
        {/* Timeframe Buttons */}
        <div className="tf-buttons">
          {timeframes.map(t => (
            <button key={t}
              className={tf === t ? "active" : ""}
              onClick={() => setTf(t)}>{t}</button>
          ))}
        </div>

        {/* Overlay Toggles */}
        <div className="overlay-toggles">
          {Object.keys(overlays).map(key => (
            <button key={key}
              className={(overlays as Record<string, boolean>)[key] ? "active" : ""}
              onClick={() => setOverlays((p: any) => ({...p, [key]: !p[key]}))}>
              {key.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Main Chart */}
      <div ref={chartRef} className="main-chart" />

      {/* Flow Label */}
      {overlays.flow && (
        <div className="pane-label">Foreign Flow (PKR M) - {tf}</div>
      )}
      <div ref={flowRef} className="flow-chart" />

      <div style={{display: 'flex', gap: '16px'}}>
        <div style={{flex: 1}}>
            <div className="pane-label" style={{marginBottom: '4px'}}>Market Breadth</div>
            {/* Breadth Bar */}
            <div className="breadth-bar">
                <span className="up">▲ {data.breadth?.advances} Advancing</span>
                <span className="neutral">● {data.breadth?.unchanged} Unchanged</span>
                <span className="down">▼ {data.breadth?.declines} Declining</span>
            </div>
        </div>

        {/* Returns Table */}
        <div className="returns-table" style={{flex: 1}}>
          <table>
            <thead>
              <tr><th>Period</th><th>Return</th><th>vs Inflation</th></tr>
            </thead>
            <tbody>
              {data.returns && Object.entries(data.returns).map(([period, ret]) => {
                const numRet = ret as number;
                return (
                <tr key={period}>
                  <td>{period}</td>
                  <td className={numRet >= 0 ? "up" : "down"}>{numRet !== null ? `${numRet > 0 ? '+' : ''}${numRet}%` : "—"}</td>
                  <td className={numRet >= (23.5/(365/((period === '1M' ? 30 : period === '3M' ? 90 : period === '6M' ? 180 : 365)))) ? "up" : "down"}>
                    {numRet !== null ? (numRet > (23.5/(365/((period === '1M' ? 30 : period === '3M' ? 90 : period === '6M' ? 180 : 365)))) ? "Beating" : "Lagging") : "—"}
                  </td>
                </tr>
              )})}
            </tbody>
          </table>
        </div>
      </div>
    </div>

  );
}
