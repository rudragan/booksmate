import os
import json
from functools import wraps

from flask import Flask, session, render_template, request, logging, url_for, redirect, flash
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import requests

from passlib.hash import sha256_crypt

app = Flask(__name__)



# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine("postgresql://postgres:chemistry12@localhost/booksmate1")
db = scoped_session(sessionmaker(bind=engine))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("username") is None:
            return render_template('login.html',message='You need to login first.')
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    return render_template('login.html')

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        password = request.form.get('password')
        username = request.form.get('username')
        confirm = request.form.get('confirm')
        #secure_password = sha256_crypt.encrypt(str(password))

        if name == '' or password == '' or username == '' or confirm == '':
            return render_template('register.html', message='Please enter required fields.')

        if not password == confirm:
            return render_template('register.html', message='Passwords do not match.')

        userrow = db.execute("SELECT * FROM users WHERE username = :username", {"username": username})
        user_exists = userrow.first()
        if not user_exists:
            db.execute("INSERT INTO users(name,username,password) VALUES(:name, :username, :password)",{"name":name,"username":username,"password":password})
            db.commit()
            return render_template('register.html', text = 'You are now registered.')

        else:
            return render_template("register.html", message="That username is taken.")

    return render_template('register.html')

@app.route('/login',methods=['POST','GET'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        #print(name, password)

        if username == '' or password == '':
            return render_template('login.html', message='Please enter required fields.')
        
        
        
        usernamedata = db.execute("SELECT username FROM users WHERE username=:username ",{"username":username}).fetchone()
        passworddata = db.execute("SELECT password FROM users WHERE username=:username ",{"username":username}).fetchone()

        if usernamedata is None:
            return render_template('login.html',message= 'User does not exist.')
        else:
            for passwor_data in passworddata:
                if password == passwor_data:
                    session['username']= username
                    return render_template('front.html',name=username)
                else:
                    return render_template('login.html',message= 'Incorrect Password.')


@app.route('/front',methods=['GET','POST'])
@login_required
def front():
    username=session.get('username')
    return render_template('front.html',name=username)

@app.route('/search',methods=['GET','POST'])
@login_required
def search():
    username=session.get('username')
    if request.method == 'POST':
        result = request.form.get('result')
        
        

        if result=='':
            return render_template('front.html',message="You did not search for anything.",name=username)

        
    query = "%" + request.form.get("result") + "%"

    
    query = query.title()
    
    rows = db.execute("SELECT isbn, title, author, year FROM books WHERE \
                        isbn LIKE :query OR \
                        title LIKE :query OR \
                        author LIKE :query OR \
                        year LIKE :query LIMIT 30",
                        {"query": query})
    
    
    if rows.rowcount == 0:
        return render_template("front.html",name=username, message="We can't find anything with that description.")
    
    
    books = rows.fetchall()

    return render_template("search.html",result=result, books=books)


@app.route('/book/<isbn>',methods=['GET','POST'])
@login_required
def book(isbn):
    username=session.get('username') 
    session["reviews"]=[]
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "Cdjuz7jTYIwy5Jj9GhY9sw", "isbns": isbn})
    average_rating=res.json()['books'][0]['average_rating']
    work_ratings_count=res.json()['books'][0]['work_ratings_count']
    reviews=db.execute("SELECT * FROM reviews WHERE isbn = :isbn",{"isbn":isbn}).fetchall() 
    secondreview=db.execute("SELECT * FROM reviews WHERE isbn = :isbn AND username= :username",{"username":username,"isbn":isbn}).fetchone()
    for y in reviews:
        session['reviews'].append(y)  
    data=db.execute("SELECT * FROM books WHERE isbn = :isbn",{"isbn":isbn}).fetchone()
    
    if request.method=="POST" and secondreview==None:
        review=request.form.get('review') 
        rating=request.form.get('rating')
        db.execute("INSERT INTO reviews (isbn, review, rating, username) VALUES (:a,:b,:c,:d)",{"a":isbn,"b":review,"c":rating,"d":username})
        db.commit()
        return redirect(url_for('book',isbn=data.isbn))
    if request.method=="POST" and secondreview!=None:
        return render_template("book.html",message="You have already reviewed this book.",data=data,reviews=session['reviews'],average_rating=average_rating,work_ratings_count=work_ratings_count,username=username)
    
    return render_template("book.html",data=data,reviews=session['reviews'],average_rating=average_rating,work_ratings_count=work_ratings_count,username=username)
    
   
        
@app.route("/api/<string:isbn>")
@login_required
def api(isbn):
    data=db.execute("SELECT * FROM books WHERE isbn = :isbn",{"isbn":isbn}).fetchone()
    if data==None:
        return render_template('404.html')
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "Cdjuz7jTYIwy5Jj9GhY9sw", "isbns": isbn})
    average_rating=res.json()['books'][0]['average_rating']
    work_ratings_count=res.json()['books'][0]['work_ratings_count']
    x = {
    "title": data.title,
    "author": data.author,
    "year": data.year,
    "isbn": isbn,
    "review_count": work_ratings_count,
    "average_score": average_rating
    }
    api=json.dumps(x)
    return render_template("api.json",api=api)

      


@app.route('/logout')
@login_required
def logout():
    session.clear()
    return render_template('logout.html') 




if __name__ == 'main':
    app.run(debug=True)