import os
import re
import time
import logging
import asyncio
import json
from datetime import datetime
from bs4 import BeautifulSoup
from shared import db, PKT
from dotenv import load_dotenv

# Load API keys from .env
load_dotenv()

# --- AI DEPENDENCIES ---
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    import torch.nn.functional as F
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False
    logger = logging.getLogger(__name__)
    logger.warning("Transformers/Torch not found. Sentiment scoring will be disabled.")

try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

# Setup logging
logger = logging.getLogger(__name__)

# --- 1. SENTIMENT ANALYSIS (FinBERT) ---
MODEL_NAME = "ProsusAI/finbert"
_tokenizer = None
_model = None

def get_finbert():
    """Singleton loader for FinBERT model"""
    global _tokenizer, _model
    if not HAS_TRANSFORMERS:
        return None, None
    if _model is None:
        try:
            logger.info(f"Loading {MODEL_NAME} (this may take a moment)...")
            # Set HF_HUB_DISABLE_SYMLINKS_WARNING to suppress Windows warnings
            os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
            _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            _model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
            logger.info("[OK] FinBERT loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load FinBERT: {e}")
            return None, None
    return _tokenizer, _model

def score_sentiment(text):
    """
    Scores financial text and returns a value between -1 and 1.
    """
    tokenizer, model = get_finbert()
    if not model or not text:
        return 0.0
    
    try:
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            outputs = model(**inputs)
        
        probs = F.softmax(outputs.logits, dim=-1)
        pos = probs[0][0].item()
        neg = probs[0][1].item()
        
        # Weighted score logic
        score = (pos * 1.0) + (neg * -1.0)
        return round(score, 3)
    except Exception as e:
        logger.error(f"Sentiment scoring error: {e}")
        return 0.0

