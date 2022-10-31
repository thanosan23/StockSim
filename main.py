import os
import functools
from datetime import datetime

from flask import Flask, flash, g, jsonify, redirect, render_template, session, url_for, request
from werkzeug.security import generate_password_hash, check_password_hash
from gevent.pywsgi import WSGIServer

from database import connect_to_db, query_db
from stocks import quote

app = Flask(__name__)

class Config:
    DATABASE_NAME ="database.db"
    SECRET_KEY = os.urandom(12).hex()
    HASH_TYPE = "sha256"
    PROD = False
    HOST = '0.0.0.0'
    PORT = 3000

app.config['SECRET_KEY'] = Config.SECRET_KEY

# utilities
def get_time():
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


def db_write(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        func(*args, **kwargs)
        g.conn.commit()
    return wrapper

def must_be_logged_in(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash("Invalid URL!", "danger")
            return redirect(url_for('homepage'))
        return func(*args, **kwargs)
    return wrapper

@db_write
def insert_user(username, password):
    g.conn.execute("insert into user (username, password_hash, profit) values (?, ?, ?)",
                   [username, password, 0.0])

@db_write
def insert_stock(symbol, shares, purchase_price):
    g.conn.execute("insert into stocks (user_id, symbol, shares, purchase_price, purchase_time) values (?, ?, ?, ?, ?)",
                   [session['user_id'], symbol, shares, purchase_price, get_time()])
# requests
@app.before_request
def before_request():
    # create database connection before every request
    g.conn = connect_to_db(Config.DATABASE_NAME)
    if 'user_id' in session:
        g.user = query_db(g.conn, 'select * from user where user_id = ?', [session['user_id']])
        if g.user is not None:
            g.user = g.user[0]
    else:
        g.user = None

@app.teardown_request
def teardown_request(_):
    # close database connection at the end of every request
    if g.conn is not None:
        g.conn.close()

@app.route('/')
def homepage():
    return render_template("about.html")

@app.route('/login', methods=['GET', 'POST'])
def loginpage():
    if request.method == "GET":
        return render_template("login.html")
    else:
        data = request.form
        username = data.get("username")
        userdata = query_db(g.conn, 'select * from user where username = ?', [username])
        if userdata is None:
            flash("User doesn't exist!", "danger")
            return redirect(url_for('loginpage'))
        else:
            userdata = userdata[0]
            password = data.get("password")
            if password is not None:
                if check_password_hash(userdata['password_hash'], password):
                    user_id = userdata['user_id']
                    g.conn.commit()
                    session['user_id'] = user_id
                    flash("Logged in", "success")
                else:
                    flash("Password is incorrect!", "danger")
                    return redirect(url_for('loginpage'))
            else:
                    flash("Please enter a password!", "danger")
                    return redirect(url_for('loginpage'))

        return redirect(url_for('homepage'))

@app.route('/signup', methods=['GET', 'POST'])
def signuppage():
    if request.method == "GET":
        return render_template("signup.html")
    else:
        data = request.form
        username = data.get("username")
        userdata = query_db(g.conn, 'select * from user where username = ?', [username])
        if userdata is None:
            password_hash = generate_password_hash(str(data.get("password")), Config.HASH_TYPE)
            insert_user(username, password_hash)
            flash("User has been created!", "success")
            return redirect(url_for('homepage'))
        else:
            flash("Username exists!", "danger")
            return redirect(url_for("signuppage"))

@app.route('/logout')
@must_be_logged_in
def logout():
    session.pop('user_id', None)
    flash("Logged out successfully!", "success")
    return redirect(url_for('homepage'))

@app.route('/portfolio')
@must_be_logged_in
def portfolio():
    stocks = []
    stockdata = query_db(g.conn, "select * from stocks where user_id = ?", [session['user_id']])
    if stockdata is not None:
        for stock in stockdata:
            s = {'symbol' : stock['symbol'], 'shares' : stock['shares'],
                           'purchase_price' : round(stock['shares'] * stock['purchase_price'], 2),
                           'price' : round(stock['shares'] * quote(stock['symbol']), 2),
                 'time' : stock['purchase_time']}
            delta = round(s['price'] - s['purchase_price'], 2)
            s['delta'] = delta
            stocks.append(s)
    return render_template("portfolio.html", stocks=stocks, profit=round(g.user['profit'], 2))

@app.route("/quote", methods=["POST"])
@must_be_logged_in
def quoteStock():
    if request.method == "POST":
        stock = request.form.get("stock")
        flash(f"{stock} Stock Price: {quote(stock)}", "info")
        return redirect(url_for('portfolio'))
    else:
        flash("Invalid URL!", "danger")
        return redirect(url_for('homepage'))

@app.route("/buy", methods=["POST"])
@must_be_logged_in
def buyStock():
    if request.method == "POST":
        data = request.form
        symbol = data.get("stock")
        shares = data.get("shares")
        if shares is not None:
            shares = int(shares)
        purchase_price = quote(symbol)
        insert_stock(symbol, shares, purchase_price)
        return redirect(url_for('portfolio'))
    else:
        flash("Invalid URL!", "danger")
        return redirect(url_for('homepage'))

@app.route("/sell", methods=["POST"])
@must_be_logged_in
def sellStock():
    data = request.json
    if data is None:
        data = {}
    symbol = data["symbol"]
    time = data["time"]
    stockdata = query_db(g.conn, "select * from stocks where (user_id, symbol, purchase_time) = (?, ?, ?)",
                         [session['user_id'], symbol, time])
    if stockdata is not None:
        stock = stockdata[0]
        price = quote(stock["symbol"]) - stock['purchase_price']
        g.conn.execute("update user set profit = ? where user_id = ?",
                       [g.user['profit'] + price, g.user['user_id']])
        g.conn.commit()
        if stock['shares']-1 > 0:
            g.conn.execute("update stocks set shares = ? where (user_id, symbol, purchase_time) = (?, ?, ?)",
                           [max(stock['shares']-1, 0), session['user_id'], symbol, time])
            g.conn.commit()
        else:
            g.conn.execute("delete from stocks where (user_id, symbol, purchase_time) = (?, ?, ?)",
                           [session['user_id'], symbol, time])
            g.conn.commit()
    return jsonify({})

@app.route("/leaderboard")
def leaderboard():
    scores = []
    data = query_db(g.conn, "select * from user")
    if data is not None:
        for user in data:
            scores.append({'user' : user['username'],
                           'profit' : round(user['profit'], 2)})
    scores.sort(key=lambda x : x['profit'])
    scores = scores[:50]
    return render_template("leaderboard.html", scores=scores)

if __name__ == "__main__":
    try:
        if Config.PROD:
            http_server = WSGIServer((Config.HOST, Config.PORT), app)
            http_server.serve_forever()
        else:
            app.run(host=Config.HOST, port=Config.PORT, debug=True)
    except KeyboardInterrupt:
        exit(0)
