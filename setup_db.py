import sqlite3
from pathlib import Path

# Define the database directory and file path
DATABASE_DIR = Path("data")
DATABASE_FILE = DATABASE_DIR / "data.db"

def setup_database():
    # Ensure the data directory exists
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    # Connect to the SQLite database (creates the file if it doesn't exist)
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Create Projects table with status
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_number TEXT NOT NULL,
            date TEXT NOT NULL,
            crew_initials TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'  -- Added status field
        );
    """)

    # Create Structures table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Structures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            project_location TEXT NOT NULL,
            structure_id TEXT NOT NULL,
            collection_date TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES Projects (id)
        );
    """)

    # Create Files table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            structure_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            path TEXT NOT NULL,
            FOREIGN KEY (structure_id) REFERENCES Structures (id)
        );
    """)

    # Optional: Add archival metadata fields
    # Uncomment the following lines if you want to track when and by whom a project was archived
    # cursor.execute("""
    #     ALTER TABLE Projects ADD COLUMN archived_at TEXT;
    # """)
    # cursor.execute("""
    #     ALTER TABLE Projects ADD COLUMN archived_by TEXT;
    # """)

    # Commit changes and close connection
    conn.commit()
    conn.close()
    print(f"Database setup complete. File created at: {DATABASE_FILE}")

if __name__ == "__main__":
    setup_database()