# --- 2. MARKET BRIEF GENERATOR ---
async def generate_market_brief():
    """
    Synthesizes daily market activity into English and Urdu briefs using LLMs.
    """
    if not db: return
    
    today_str = datetime.now(PKT).strftime("%Y-%m-%d")
    
    # Check if brief already generated for today
    existing = db.collection("market_briefs").document(today_str).get()
    if existing.exists:
        logger.info(f"Market brief for {today_str} already exists.")
        # We still want to return to ensure "latest" is synced
        latest_data = existing.to_dict()
        db.collection("market_briefs").document("latest").set(latest_data)
        return

    # 1. Gather Context
    try:
        macro_doc = db.collection("macro_history").document(today_str).get()
        macro = macro_doc.to_dict() if macro_doc.exists else {}
        
        market_doc = db.collection("market_data").document("latest").get()
        market_data = market_doc.to_dict() if market_doc.exists else {}

        # Pull additional data for context
        movers_doc = db.collection("market_movers").document("latest").get()
        movers = movers_doc.to_dict() if movers_doc.exists else {}
        
        sectors_doc = db.collection("market_sectors").document("latest").get()
        sectors = sectors_doc.to_dict() if sectors_doc.exists else {"sectors": []}
        
        kse100 = market_data.get('kse100', {})
        kse100_val = kse100.get('value') if isinstance(kse100, dict) else "0"
        kse100_change = kse100.get('change') if isinstance(kse100, dict) else "0"
        kse100_pts = kse100.get('points') if isinstance(kse100, dict) else "0"
        
        kse30 = market_data.get('kse30', {})
        kse30_change = kse30.get('change', 0) if isinstance(kse30, dict) else 0
        
        top_gainers = [f"{str(s.get('symbol', ''))} (+{str(s.get('change', 0))}%)" for s in (movers.get('top_gainers', []) if isinstance(movers, dict) else [])]
        top_losers = [f"{str(s.get('symbol', ''))} ({str(s.get('change', 0))}%)" for s in (movers.get('top_losers', []) if isinstance(movers, dict) else [])]
        top_sectors = [f"{str(s.get('name', ''))} ({str(s.get('change', 0))}%)" for s in (sectors.get('sectors', [])[:3] if isinstance(sectors, dict) else [])]
        
        news_docs = db.collection("news").where("scraped_at", ">=", today_str).limit(10).get()
        annc_docs = db.collection("announcements").where("created_at", ">=", today_str).limit(10).get()
        
        top_news = [d.to_dict().get("content", "")[:150] for d in news_docs]
        anncs = [d.to_dict().get("headline", "") for d in annc_docs]
        
        market_dir = "Bullish / Positive" if float(str(kse100_change)) > 0 else "Bearish / Negative"
        if float(str(kse100_change)) == 0: market_dir = "Neutral / Sideways"

        context = f"""
        DATE: {today_str}
        MARKET SENTIMENT: {market_dir}
        KSE-100 INDEX: {kse100_val} (PRECISE VALUE)
        KSE-100 CHANGE: {kse100_pts} points ({kse100_change}%)
        KSE-30 CHANGE: {kse30_change}%
        
        ALLOWED_STOCKS_FOR_GAINERS: {', '.join(top_gainers) or 'N/A'}
        ALLOWED_STOCKS_FOR_LOSERS: {', '.join(top_losers) or 'N/A'}
        TOP_PERFORMING_SECTOR: {top_sectors[0] if top_sectors else 'N/A'}
        
        MACRO DATA:
        - USD/PKR: {str(macro.get('usdPkr', '278.40'))}
        - Brent Oil: ${str(macro.get('brentOil', '82.40'))}/bbl
        
        TOP NEWS: {'; '.join(top_news) or 'No major news'}
        """
        
        groq_key = os.getenv("GROQ_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        
        if not any([groq_key, anthropic_key, openai_key]):
            logger.warning("No LLM API keys found. Briefly skipping AI generation.")
            return

        prompt = f"""
        Act as 'Antigravity AI', a lead financial strategist for the Pakistan Stock Exchange. 
        Your task is to synthesize today's market data into a highly professional, "Bloomberg-style" market brief.

        ### MARKET CONTEXT (REAL DATA - DO NOT HALLUCINATE):
        {context}

        ### GROUNDED ANALYSIS RULES:
        1. Use ONLY the data provided above. If a fact is not in the data, do not mention it.
        2. Every number you write must come from the data above.
        3. Do NOT invent any stock symbols, percentages, or reasons for movement.

        ### SYSTEM RULES:
        1. **NUMERICAL PRECISION**: Use the exact number {kse100_val} for KSE-100. DO NOT ROUND.
        2. **ZERO TOLERANCE FOR HALLUCINATION**: 
           - You are FORBIDDEN from mentioning any stock symbol or name NOT in the ALLOWED lists.
           - If a name like 'TRG', 'Systems', or 'HBL' is NOT in the allowed list, DO NOT MENTION IT.
           - Use the symbols as provided (e.g., 'YOUW', 'MEHT').
        3. **SENTIMENT**: KSE-100 is {market_dir}. Reflect this in the tone.
        4. **STRUCTURE**:
           - Bullet 1: Index value and change.
           - Bullet 2: Top Gainers (pick from ALLOWED_STOCKS_FOR_GAINERS).
           - Bullet 3: Top Losers (pick from ALLOWED_STOCKS_FOR_LOSERS).
        5. **OBLIGATION**: Mention specific names from the allowed lists. Do not be generic.

        ### REQUIREMENTS:
        1. **English Summary**: 3-4 professional bullet points using financial terminology.
        2. **Urdu Market Brief**: A deep, insightful paragraph in high-quality formal "Business Urdu".
        3. **Sentiment Gauge**: A score from 1-10 (1: Extreme Fear, 5: Neutral, 10: Extreme Greed). 
        4. **Key Movers Analysis**: Mention specific gainers/losers or sectors from the context.

        ### FORMAT:
        You MUST return ONLY a valid JSON object:
        {{
          "english_summary": [ "...", "..." ],
          "urdu_brief": "...",
          "sentiment_score": 5.0,
          "market_outlook": "Short-term bullish/neutral/bearish",
          "top_movers_insight": "..."
        }}
        """
        
        raw_text = ""
        if HAS_GROQ and groq_key:
            try:
                logger.info("Using Groq (Llama-3) for AI brief generation...")
                client = Groq(api_key=groq_key)
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt.replace("{context}", context)}],
                    response_format={"type": "json_object"},
                    temperature=0.3
                )
                raw_text = completion.choices[0].message.content
            except Exception as e: logger.error(f"Groq failed: {e}")

        if not raw_text and HAS_ANTHROPIC and anthropic_key:
            try:
                client = Anthropic(api_key=anthropic_key)
                message = client.messages.create(
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=1500,
                    messages=[{"role": "user", "content": prompt.replace("{{context}}", context)}]
                )
                raw_text = message.content[0].text
            except Exception as e: logger.error(f"Anthropic count failed: {e}")

        if not raw_text and HAS_OPENAI and openai_key:
            try:
                client = OpenAI(api_key=openai_key)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    response_format={"type": "json_object"},
                    messages=[{"role": "user", "content": prompt.replace("{{context}}", context)}]
                )
                raw_text = response.choices[0].message.content
            except Exception as e: logger.error(f"OpenAI failed: {e}")
        
        if not raw_text: return
            
        brief_data = json.loads(raw_text)
        brief_data["date"] = today_str
        brief_data["generated_at"] = datetime.now(PKT).isoformat()
        
        db.collection("market_briefs").document(today_str).set(brief_data)
        db.collection("market_briefs").document("latest").set(brief_data)
        logger.info("[OK] AI Market Brief updated.")
        
    except Exception as e:
        logger.error(f"Brief generation failed: {e}")

