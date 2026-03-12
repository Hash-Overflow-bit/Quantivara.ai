from scraper import generate_expected_movers
import json

print("--- TESTING EXPECTED MOVERS ---")
predictions = generate_expected_movers()
print(json.dumps(predictions, indent=2))
