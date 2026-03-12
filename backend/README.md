# PSX Insider AI Backend

FastAPI backend serving Machine Learning models (XGBoost, Random Forest, FinBERT) for the Pakistan Stock Exchange.

## Stack
- Python 3.10+
- FastAPI
- yfinance (for free KSE-100 data)
- XGBoost + Scikit-Learn (Price Direction)
- HuggingFace Transformers (FinBERT sentiment)

## Running
```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```
