import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Query DB to find out how much cash the user currently has
    user = session.get("user_id")
    rows = db.execute("SELECT cash FROM users WHERE id = ?", user)
    cash = rows[0]["cash"]

    rows = db.execute("SELECT symbol, shares FROM stocks WHERE user_id = ? ORDER BY symbol ASC", user)
    total = cash
    for row in rows:
        print("From GB : " + str(row))
        data = lookup(row["symbol"])
        print("FROM GB : " + str(data))
        row["name"] = data["name"]
        row["price"] = data["price"]
        row["total"] = row["price"] * row["shares"]
        total += row["total"]
        print()

    return render_template("portfolio.html", cash_balance = cash, stocks = rows, grand_total = total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("missing symbol")
        symbol = request.form.get("symbol").upper()

        # Ensure shares was submitted
        if not request.form.get("shares"):
            return apology("missing shares")
        shares = int(request.form.get("shares"))

        # Ensure shares is a positive integer
        if shares < 1:
            return apology("non positive number of shares")

        # Lookup the symbol
        lookup_data = lookup(symbol)
        
        # Return apology if the symbol is invalid
        if not lookup_data:
            return apology("invalid symbol")
        price = lookup_data["price"]
        
        # Query DB to find out how much cash the user currently has
        user = session.get("user_id")
        rows = db.execute("SELECT cash FROM users WHERE id = ?", user)
        cost = shares * price

        # Check if the cash is sufficient
        if cost > rows[0]["cash"]:
            return apology("insufficient cash")

        '''All OK'''

        # Record transaction
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, transacted) VALUES (?, ?, ?, ?, datetime('now'))", user, symbol, shares, price)

        # Add shares to stocks
        rows = db.execute("SELECT id FROM stocks WHERE user_id = ? AND symbol = ?", user, symbol)
        if len(rows) == 0:
            db.execute("UPDATE stocks SET shares = shares + ? WHERE ID = ?", shares, rows[0]["id"])
        else:
            db.execute("INSERT INTO stocks (user_id, symbol, shares) VALUES (?, ?, ?)", user, symbol, shares)

        # Deduct cash from users
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", cost, user)

        # Display the results
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    
    # Query DB for transaction history of current user
    rows = db.execute("SELECT * FROM transactions WHERE user_id = ?", session.get("user_id"))

    return render_template("history.html", transactions = rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("missing symbol")

        # Lookup the symbol
        lookup_data = lookup(request.form.get("symbol"))
        
        # Return apology if the symbol is invalid
        if not lookup_data:
            return apology("invalid symbol")
        
        # Display the results
        return render_template("quoted.html", data = lookup_data)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("missing username")

        form_username = request.form.get("username")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", form_username)

        # Ensure username is not already taken
        if len(rows) != 0:
            return apology("username is already taken")

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("missing password")
        
        # Ensure confirmation was submitted
        if not request.form.get("confirmation"):
            return apology("missing confirmation password")
        
        form_password = request.form.get("password")
        form_confirm = request.form.get("confirmation")
        
        # Match passwords for confirmation
        if form_password != form_confirm:
            return apology("passwords don't match")

        # Insert user into database & Remember which user has logged in
        session["user_id"] = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", form_username, generate_password_hash(form_password))

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user = session.get("user_id")

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("missing symbol")
        symbol = request.form.get("symbol").upper()

        # Ensure shares was submitted
        if not request.form.get("shares"):
            return apology("missing shares")
        shares = int(request.form.get("shares"))

        # Ensure shares is a positive integer
        if shares < 1:
            return apology("non positive number of shares")

        # Lookup the symbol
        lookup_data = lookup(symbol)
        
        # Return apology if the symbol is invalid
        if not lookup_data:
            return apology("invalid symbol")
        price = lookup_data["price"]
        
        # Check if user has any shares of symbol
        rows = db.execute("SELECT * FROM stocks WHERE user_id = ? AND symbol = ?", user, symbol)
        if len(rows) == 0:
            return apology(f"you don't have any shares of {symbol}")
        
        # Ensure user has sufficient number of shares
        if shares > rows[0]["shares"]:
            return apology("too many shares")

        '''All OK'''
        
        # Record transaction
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, transacted) VALUES (?, ?, ?, ?, datetime('now'))", user, symbol, (-1) * shares, price)

        # Deduct shares from stocks
        if shares == rows[0]["shares"]:
            db.execute("DELETE FROM stocks WHERE id = ?", rows[0]["id"])
        else:
            db.execute("UPDATE stocks SET shares = shares - ? WHERE ID = ?", shares, rows[0]["id"])

        # Add cash to users
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", (shares * price), user)

        # Display the results
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        # Query DB to find the user's stocks info
        rows = db.execute("SELECT * FROM stocks WHERE user_id = ? ORDER BY symbol ASC", user)
        return render_template("sell.html", stocks = rows)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