async def generate_chart_commentary():
    """Morning job to generate exactly one line of context for KSE100 chart."""
    if not db: return
    try:
        import yfinance as yf
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key or not HAS_GROQ:
            return

        # KSE100 data from Firestore for reliability
        market_doc = db.collection("market_data").document("latest").get()
        market_data = market_doc.to_dict() if market_doc.exists else {}
        kse100 = market_data.get('kse100', {})
        level = float(kse100.get('value', 0).replace(',', '') if isinstance(kse100.get('value'), str) else kse100.get('value', 0))
        chg_pct_raw = kse100.get('change', 0)
        chg_pct = float(chg_pct_raw) if chg_pct_raw else 0.0

        if level == 0:
            logger.warning("generate_chart_commentary: KSE100 data unavailable in Firestore.")
            return
        
        # Flow data
        flow_docs = db.collection("foreign_flow").order_by("date", direction="DESCENDING").limit(1).get()
        flow = flow_docs[0].to_dict() if flow_docs else {"bias": "Neutral", "net": 0}

        prompt = f"""
        KSE-100: {level:,.0f} ({chg_pct:+.2f}% today)
        Foreign flow: {flow.get('bias', 'Neutral')} net Rs. {flow.get('net', 0)}M
        
        Write ONE sentence max 25 words of market context for a Pakistani retail trader. Specific, no fluff.
        """
        
        client = Groq(api_key=groq_key)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
            temperature=0.3
        )
        
        commentary = resp.choices[0].message.content.strip()
        
        db.collection("market_briefs").document("latest").set({
            "chart_commentary": commentary
        }, merge=True)
        
        today_str = datetime.now(PKT).strftime("%Y-%m-%d")
        db.collection("market_briefs").document(today_str).set({
            "chart_commentary": commentary
        }, merge=True)
        
        logger.info(f"[OK] Chart commentary generated: {commentary}")
    except Exception as e:
        logger.error(f"Failed to generate chart commentary: {e}")

# --- 3. BATCH SCORING ---
def batch_score_sentiments():
    if not db: return
    for col in ["news", "announcements"]:
        docs = db.collection(col).where("sentiment_scored", "==", False).limit(20).get()
        for doc in docs:
            try:
                data = doc.to_dict()
                text = data.get("content", data.get("headline", ""))
                score = score_sentiment(text)
                doc.reference.update({
                    "sentiment_score": score,
                    "sentiment_label": "Bullish" if score > 0.1 else ("Bearish" if score < -0.1 else "Neutral"),
                    "sentiment_scored": True
                })
            except: continue

# --- 4. SIGNAL ENGINE ---
def update_ticker_signals():
    logger.info("Updating ticker signals...")
    try:
        spikes_doc = db.collection("volume_spikes").document("latest").get()
        if not spikes_doc.exists: return
        
        spikes = spikes_doc.to_dict().get("spikes", [])
        signals = []
        
        for s in spikes:
            symbol = s['symbol']
            vol_score = min(s['spike_ratio'] * 10, 40)
            
            sentiment_score = 0
            # Simplified query to avoid index requirement
            recent_news = db.collection("news").where("tickers", "array_contains", symbol).limit(5).get()
            if recent_news:
                scores = [d.to_dict().get("sentiment_score", 0) for d in recent_news]
                sentiment_score = (sum(scores) / len(scores)) * 40
            
            total_score = round(vol_score + sentiment_score + 20, 1)
            
            signals.append({
                "symbol": symbol,
                "score": total_score,
                "bias": "Strong Bullish" if total_score > 75 else ("Bullish" if total_score > 60 else "Watch"),
                "signals": ["Vol Spike", "AI Sentiment" if sentiment_score != 0 else "Technical"],
                "run_price": s['price'],
                "updated_at": datetime.now(PKT).isoformat()
            })
            
        signals = sorted(signals, key=lambda x: x['score'], reverse=True)[:10]
        db.collection("predictions").document("latest_day").set({
            "data": signals,
            "updated_at": datetime.now(PKT).isoformat()
        })
    except Exception as e:
        logger.error(f"Signal failed: {e}")

def run_ai_layer():
    logger.info("--- AI PULSE START ---")
    batch_score_sentiments()
    asyncio.run(generate_market_brief())
    update_ticker_signals()
    logger.info("--- AI PULSE COMPLETE ---")

if __name__ == "__main__":
    run_ai_layer()
