from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
from datetime import datetime

api = Blueprint('api', __name__)

def get_db_connection():
    conn = sqlite3.connect('bikes.db')
    conn.row_factory = sqlite3.Row
    return conn

@api.route('/api/bikes', methods=['GET'])
def get_bikes():
    try:
        conn = get_db_connection()
        bikes = conn.execute('SELECT * FROM bikes').fetchall()
        conn.close()
        return jsonify([dict(bike) for bike in bikes])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/api/bikes/<int:bike_id>', methods=['GET'])
def get_bike(bike_id):
    try:
        conn = get_db_connection()
        bike = conn.execute('SELECT * FROM bikes WHERE id = ?', (bike_id,)).fetchone()
        conn.close()
        if bike is None:
            return jsonify({'error': 'Bike not found'}), 404
        return jsonify(dict(bike))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/api/reservations', methods=['POST'])
def create_reservation():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401
        
    data = request.get_json()
    required_fields = ['bike_id', 'start_date', 'end_date']
    
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if bike exists and is available
        bike = cursor.execute('''
            SELECT id, price, status 
            FROM bikes 
            WHERE id = ? AND status = 'Available'
        ''', (data['bike_id'],)).fetchone()
        
        if not bike:
            return jsonify({'error': 'Bike not found or not available'}), 404
            
        # Check if dates are valid
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')
        
        if start_date >= end_date:
            return jsonify({'error': 'Invalid date range'}), 400
            
        # Check if bike is already reserved for these dates
        existing_reservation = cursor.execute('''
            SELECT id FROM reservations 
            WHERE bike_id = ? AND 
            ((start_date BETWEEN ? AND ?) OR 
             (end_date BETWEEN ? AND ?) OR
             (start_date <= ? AND end_date >= ?))
        ''', (data['bike_id'], data['start_date'], data['end_date'],
              data['start_date'], data['end_date'],
              data['start_date'], data['end_date'])).fetchone()
              
        if existing_reservation:
            return jsonify({'error': 'Bike is already reserved for these dates'}), 400
            
        # Calculate total cost
        days = (end_date - start_date).days + 1
        total_cost = days * bike['price']
        
        # Create reservation
        cursor.execute('''
            INSERT INTO reservations (bike_id, user_id, start_date, end_date, total_cost) 
            VALUES (?, ?, ?, ?, ?)
        ''', (data['bike_id'], session['user_id'], data['start_date'], 
              data['end_date'], total_cost))
        
        # Update bike status
        cursor.execute('''
            UPDATE bikes 
            SET status = 'Rented' 
            WHERE id = ?
        ''', (data['bike_id'],))
        
        conn.commit()
        
        return jsonify({
            'message': 'Reservation created successfully',
            'reservation_id': cursor.lastrowid,
            'total_cost': total_cost
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@api.route('/api/user/register', methods=['POST'])
def register_user():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Missing username or password'}), 400
        
    try:
        conn = get_db_connection()
        password_hash = generate_password_hash(data['password'])
        
        conn.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                    (data['username'], password_hash))
        conn.commit()
        return jsonify({'message': 'User registered successfully'})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username already exists'}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@api.route('/api/user/login', methods=['POST'])
def login_user():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Missing username or password'}), 400
        
    try:
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', 
                          (data['username'],)).fetchone()
        
        if user and check_password_hash(user['password'], data['password']):
            session['user_id'] = user['id']
            return jsonify({
                'message': 'Login successful',
                'user_id': user['id']
            })
        return jsonify({'error': 'Invalid username or password'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@api.route('/api/reservations/<int:user_id>', methods=['GET'])
def get_user_reservations(user_id):
    if 'user_id' not in session or session['user_id'] != user_id:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        conn = get_db_connection()
        reservations = conn.execute('''
            SELECT r.*, b.Brand, b.model 
            FROM reservations r
            JOIN bikes b ON r.bike_id = b.id
            WHERE r.user_id = ?
            ORDER BY r.start_date DESC
        ''', (user_id,)).fetchall()
        return jsonify([dict(reservation) for reservation in reservations])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@api.route('/api/reservations/<int:reservation_id>', methods=['DELETE'])
def cancel_reservation(reservation_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if reservation exists and belongs to user
        reservation = cursor.execute('''
            SELECT bike_id, start_date 
            FROM reservations 
            WHERE id = ? AND user_id = ?
        ''', (reservation_id, session['user_id'])).fetchone()
        
        if not reservation:
            return jsonify({'error': 'Reservation not found'}), 404
            
        # Check if cancellation is allowed (e.g., not on same day)
        start_date = datetime.strptime(reservation['start_date'], '%Y-%m-%d')
        if (start_date - datetime.now()).days < 1:
            return jsonify({'error': 'Cannot cancel reservation on same day'}), 400
            
        # Cancel reservation and update bike status
        cursor.execute('DELETE FROM reservations WHERE id = ?', (reservation_id,))
        cursor.execute('''
            UPDATE bikes 
            SET status = 'Available' 
            WHERE id = ?
        ''', (reservation['bike_id'],))
        
        conn.commit()
        return jsonify({'message': 'Reservation cancelled successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@api.route('/api/reservations/latest', methods=['GET'])
def get_latest_reservation():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        conn = get_db_connection()
        # Get reservation with payment status and bike details
        reservation = conn.execute('''
            SELECT 
                r.*, 
                b.Brand as bike_brand, 
                b.model as bike_model,
                p.payment_status,
                p.payment_method
            FROM reservations r
            JOIN bikes b ON r.bike_id = b.id
            LEFT JOIN payments p ON p.reservation_id = r.id
            WHERE r.user_id = ?
            ORDER BY r.created_at DESC
            LIMIT 1
        ''', (session['user_id'],)).fetchone()
        
        if not reservation:
            return jsonify({'error': 'No reservation found'}), 404
            
        return jsonify(dict(reservation))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@api.route('/api/reservations/<int:reservation_id>/payment', methods=['GET'])
def get_reservation_payment(reservation_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        conn = get_db_connection()
        # Verify reservation belongs to user
        reservation = conn.execute('''
            SELECT user_id 
            FROM reservations 
            WHERE id = ?
        ''', (reservation_id,)).fetchone()
        
        if not reservation or reservation['user_id'] != session['user_id']:
            return jsonify({'error': 'Reservation not found'}), 404
            
        # Get payment details
        payment = conn.execute('''
            SELECT * 
            FROM payments 
            WHERE reservation_id = ?
        ''', (reservation_id,)).fetchone()
        
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
            
        return jsonify(dict(payment))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()