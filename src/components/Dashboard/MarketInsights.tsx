import { useState, useEffect } from "react";
import { doc, onSnapshot, collection, query, orderBy, limit } from "firebase/firestore";
import { db } from "../../firebase";
import { 
  Sparkles, 
  TrendingUp, 
  Newspaper, 
  Gauge,
  Zap,
  Info
} from "lucide-react";

interface AI_Brief {
  english_summary: string[];
  urdu_brief: string;
  sentiment_score: number;
  market_outlook: string;
  top_movers_insight: string;
  generated_at: string;
}

interface Announcement {
  id: string;
  headline: string;
  symbol: string;
  sentiment_score?: number;
  sentiment_label?: string;
  created_at: string;
}

export default function MarketInsights() {
  const [brief, setBrief] = useState<AI_Brief | null>(null);
  const [anncs, setAnncs] = useState<Announcement[]>([]);
  const [lang, setLang] = useState<"en" | "ur">("en");

  useEffect(() => {
    // 1. Listen for latest AI brief
    const unsubBrief = onSnapshot(doc(db, "market_briefs", "latest"), (doc) => {
      if (doc.exists()) setBrief(doc.data() as AI_Brief);
    });

    // 2. Listen for latest scored announcements
    const q = query(
      collection(db, "announcements"), 
      orderBy("created_at", "desc"), 
      limit(5)
    );
    const unsubAnncs = onSnapshot(q, (snapshot) => {
      setAnncs(snapshot.docs.map(d => ({ id: d.id, ...d.data() } as Announcement)));
    });

    return () => {
      unsubBrief();
      unsubAnncs();
    };
  }, []);

  const sentimentColor = (score: number) => {
    if (score >= 7) return "text-bullish";
    if (score <= 4) return "text-bearish";
    return "text-orange-400";
  };

  const sentimentBG = (score: number) => {
    if (score >= 7) return "bg-bullish/10 border-bullish/20";
    if (score <= 4) return "bg-bearish/10 border-bearish/20";
    return "bg-orange-400/10 border-orange-400/20";
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* 1. AI Market Analysis (Main Section) */}
      <div className="lg:col-span-2 bg-background-accent/40 border border-border/50 rounded-xl overflow-hidden backdrop-blur-md shadow-2xl">
        <div className="px-6 py-4 border-b border-border/50 bg-white/5 flex justify-between items-center">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-blue-500/10 rounded-lg">
              <Sparkles className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h3 className="text-sm font-black tracking-[0.2em] text-white uppercase italic">
                Antigravity AI <span className="text-content-muted font-normal not-italic ml-1">Daily Brief</span>
              </h3>
              <p className="text-[10px] text-content-muted font-bold tracking-tight">
                LLM-Synthesized Multi-Source Market Intelligence
              </p>
            </div>
          </div>
          <div className="flex bg-white/5 p-1 rounded-lg border border-white/5">
            <button 
              onClick={() => setLang("en")}
              className={`px-3 py-1 rounded text-[10px] font-black uppercase transition-all ${lang === "en" ? "bg-white/10 text-white" : "text-content-muted hover:text-white"}`}
            >
              EN
            </button>
            <button 
              onClick={() => setLang("ur")}
              className={`px-3 py-1 rounded text-[10px] font-black uppercase transition-all ${lang === "ur" ? "bg-white/10 text-white" : "text-content-muted hover:text-white"}`}
            >
              اردو
            </button>
          </div>
        </div>

        <div className="p-6 relative min-h-[300px]">
          {!brief ? (
            <div className="flex flex-col items-center justify-center h-full py-12 opacity-50">
              <Zap className="w-8 h-8 text-blue-400 animate-pulse mb-4" />
              <p className="text-xs font-black uppercase tracking-widest text-content-muted">Processing overnight data...</p>
            </div>
          ) : (
            <div className="space-y-6">
              {lang === "en" ? (
                <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2">
                  <div className="grid grid-cols-2 gap-4">
                    <div className={`p-4 rounded-xl border relative overflow-hidden transition-all hover:scale-[1.02] ${sentimentBG(brief.sentiment_score)}`}>
                      <span className="text-[10px] font-black uppercase tracking-widest block mb-1 opacity-70 text-white">Sentiment Outlook</span>
                      <span className={`text-xl font-black font-mono relative z-10 ${sentimentColor(brief.sentiment_score)}`}>
                        {brief.market_outlook}
                      </span>
                      <Gauge className={`absolute -right-2 -bottom-2 w-16 h-16 opacity-10 transition-transform group-hover:rotate-12 ${sentimentColor(brief.sentiment_score)}`} />
                    </div>
                    <div className="p-4 rounded-xl border border-white/5 bg-white/5 relative overflow-hidden transition-all hover:scale-[1.02]">
                      <span className="text-[10px] font-black uppercase tracking-widest block mb-1 opacity-70 text-white">Sentiment Score</span>
                      <div className="flex items-center space-x-2 relative z-10">
                        <span className={`text-2xl font-black font-mono ${sentimentColor(brief.sentiment_score)}`}>{brief.sentiment_score}</span>
                        <span className="text-xs text-content-muted font-bold">/ 10</span>
                      </div>
                      <div className="absolute left-0 bottom-0 w-full h-1 bg-white/10">
                        <div 
                          className={`h-full transition-all duration-1000 ease-out ${sentimentBG(brief.sentiment_score).split(' ')[0].replace('/10', '')}`} 
                          style={{ width: `${brief.sentiment_score * 10}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <h4 className="text-[10px] font-black uppercase tracking-widest text-white/50 border-b border-white/5 pb-2">Key Highlights</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3">
                      {Array.isArray(brief.english_summary) ? (
                        brief.english_summary.map((point: string, i: number) => (
                          <div key={i} className="flex items-start space-x-3 group">
                            <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)] group-hover:scale-125 transition-transform" />
                            <p className="text-xs text-content-secondary leading-relaxed font-medium">
                              {point}
                            </p>
                          </div>
                        ))
                      ) : (
                        <div className="col-span-2 flex items-start space-x-3 group">
                          <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)] group-hover:scale-125 transition-transform" />
                          <p className="text-xs text-content-secondary leading-relaxed font-medium whitespace-pre-wrap">
                            {brief.english_summary}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="bg-white/5 border border-white/5 rounded-xl p-4">
                    <h4 className="text-[10px] font-black uppercase tracking-widest text-blue-400 mb-2 flex items-center">
                      <TrendingUp className="w-3 h-3 mr-2" />
                      Sector & Ticker Insight
                    </h4>
                    <p className="text-[11px] text-content-secondary leading-relaxed italic">
                      "{brief.top_movers_insight}"
                    </p>
                  </div>
                </div>
              ) : (
                <div className="animate-in fade-in slide-in-from-right-2 text-right">
                  <div className={`p-4 rounded-xl border mb-6 inline-block bg-white/5 border-white/10`}>
                    <span className={`text-2xl font-black font-mono inline-flex items-center`}>
                      <span className="text-xs text-content-muted font-bold mr-4 uppercase tracking-[0.2em]">مارکیٹ سینٹیمنٹ</span>
                      {brief.sentiment_score} / 10
                    </span>
                  </div>
                  <p className="text-2xl leading-[2.2] text-white font-medium py-4" style={{ fontFamily: '"Noto Nastaliq Urdu", "Jameel Noori Nastaleeq", serif', direction: 'rtl' }}>
                    {brief.urdu_brief}
                  </p>
                </div>
              )}
              
              <div className="mt-8 flex items-center justify-between opacity-50 border-t border-white/5 pt-4">
                <span className="text-[8px] font-black uppercase tracking-widest flex items-center">
                  <Info className="w-2.5 h-2.5 mr-1.5" />
                  Generated by Groq-70B Llama 3 v3
                </span>
                <span className="text-[10px] font-mono font-bold">
                  {new Date(brief.generated_at).toLocaleString()}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 2. Announcement Pulse (Scored Feed) */}
      <div className="bg-background-accent/40 border border-border/50 rounded-xl overflow-hidden flex flex-col backdrop-blur-md">
        <div className="px-6 py-4 border-b border-border/50 bg-white/5 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Newspaper className="w-5 h-5 text-bullish" />
            <h3 className="text-sm font-black tracking-[0.2em] text-white uppercase">Announcement <span className="text-bullish">Score</span></h3>
          </div>
        </div>

        <div className="flex-1 divide-y divide-white/5 overflow-y-auto max-h-[460px]">
          {anncs.length > 0 ? (
            anncs.map((annc) => (
              <div key={annc.id} className="p-4 hover:bg-white/5 transition-all group relative overflow-hidden">
                <div className="flex justify-between items-start mb-1.5">
                  <span className="text-[10px] font-black px-2 py-0.5 bg-white/10 rounded-md text-white tracking-widest uppercase">
                    {annc.symbol}
                  </span>
                  {annc.sentiment_label && (
                    <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full border ${
                      annc.sentiment_label === 'Bullish' ? 'bg-bullish/20 text-bullish border-bullish/30' : 
                      annc.sentiment_label === 'Bearish' ? 'bg-bearish/20 text-bearish border-bearish/30' : 
                      'bg-white/10 text-white/50 border-white/10'
                    }`}>
                      {annc.sentiment_label}
                    </span>
                  )}
                </div>
                <h4 className="text-[11px] font-bold text-white leading-snug group-hover:text-bullish transition-colors mb-2">
                  {annc.headline}
                </h4>
                <div className="flex items-center justify-between">
                   <div className="flex items-center space-x-2">
                    {annc.sentiment_score !== undefined && (
                      <div className="flex items-center space-x-0.5">
                        <div className="w-12 h-1 bg-white/10 rounded-full overflow-hidden">
                          <div 
                            className={`h-full rounded-full ${annc.sentiment_score > 0 ? 'bg-bullish' : 'bg-bearish'}`} 
                            style={{ width: `${Math.abs(annc.sentiment_score) * 100}%` }} 
                          />
                        </div>
                        <span className="text-[8px] font-bold text-content-muted font-mono">{Math.abs(annc.sentiment_score).toFixed(2)}</span>
                      </div>
                    )}
                   </div>
                   <span className="text-[9px] font-mono font-bold text-content-muted">
                    {new Date(annc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                   </span>
                </div>
              </div>
            ))
          ) : (
            <div className="p-12 text-center opacity-30 italic text-xs">Waiting for announcements...</div>
          )}
        </div>
        
        <div className="p-3 bg-white/5 border-t border-white/5 text-center">
          <button className="text-[10px] font-black uppercase tracking-widest text-content-muted hover:text-white transition-colors">
            View Analysis History
          </button>
        </div>
      </div>
    </div>
  );
}
