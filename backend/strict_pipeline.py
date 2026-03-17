
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import logging
import pytz
import re

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("PSX_STRICT_PIPELINE")

PKT = pytz.timezone('Asia/Karachi')

# ─────────────────────────────────────────
# VALIDATION GATES
# ─────────────────────────────────────────

def validate_kse100(value: float) -> bool:
    if not (40000 < value < 300000):
        logger.error(f"KSE-100 VALIDATION FAILED: {value}")
        return False
    return True

def validate_change_pct(value: float) -> bool:
    if not (-8.0 < value < 8.0):
        logger.error(f"CHANGE_PCT VALIDATION FAILED: {value}%")
        return False
    return True

def validate_foreign_flow(value_millions: float) -> bool:
    if not (-5000 < value_millions < 5000):
        logger.error(f"FOREIGN FLOW VALIDATION FAILED: {value_millions}M")
        return False
    return True

def validate_pkr_usd(value: float) -> bool:
    if not (200 < value < 450):
        logger.error(f"PKR/USD VALIDATION FAILED: {value}")
        return False
    return True

# ─────────────────────────────────────────
# SCRAPERS
# ─────────────────────────────────────────

def fetch_kse100() -> dict:
    try:
        url = "https://dps.psx.com.pk/"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=15)
        
        # Use a very broad regex to find the KSE100 index in the HTML
        # Look for "KSE100" followed by a number like 65,123.45
        # The structure is often: <div class="...">KSE100</div><div class="...">65,123.45</div>
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Try to find the KSE100 item specifically
        kse_item = soup.find(string=re.compile(r"KSE100", re.I))
        if kse_item:
            parent = kse_item.find_parent()
            # Search nearby for the price and percentage
            # We use regex on the whole parent's text to find the first large number and first percentage
            text = parent.get_text(separator=" ", strip=True)
            # This handles cases where the index name and value are in siblings
            if not re.search(r"\d{2,3},\d{3}", text):
                # Check siblings
                text = parent.find_parent().get_text(separator=" ", strip=True)

            val_match = re.search(r"(\d{2,3},\d{3}\.\d{2})", text)
            pct_match = re.search(r"([+-]?\d+\.\d+)%", text)
            
            if val_match:
                val = float(val_match.group(1).replace(",", ""))
                pct = float(pct_match.group(1)) if pct_match else 0.0
                
                if validate_kse100(val):
                    return {
                        "source": "dps.psx.com.pk (HTML)",
                        "index": val,
                        "change_pct": pct,
                        "fetched_at": datetime.now(PKT).isoformat()
                    }

        # Fallback to the topIndices selector if regex fails
        items = soup.select(".topIndices__item")
        for item in items:
            name_el = item.select_one(".topIndices__item__name")
            if name_el and "KSE100" in name_el.text.upper():
                val = float(item.select_one(".topIndices__item__val").text.replace(",", ""))
                pct_text = item.select_one(".topIndices__item__changep").text.replace("(", "").replace(")", "").replace("%", "")
                pct = float(pct_text)
                return {
                    "source": "dps.psx.com.pk (Selector)",
                    "index": val,
                    "change_pct": pct,
                    "fetched_at": datetime.now(PKT).isoformat()
                }

        raise Exception("KSE100 not found on PSX home page")
    except Exception as e:
        logger.error(f"KSE-100 FETCH FAILED: {e}")
        raise

def fetch_top_movers() -> dict:
    try:
        url = "https://dps.psx.com.pk/"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")

        gainers = []
        losers = []

        # Market Performers tables
        tables = soup.select("table.tbl")
        # index 1 = Advancers, 2 = Decliners
        
        def parse_table(table):
            stocks = []
            for row in table.select("tbody tr")[:5]:
                cols = row.select("td")
                if len(cols) >= 4:
                    stocks.append({
                        "ticker": cols[0].text.strip(),
                        "price": float(cols[2].text.strip().replace(",", "")),
                        "change": float(cols[3].text.strip().replace("%", "").replace("+", ""))
                    })
            return stocks

        if len(tables) >= 3:
            gainers = parse_table(tables[1])
            losers = parse_table(tables[2])
        else:
            # Weekend/Off-hour check - sometimes tables are indexed differently
            # Or they might be under a different class like 'tbl--market-performers'
            logger.info("Standard tables missing, attempting alternate section search")
            market_sect = soup.find('div', id='market-performers')
            if market_sect:
                alt_tables = market_sect.select("table")
                if len(alt_tables) >= 2:
                    gainers = parse_table(alt_tables[0])
                    losers = parse_table(alt_tables[1])
            
        return {"gainers": gainers, "losers": losers, "source": "dps.psx.com.pk"}
    except Exception as e:
        logger.error(f"TOP MOVERS FETCH FAILED: {e}")
        raise

