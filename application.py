import os
import requests

from flask import Flask, session, jsonify, render_template, request, redirect, flash, url_for
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import default_exceptions
from helpers import login_required

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/")
def index():
 # session["user_id"]= None
    return render_template("index.html")

@app.route("/outcomes",methods=["GET", "POST"])
def outcomes():
    # select books user search for
    keyword =  request.form.get("keyword")
    results = db.execute("SELECT * FROM books WHERE title LIKE :k OR isbn LIKE :k OR author LIKE :k OR year LIKE :k",
                       {"k":keyword}).fetchall()
    db.commit()
    return render_template("outcomes.html", results=results)


@app.route("/outcomes/<title>", methods=["GET","POST"])
def outcome(title):
    # remember this book, so that when user return from login page, he can still in this book page
    session["thebook"] = title
    result = db.execute ("SELECT * FROM books WHERE title = :k",
                   {"k":title}).fetchone()

    if request.method == "POST":

        if session["user_id"] == None:
            return redirect("/login")
        else:
            new_review = request.form.get("myreview")
            book = session["thebook"]
            user_id = session["user_id"]
            rate = request.form.get("rate")

            # Check if this user add review for the book twice
            check = db.execute("SELECT * FROM review WHERE user_id=:u AND book_title=:b",
                              {"u":user_id, "b":book}).fetchall()
            
            if check != []:
                message = "You can only rate the same book once"
                return render_template("apology.html",message=message)

            # Add new review into database
            add = db.execute("INSERT INTO review(user_id, book_title, reviews, rate, time) VALUES(:i, :b, :r, :rate, CURRENT_TIMESTAMP)",
                            {"i":user_id, "b":title, "r":new_review, "rate":rate})
            db.commit()
            reviews = []
            reviews = db.execute("SELECT * FROM review WHERE book_title = :t",
                                {"t":title}).fetchall()
            average_score_0 = db.execute("SELECT AVG(rate) FROM review WHERE book_title=:b",
                                      {"b":title}).fetchone()

            if average_score_0 is None:
                average_score ="There is no rate yet"
            else:
                average_score = float(average_score_0[0])

            return render_template("outcome.html", reviews=reviews,result=result, average_score=average_score)
    else:
            # select reviews of a certain book
            reviews = []
            reviews = db.execute("SELECT reviews FROM review WHERE book_title = :t",
                                {"t":title}).fetchall()
            average_score_0 = db.execute("SELECT AVG(rate) FROM review WHERE book_title=:b",
                                      {"b":title}).fetchone()
            if average_score_0[0] is None:
                average_score ="There is no rate yet"
            else:
                average_score = float(average_score_0[0])
            return render_template("outcome.html", reviews=reviews,result=result, average_score=average_score)


@app.route("/register", methods=["GET","POST"])
def register():
    """Register user"""

    # input username
    if request.method == "POST":
        username = request.form.get("username")

        # check whether username has been existed
        exist = db.execute("SELECT username FROM users WHERE username=:username",
                            {"username":username}).fetchall()
        if exist != []:
            message ="Sorry, this username already exist. Please use another username."
            return render_template("apology.html", message=message)

        else:
            # hash password
            pass_word = request.form.get("password")
            hash_pass = generate_password_hash(pass_word)

            #add user into database
            add_user = db.execute("INSERT INTO users(username, password) VALUES(:username, :hashed_password)",
                           {"username": username, "hashed_password": hash_pass})
            db.commit()

            if not add_user:
                message = "Something wrong with register"
                return render_template("apology.html",message=message)

            #Redirect user to homepage
            return redirect("/")

    # Users reached route via GET
    else:
        return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """log user in """
    session["user_id"]= None

    # Query database for username
    if request.method == "POST":
        username = request.form.get("username")
        userinfo = db.execute("SELECT * FROM users WHERE username = :username",
                                {"username": username}).fetchone()

        # check whether user exist
        if userinfo == []:
            message = "This username already exist. Please try another username."
            return render_template("apology.html",message=message)

        # check whether password is right
        elif check_password_hash(userinfo.password, request.form.get("password")) == False:
            message ="Password and username do not match"
            return render_template("apology.html",message=message)

        # User is correctly login, comeback to former page
        else:
            # Remember login information
            session["user_id"] = userinfo.id
            if session["thebook"] == []:
                return redirect("/")
            else:
                title = session["thebook"]
                reviews = []
                reviews = db.execute("SELECT reviews FROM review WHERE book_title = :t",
                                    {"t":title}).fetchall()
                result = db.execute ("SELECT * FROM books WHERE title = :k",
                                   {"k":title}).fetchone()
                average_score_0 = db.execute("SELECT AVG(rate) FROM review WHERE book_title=:b",
                                          {"b":title}).fetchone()

                if average_score_0[0] is None:
                    average_score ="There is no rate yet"
                else:
                    average_score = float(average_score_0[0])

                return render_template("outcome.html", reviews=reviews,result=result, average_score=average_score)
      # User reached route via GET
    else:
        return render_template("login.html")


@app.route("/api/outcomes/<isbn>")
def book_api(isbn):
    """Return details about a single book."""

    book = db.execute("SELECT * FROM books WHERE isbn=:i",
                     {"i":isbn}).fetchone()
    if book is None:
        return jsonify({"error":"Invalid isbn"}),422

    title = book.title
    review_count_0 = db.execute("SELECT COUNT(reviews) FROM review WHERE book_title=:b",
                             {"b":title}).fetchone()
    review_count =review_count_0[0]
    average_score_0 = db.execute("SELECT AVG(rate) FROM review WHERE book_title=:b",
                              {"b":title}).fetchone()

    if average_score_0[0] is None:
        average_score ="There is no rate yet"
    else:
        average_score = float(average_score_0[0])

    return jsonify({
    "title": book.title,
    "author": book.author,
    "year": book.year,
    "isbn": isbn,
    "review_count": review_count,
    "average_score": average_score
    })


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
