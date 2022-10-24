import requests
import os

if "API_KEY" not in os.environ:
    print("Run: API_KEY=<insert key here> python3 main.py")
    exit(0)

API_KEY = os.environ.get("API_KEY")

def quote(symbol):
    data = requests.get(f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}")
    data = data.json()
    return data['c']