def fetch_foreign_flow() -> dict:
    """
    Scrapes Foreign Flow from NCCPL. 
    Tries multiple report pages and handles Cloudflare.
    """
    try:
        urls = [
            "https://www.nccpl.com.pk/en/market-information/foreign-investors-trading-report",
            "https://www.nccpl.com.pk/en/market-information/foreign-investors-trading-report-fipi"
        ]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Referer": "https://www.google.com/"
        }
        
        for url in urls:
            try:
                res = requests.get(url, headers=headers, timeout=15)
                if res.status_code == 200 and "Total Foreign" in res.text:
                    soup = BeautifulSoup(res.text, "html.parser")
                    row = soup.find(string=re.compile("Total Foreign", re.I)).find_parent("tr")
                    cols = row.find_all("td")
                    
                    def parse_val(t):
                        # Handle cases like (12.3) for negative numbers
                        text = t.strip().replace(",", "").replace("(", "-").replace(")", "")
                        return float(text)

                    net = parse_val(cols[3].text)
                    assert validate_foreign_flow(net), f"Net flow {net}M invalid"
                    
                    return {
                        "source": "nccpl.com.pk",
                        "net_m": net,
                        "direction": "INFLOW" if net > 0 else "OUTFLOW",
                        "fetched_at": datetime.now(PKT).isoformat()
                    }
            except:
                continue

        # If all NCCPL attempts fail, use the PSX mirror fallback
        logger.warning("NCCPL Blocked or Layout changed. Attempting PSX Mirror...")
        return fetch_fipi_from_psx_fallback()

    except Exception as e:
        logger.error(f"FOREIGN FLOW FETCH FAILED: {e}")
        raise

def fetch_fipi_from_psx_fallback():
    """
    PSX mirrors the latest FIPI net total in their market summary section or slider.
    """
    try:
        url = "https://dps.psx.com.pk/"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Look for the 'Net' value near 'FIPI'
        # Often in a carousel or summary table with labels like 'FIPI'
        fipi_item = soup.find(string=re.compile(r"FIPI", re.I))
        if fipi_item:
            # Look for the next number in the sibling elements or table cells
            parent = fipi_item.find_parent()
            # Searching for numbers like (+1.23) or (-5.67) in the nearby text
            nearby_text = parent.find_parent().get_text(separator=" ", strip=True)
            # Find the value which is usually a float in millions
            val_match = re.search(r"Net\s*[:]\s*([+-]?\d+\.\d+)", nearby_text, re.I)
            if not val_match:
                # Try just finding any signed float near FIPI
                val_match = re.search(r"([+-]?\d+\.\d+)", nearby_text)
                
            if val_match:
                net = float(val_match.group(1))
                return {
                    "source": "dps.psx.com.pk (Mirror)",
                    "net_m": net,
                    "direction": "INFLOW" if net > 0 else "OUTFLOW",
                    "fetched_at": datetime.now(PKT).isoformat()
                }
                
        # If not found in main page, check the Market summary tab content specifically
        # which is sometimes embedded in the HTML
        raise Exception("FIPI not found on PSX mirror")
    except Exception as e:
        logger.error(f"FIPI MIRROR ERROR: {e}")
        raise

def fetch_pkr_usd() -> dict:
    """
    Scrapes PKR/USD from SBP. Tries M2M and WAR pages.
    """
    try:
        # SBP M2M page is usually the most stable for automation
        urls = [
            "https://www.sbp.org.pk/ecodata/rates/m2m/M2M-Current.asp",
            "https://www.sbp.org.pk/ecodata/index2.asp"
        ]
        headers = {"User-Agent": "Mozilla/5.0"}
        
        for url in urls:
            try:
                res = requests.get(url, headers=headers, timeout=10)
                res.encoding = res.apparent_encoding
                
                # Check for USD rate using a refined regex
                # Pakistan rates are typically 270.00 to 290.00 currently
                # We search for any number with 2 decimal places near 'USD'
                matches = re.findall(r"USD.*?(\d{3}\.\d{2,4})", res.text, re.DOTALL | re.I)
                if not matches:
                    # Try a broader search for any rate in the 200-400 range
                    matches = re.findall(r"(\d{3}\.\d{2,4})", res.text)
                    # Filter for plausible PKR/USD rates
                    valid_rates = [float(m) for m in matches if 250 < float(m) < 350]
                else:
                    valid_rates = [float(m) for m in matches if 250 < float(m) < 350]

                if valid_rates:
                    rate = valid_rates[0]
                    return {"rate": rate, "source": f"sbp.org.pk ({url.split('/')[-1]})", "fetched_at": datetime.now(PKT).isoformat()}
            except:
                continue
        
        # Last resort: Try Home Page Sidebar (if it was text-accessible)
        # But for now, we report the failure to adhere to the strict rule.
        raise Exception("Rate not found in SBP sources")

    except Exception as e:
        logger.error(f"PKR/USD FETCH FAILED: {e}")
        raise

# ─────────────────────────────────────────
# MASTER PIPELINE
# ─────────────────────────────────────────

def run_strict_pipeline() -> dict:
    data = {}
    errors = []
    
    stages = [
        ("kse100", fetch_kse100),
        ("top_movers", fetch_top_movers),
        ("foreign_flow", fetch_foreign_flow),
        ("pkr_usd", fetch_pkr_usd)
    ]
    
    for key, func in stages:
        try:
            data[key] = func()
        except Exception as e:
            errors.append(f"{key}: {str(e)}")
            
    if "kse100" not in data or "top_movers" not in data:
        return {"status": "failed", "errors": errors}
        
    return {
        "status": "success",
        "data": data,
        "errors": errors,
        "generated_at": datetime.now(PKT).isoformat()
    }

if __name__ == "__main__":
    print(json.dumps(run_strict_pipeline(), indent=2))
