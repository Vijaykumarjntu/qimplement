import os
import json
import sqlite3
from datetime import datetime

# Database file
DB_PATH = "qomplement.db"

def init_database():
    """Create tables if they don't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Invoices table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT,
            vendor_name TEXT,
            invoice_date TEXT,
            total_amount REAL,
            source_file TEXT,
            extracted_at TEXT,
            status TEXT DEFAULT 'processed',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Line items table (one-to-many with invoices)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS line_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER,
            description TEXT,
            quantity REAL,
            unit_price REAL,
            FOREIGN KEY (invoice_id) REFERENCES invoices (id)
        )
    ''')
    
    # Processing logs table (for audit)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processing_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT,
            action TEXT,
            status TEXT,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def insert_invoice(invoice_data):
    """Insert invoice and line items into database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Insert invoice
    cursor.execute('''
        INSERT INTO invoices (invoice_number, vendor_name, invoice_date, total_amount, source_file, extracted_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        invoice_data.get('invoice_number'),
        invoice_data.get('vendor_name'),
        invoice_data.get('invoice_date'),
        invoice_data.get('total_amount'),
        invoice_data.get('source_file'),
        invoice_data.get('extracted_at')
    ))
    
    invoice_id = cursor.lastrowid
    
    # Insert line items
    for item in invoice_data.get('line_items', []):
        cursor.execute('''
            INSERT INTO line_items (invoice_id, description, quantity, unit_price)
            VALUES (?, ?, ?, ?)
        ''', (
            invoice_id,
            item.get('description'),
            item.get('quantity'),
            item.get('unit_price')
        ))
    
    conn.commit()
    conn.close()
    
    print(f"   💾 Inserted invoice ID {invoice_id} with {len(invoice_data.get('line_items', []))} line items")
    return invoice_id

def log_processing(source_file, action, status, error_message=None):
    """Log processing events for audit"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO processing_logs (source_file, action, status, error_message)
        VALUES (?, ?, ?, ?)
    ''', (source_file, action, status, error_message))
    
    conn.commit()
    conn.close()

def load_and_store_all():
    """Load all extracted JSON files and store in database"""
    
    # Initialize database
    init_database()
    
    # Load master JSON file
    master_json = 'extracted_data/all_invoices.json'
    
    if not os.path.exists(master_json):
        print("❌ No extracted data found. Run step5 first.")
        return
    
    with open(master_json, 'r') as f:
        invoices = json.load(f)
    
    print(f"\n📊 Found {len(invoices)} invoices to store\n")
    print("="*60)
    
    for invoice in invoices:
        source_file = invoice.get('source_file', 'unknown')
        print(f"\n📄 Storing: {source_file}")
        print(f"   Invoice: {invoice.get('invoice_number', 'N/A')}")
        print(f"   Vendor: {invoice.get('vendor_name', 'N/A')}")
        print(f"   Total: ${invoice.get('total_amount', 'N/A')}")
        
        try:
            # Check if already exists (avoid duplicates)
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM invoices WHERE source_file = ?', (source_file,))
            existing = cursor.fetchone()
            conn.close()
            
            if existing:
                print(f"   ⚠️ Already in database (ID: {existing[0]}), skipping")
                log_processing(source_file, 'store', 'skipped', 'Already exists')
            else:
                invoice_id = insert_invoice(invoice)
                log_processing(source_file, 'store', 'success')
                
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            log_processing(source_file, 'store', 'failed', str(e))
    
    # Show summary
    print("\n" + "="*60)
    print("✅ DATABASE STORAGE COMPLETE")
    print("="*60)
    
    # Query to show what's in database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM invoices')
    total_invoices = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM line_items')
    total_items = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"📊 Database: {DB_PATH}")
    print(f"📄 Total invoices stored: {total_invoices}")
    print(f"📦 Total line items stored: {total_items}")
    
    # Show recent invoices
    print("\n📋 Recent invoices in database:")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT invoice_number, vendor_name, total_amount, invoice_date 
        FROM invoices 
        ORDER BY id DESC 
        LIMIT 5
    ''')
    
    for row in cursor.fetchall():
        print(f"   - {row[0]} | {row[1]} | ${row[2]} | {row[3]}")
    
    conn.close()

def query_database():
    """Interactive queries to verify data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("🔍 DATABASE QUERIES")
    print("="*60)
    
    # Total by vendor
    print("\n💰 Total amount by vendor:")
    cursor.execute('''
        SELECT vendor_name, SUM(total_amount) as total
        FROM invoices
        GROUP BY vendor_name
        ORDER BY total DESC
    ''')
    
    for row in cursor.fetchall():
        print(f"   {row[0]}: ${row[1]:.2f}")
    
    # Invoice count by month
    print("\n📅 Invoices by month:")
    cursor.execute('''
        SELECT strftime('%Y-%m', invoice_date) as month, COUNT(*) as count
        FROM invoices
        WHERE invoice_date IS NOT NULL
        GROUP BY month
        ORDER BY month DESC
    ''')
    
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} invoices")
    
    conn.close()

if __name__ == "__main__":
    # Store all extracted data
    load_and_store_all()
    
    # Run some queries
    query_database()