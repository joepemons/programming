import sqlite3
import sys

from config import CONFIG

class BikesDB:
    @staticmethod
    def initialize(database_connection: sqlite3.Connection):
        cursor = database_connection.cursor()
        try:
            print("Dropping existing tables(if present)...")
            cursor.execute("DROP TABLE IF EXISTS users")
            cursor.execute("DROP TABLE IF EXISTS bikes")
            cursor.execute("DROP TABLE IF EXISTS reservations")
            cursor.execute("DROP TABLE IF EXISTS payments")
        except sqlite3.OperationalError as db_error:
            print(f"unable to drop table. Error: {db_error}")
        print("Creating tables...")
        cursor.execute(BikesDB.CREATE_TABLE_USERS)
        cursor.execute(BikesDB.CREATE_TABLE_BIKES)
        cursor.execute(BikesDB.CREATE_TABLE_RESERVATIONS)
        cursor.execute(BikesDB.CREATE_TABLE_PAYMENTS)
        database_connection.commit()

        print("Populating database with sample data...")
        cursor.executemany(BikesDB.INSERT_Bikes, BikesDB.sample_Bikes)
        database_connection.commit()
    
    
    CREATE_TABLE_USERS = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )"""

    CREATE_TABLE_BIKES = """
    CREATE TABLE IF NOT EXISTS bikes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        Brand TEXT NOT NULL,
        model TEXT NOT NULL,
        type TEXT NOT NULL,
        price REAL NOT NULL,
        status TEXT NOT NULL,
        image_url TEXT DEFAULT 'https://via.placeholder.com/150'
    )"""

    CREATE_TABLE_RESERVATIONS = """
    CREATE TABLE IF NOT EXISTS reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bike_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        total_cost REAL NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bike_id) REFERENCES bikes (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )"""

    CREATE_TABLE_PAYMENTS = """
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reservation_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        payment_status TEXT NOT NULL,
        payment_method TEXT NOT NULL,
        FOREIGN KEY (reservation_id) REFERENCES reservations (id)
    )"""

    INSERT_Bikes = 'INSERT INTO bikes (Brand, model, type, price, status, image_url) VALUES (?, ?, ?, ?, ?, ?)'

    sample_Bikes = [
        ('Harley-Davidson', 'Iron 883', 'Cruiser', 89.99, 'Available', '/static/images/download.jpg'),
        ('Ducati', 'Panigale V4', 'Sport Bike', 149.99, 'Rented', '/static/images/v4.jpg'),
        ('Yamaha', 'MT-09', 'Naked Bike', 74.99, 'Available', '/static/images/download (1).jpg'),
        ('Honda', 'CBR600RR', 'Sport Bike', 99.99, 'Available', '/static/images/download (2).jpg'),
        ('BMW', 'R 1250 GS', 'Adventure Bike', 129.99, 'Maintenance', '/static/images/download (3).jpg'),
        ('Triumph', 'Street Triple R', 'Naked Bike', 84.99, 'Available', '/static/images/download (4).jpg'),
        ('Indian', 'Scout Bobber', 'Cruiser', 94.99, 'Rented', '/static/images/download (5).jpg'),
        ('Kawasaki', 'Ninja ZX-10R', 'Sport Bike', 109.99, 'Available', '/static/images/download (6).jpg'),
        ('Suzuki', 'SV650', 'Naked Bike', 64.99, 'Available', '/static/images/download (7).jpg'),
        ('Honda', 'Africa Twin', 'Adventure Bike', 119.99, 'Maintenance', '/static/images/download (8).jpg')
    ]

def main():
    db_conn = sqlite3.connect(CONFIG["database"]["name"])
    db_conn.row_factory = sqlite3.Row

    BikesDB.initialize(db_conn)
    db_conn.close()

    print("Database created successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main())