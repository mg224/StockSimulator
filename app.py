import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
import datetime
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Get stocks and shares
    transactions = db.execute("SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id = :user_id GROUP BY symbol HAVING total_shares > 0", user_id = session["user_id"])

    # Get cash balance
    cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = session["user_id"])[0]["cash"]

    # Initialize variables
    total_value = cash
    final_total = cash

    # Display HTML table with:
        # All stocks owned
        # Number of shares of each stock
        # Current price of each stock
        # Total value of each holding
    # Display user's current cash balance
    # Display total value of stocks and cash together
    # Use loop to display for each stock in portfolio
    for transaction in transactions:
        quote = lookup(transaction["symbol"])
        transaction["price"] = quote["price"]
        transaction["value"] = transaction["price"] * transaction["total_shares"]
        total_value += transaction["value"]
        final_total += transaction["value"]

    return render_template("index.html", transactions=transactions, cash=cash, total_value=total_value, final_total=final_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Purchase the stock as long as the user can afford it & stock symbol is valid
        # Get symbol and shares
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")

        # Check validity of input for symbol and shares
        if not symbol:
            return apology("must provide symbol")
        elif not shares or not shares.isdigit() or int(shares) <= 0:
            return apology("must provide positive integer number of shares")

        # Lookup symbol
        quote = lookup(symbol)
        if quote is None:
            return apology("symbol not found")

        # Get price, calculate total cost, and find cash from database
        price = float(quote["price"])
        total_cost = float(shares) * price
        cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = session["user_id"])[0]["cash"]

        # If user can't afford purchase, display apology
        if cash < total_cost:
            return apology("insufficient funds to complete purchase")

        # If they can afford it, run SQL statement on database to update cash
        db.execute("UPDATE users SET cash = (cash - :total_cost) WHERE id = :user_id", total_cost = total_cost, user_id = session["user_id"])

        # Record current timestamp
        timestamp = datetime.datetime.now()

        # Add purchase to history table
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, timestamp) VALUES (:user_id, :symbol, :shares, :price, :timestamp)", user_id = session["user_id"], symbol = symbol, shares = shares, price = price, timestamp = timestamp)

        # Display purchase
        flash(f"Successfully purchased {shares} shares of {symbol} for {usd(total_cost)}")

        # Redirect to home page
        return redirect("/")

    # User reached route via GET
    else:
        # Display form to buy a stock
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Display a table with history of all transactions, listing one row for every buy and sell
    transactions = db.execute("SELECT symbol, shares, price, timestamp FROM transactions WHERE user_id = :user_id ORDER BY timestamp DESC", user_id = session["user_id"])
    for i in range(len(transactions)):
        transactions[i]["price"] = usd(transactions[i]["price"])
    return render_template("history.html", transactions = transactions)

@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    """Allow user to add cash to their account"""
    if request.method == "POST":

        # Check for additional cash amount requested
        new_cash = request.form.get("new_cash")

        # Error checking for input
        if not new_cash:
            return apology("invalid input")

        # Find user's current cash
        current_cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = session["user_id"])[0]["cash"]

        # Add the new_cash to the user's current cash
        updated_cash = float(current_cash) + float(new_cash)

        # Update users table
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updated_cash, session["user_id"])

        # Redirect to home page
        return redirect("/")

    else:
        return render_template("add_cash.html")


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
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
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
        # Lookup stock symbol by calling lookup function
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("must input symbol")

        quote = lookup(symbol.upper())

        # If lookup is successful, display results. If unsuccessful, display apology
        if not quote:
            return apology("invalid symbol", 400)

        return render_template("quote.html", quote=quote)
    # User reached route via GET
    else:
        # Display form to request a stock quote
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Clear session
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Check for possible errors
        # If any field left blank, return aplogy
        if not request.form.get("username"):
            return apology("must provide username", 400)

        elif not request.form.get("password"):
            return apology("must provide password", 400)

        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)

        # If password and confirmation don't match, return apology
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        try:
            # Database should never store plain text password, use generate_password_hash to generate a hash of the password
            new_user = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")))
        except:
            return apology("username already exists")

        # Log user in, session["user_id"] keeps track of user
        session["user_id"] = new_user

        # Redirect user to homepage
        return redirect("/")

    # User reached route via GET
    else:
        # Display registration form
        # (Create new template for registration, user should be prompted with username, password, confirmation)
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get symbol and shares
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Error checking for symbol and shares input
        if not request.form.get("symbol"):
            return apology("must provide symbol")

        elif not request.form.get("shares"):
            return apology("must provide shares")

        elif int(request.form.get("shares")) < 0:
            return apology("must provide a valid number of shares")

        if not request.form.get("symbol"):
            return apology("must provide an existing symbol")

        # Lookup symbol
        symbol = request.form.get("symbol").upper()
        stock = lookup(symbol)

        rows = db.execute("SELECT symbol, SUM(shares) FROM transactions WHERE user_id = :user_id GROUP BY symbol HAVING SUM(shares) > 0", user_id = session["user_id"])

        # Calculate sale
        shares = int(request.form.get("shares"))
        for row in rows:
            if row["symbol"] == symbol:
                if shares > row["SUM(shares)"]:
                    return apology("insufficient shares to complete sale")
        total_sale = shares * stock['price']

        # Get user cash and add the sale to it
        user_cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        cash = user_cash[0]["cash"]
        # Add user_cash by value of transaction
        updated_cash = cash + total_sale

        # Update cash in users table
        db.execute("UPDATE users SET cash = :updated_cash WHERE id = :user_id", updated_cash = updated_cash, user_id=session["user_id"])

        # Update transactions table
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (:user_id, :symbol, :shares, :price)", user_id = session["user_id"], symbol = stock["symbol"], shares = ((-1) * shares), price = stock["price"])

        # Flash confirmation of sale
        flash(f"Successfully sold {shares} shares of {symbol} for {usd(total_sale)}")

        # Redirect to homepage
        return redirect("/")

    # User reached route via GET
    else:
        # Display form to sell a stock
        rows = db.execute("SELECT symbol FROM transactions WHERE user_id =:user_id GROUP BY symbol HAVING SUM(shares) > 0", user_id = session["user_id"])
        return render_template("sell.html", symbols = [row["symbol"] for row in rows])
