import os
import functools

from flask import Flask, flash, g, redirect, render_template, session, url_for, request
from werkzeug.security import generate_password_hash, check_password_hash

from database import connect_to_db, query_db
from stocks import quote

app = Flask(__name__)

class Config:
    DATABASE_NAME ="database.db"
    SECRET_KEY = os.urandom(12).hex()

app.config['SECRET_KEY'] = Config.SECRET_KEY

# utilities
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
    g.conn.execute("insert into user (username, password_hash) values (?, ?)",
                   [username, password])

@db_write
def insert_stock(symbol, shares, purchase_price):
    g.conn.execute("insert into stocks (user_id, symbol, shares, purchase_price) values (?, ?, ?, ?)",
                   [session['user_id'], symbol, shares, purchase_price])
# requests
@app.before_request
def before_request():
    # create database connection before every request
    g.conn = connect_to_db(Config.DATABASE_NAME)
    if 'user_id' in session:
        g.user = query_db(g.conn, 'select * from user where user_id = ?', [session['user_id']])[0]
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
            return redirect(url_for('homepage'))
        else:
            userdata = userdata[0]
            if check_password_hash(userdata['password_hash'], data.get("password")):
                user_id = userdata['user_id']
                g.conn.commit()
                session['user_id'] = user_id
                flash("Logged in", "success")
            else:
                flash("Password is incorrect!", "danger")
                return redirect(url_for('homepage'))

        return redirect(url_for('homepage'))

@app.route('/signup', methods=['GET', 'POST'])
def signuppage():
    if request.method == "GET":
        return render_template("signup.html")
    else:
        data = request.form
        username = data.get("username")
        password_hash = generate_password_hash(str(data.get("password")), "sha256")
        insert_user(username, password_hash)
        flash("User has been created!", "success")
        return redirect(url_for('homepage'))

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
    profit = 0
    stockdata = query_db(g.conn, "select * from stocks where user_id = ?", [session['user_id']])
    if stockdata is not None:
        for stock in stockdata:
            s = {'symbol' : stock['symbol'], 'shares' : stock['shares'],
                           'purchase_price' : round(stock['shares'] * stock['purchase_price'], 2),
                           'price' : round(stock['shares'] * quote(stock['symbol']), 2)}
            delta = round(s['price'] - s['purchase_price'], 2)
            s['delta'] = delta
            profit += delta
            profit = round(profit, 2)
            stocks.append(s)
    return render_template("portfolio.html", stocks=stocks, profit=profit)

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
        shares = int(data.get("shares"))
        stockdata = query_db(g.conn, "select * from stocks where (user_id, symbol) = (?, ?)",
                             [session['user_id'], symbol])
        if stockdata is None:
            purchase_price = quote(symbol)
            insert_stock(symbol, shares, purchase_price)
        return redirect(url_for('portfolio'))
    else:
        flash("Invalid URL!", "danger")
        return redirect(url_for('homepage'))

@app.route("/sell", methods=["POST"])
@must_be_logged_in
def sellStock():
    if request.method == "POST":
        data = request.form
        symbol = data.get("stock")
        shares = int(data.get("shares"))
        stockdata = query_db(g.conn, "select * from stocks where (user_id, symbol) = (?, ?)",
                             [session['user_id'], symbol])
        if stockdata is not None:
            if stockdata[0]['shares']-shares > 0:
                g.conn.execute("update stocks set shares = ? where (user_id, symbol) = (?, ?)",
                               [max(stockdata[0]['shares']-shares, 0), session['user_id'], symbol])
                g.conn.commit()
            else:
                g.conn.execute("delete from stocks where (user_id, symbol) = (?, ?)",
                               [session['user_id'], symbol])
                g.conn.commit()
        return redirect(url_for('portfolio'))
    else:
        flash("Invalid URL!", "danger")
        return redirect(url_for('homepage'))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3000, debug=True)
