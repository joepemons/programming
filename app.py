from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
from config import CONFIG
from create_db_bikes import BikesDB
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from api import api

app = Flask(__name__)
app.secret_key = 'bikes123'
app.register_blueprint(api)

def get_db_connection():
    conn = sqlite3.connect(CONFIG["database"]["name"])
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('You need to login first.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def homepage():
    return render_template("homepage.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/login/", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    
    username = request.form["username"]
    password = request.form["password"]

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        return redirect(url_for('overview'))
    else:
        flash('Invalid username or password')
        return redirect(url_for('login'))

@app.route('/overview')
@login_required
def overview():
    return render_template('overview.html')

@app.route('/bikes')
@login_required
def bikes():
    conn = get_db_connection()
    all_bikes = conn.execute('SELECT Brand, model, type, price, status, image_url FROM bikes').fetchall()
    conn.close()
    return render_template("bikes.html", bikes=all_bikes)

@app.route('/rent', methods=["GET"])
@login_required
def rent():
    bike_id = request.args.get('bike_id', 0)
    bike_name = request.args.get('bike_name', '')
    bike_model = request.args.get('bike_model', '')
    bike_price = request.args.get('bike_price', 0)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if not all([bike_id, bike_name, bike_model, bike_price]):
        flash('Invalid bike selection')
        return redirect(url_for('bikes'))
        
    return render_template("rent.html", 
                         bike_id=bike_id, 
                         bike_name=bike_name, 
                         bike_model=bike_model, 
                         bike_price=bike_price,
                         today=today)

@app.route('/payment', methods=['GET', 'POST'])
@login_required
def payment():
    if request.method == 'GET':
        bike_id = request.args.get('bike_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not all([bike_id, start_date, end_date]):
            flash('Missing rental information')
            return redirect(url_for('bikes'))
        
        try:
            conn = get_db_connection()
            bike = conn.execute('SELECT price FROM bikes WHERE id = ?', (bike_id,)).fetchone()
            
            if not bike:
                flash('Bike not found')
                return redirect(url_for('bikes'))
            
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            days = (end - start).days + 1
            total_amount = days * bike['price']
            
            session['rental_info'] = {
                'bike_id': bike_id,
                'start_date': start_date,
                'end_date': end_date,
                'total_amount': total_amount
            }
            
            return render_template('payment.html', total_amount=total_amount)
            
        except Exception as e:
            print(f"Error in GET payment: {str(e)}")  # Debug log
            flash('Error processing rental')
            return redirect(url_for('bikes'))
        finally:
            if 'conn' in locals():
                conn.close()
            
    elif request.method == 'POST':
        print("Processing POST payment")  # Debug log
        if 'rental_info' not in session:
            flash('No rental information found')
            return redirect(url_for('bikes'))
        
        rental_info = session.get('rental_info')
        print(f"Rental info: {rental_info}")  # Debug log
        
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Start transaction
            cursor.execute('BEGIN TRANSACTION')
            print("Started transaction")  # Debug log
            
            # Create the reservation
            cursor.execute('''
                INSERT INTO reservations 
                (bike_id, user_id, start_date, end_date, total_cost, status) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                rental_info['bike_id'],
                session['user_id'],
                rental_info['start_date'],
                rental_info['end_date'],
                rental_info['total_amount'],
                'confirmed'
            ))
            
            reservation_id = cursor.lastrowid
            print(f"Created reservation {reservation_id}")  # Debug log
            
            # Record the payment
            cursor.execute('''
                INSERT INTO payments 
                (reservation_id, amount, payment_status, payment_method) 
                VALUES (?, ?, ?, ?)
            ''', (
                reservation_id,
                rental_info['total_amount'],
                'completed',
                'credit_card'
            ))
            print("Recorded payment")  # Debug log
            
            # Update bike status
            cursor.execute('''
                UPDATE bikes 
                SET status = 'Rented'
                WHERE id = ?
            ''', (rental_info['bike_id'],))
            print("Updated bike status")  # Debug log
            
            # Commit transaction
            conn.commit()
            print("Committed transaction")  # Debug log
            
            # Clear the rental info from session
            session.pop('rental_info', None)
            
            print("Redirecting to thank you page")  # Debug log
            return redirect(url_for('thank_you'))
            
        except Exception as e:
            print(f"Error in POST payment: {str(e)}")  # Debug log
            if conn:
                conn.rollback()
                print("Rolled back transaction")  # Debug log
            flash(f'Error processing payment: {str(e)}')
            return redirect(url_for('bikes'))
        finally:
            if conn:
                conn.close()

@app.route('/thank_you')
@login_required
def thank_you():
    try:
        conn = get_db_connection()
        # Get the most recent reservation for this user
        reservation = conn.execute('''
            SELECT r.*, b.Brand, b.model, p.payment_status
            FROM reservations r
            JOIN bikes b ON r.bike_id = b.id
            LEFT JOIN payments p ON p.reservation_id = r.id
            WHERE r.user_id = ?
            ORDER BY r.id DESC
            LIMIT 1
        ''', (session['user_id'],)).fetchone()
        
        return render_template('thank_you.html', reservation=reservation)
    except Exception as e:
        print(f"Error in thank you page: {str(e)}")  # Debug log
        flash('Error loading reservation details')
        return redirect(url_for('overview'))
    finally:
        if 'conn' in locals():
            conn.close()
            
@app.route("/logout/")
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully!')
    return redirect(url_for('homepage'))

if __name__ == "__main__":
    app.run(host=CONFIG["frontend"]["listen_ip"], 
            port=CONFIG["frontend"]["port"], 
            debug=CONFIG["frontend"]["debug"])