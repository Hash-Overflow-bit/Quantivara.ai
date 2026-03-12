from scraper import get_market_indices
import json

indices = get_market_indices()
print(json.dumps(indices, indent=2))
