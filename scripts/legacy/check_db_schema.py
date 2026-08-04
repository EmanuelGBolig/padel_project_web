import os
import django
import sqlite3

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

# Check database schema
conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

print("=== Checking accounts_division table schema ===")
cursor.execute("PRAGMA table_info(accounts_division);")
columns = cursor.fetchall()
for col in columns:
    print(f"{col[1]}: {col[2]} (nullable={col[3] == 0})")

print("\n=== Existing divisions ===")
cursor.execute("SELECT * FROM accounts_division;")
divisions = cursor.fetchall()
for div in divisions:
    print(f"ID: {div[0]}, Name: {div[1]}")

conn.close()
