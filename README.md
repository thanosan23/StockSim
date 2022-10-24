# StockSim

StockSim is a stock portfolio site that can be used to practice your investing skills using real-time stock market data.

StockSim was primarily made using Python and Flask. Market data is fetched from [Finnhub](https://finnhub.io/), a free and amazing stock API.


To run the server, ensure that you have a created the database. This can be done using:
```
sqlite3 database.db < schema.sql
```

To run the program, you also need a FinnHub API key. This can be obtained for free on FinnHub's website. Once you have an API Key, run:
```
API_KEY=<your apikey> python3 main.py
```
