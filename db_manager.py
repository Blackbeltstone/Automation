import sqlite3
from pathlib import Path

DATABASE_FILE = Path("data/data.db")


def connect_db():
    """Connect to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # Enable dictionary-like row access
    return conn


def execute_query(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False, return_lastrowid: bool = False):
    """Generic function to execute a database query."""
    conn = None
    lastrowid = None
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if return_lastrowid:
            lastrowid = cursor.lastrowid
        
        result = None
        if fetch_one:
            result = cursor.fetchone()
        if fetch_all:
            result = cursor.fetchall()
        
        conn.commit()
        if return_lastrowid:
            return result, lastrowid
        return result
    except Exception as e:
        print(f"Error executing query: {query} with params: {params}. Error: {e}")
        raise
    finally:
        if conn:
            conn.close()


# --- CRUD for Projects ---
def insert_project(project_number, date, crew_initials, status="active"):
    query = """
        INSERT INTO Projects (project_number, date, crew_initials, status)
        VALUES (?, ?, ?, ?)
    """
    params = (project_number, date, crew_initials, status)
    conn = connect_db()
    cursor = conn.cursor()
    
    # Check if the project exists
    cursor.execute(
        "SELECT id FROM Projects WHERE project_number = ? AND date = ? AND crew_initials = ?",
        (project_number, date, crew_initials)
    )
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return existing["id"]
    
    # Insert new project
    cursor.execute(query, params)
    conn.commit()
    project_id = cursor.lastrowid
    conn.close()
    return project_id


def update_project_status(project_id, status):
    query = "UPDATE Projects SET status = ? WHERE id = ?"
    params = (status, project_id)
    execute_query(query, params)


def get_all_projects():
    """Retrieve all projects."""
    query = "SELECT * FROM Projects"
    return execute_query(query, fetch_all=True)


def get_project_by_id(project_id):
    """Fetch a project by its ID."""
    query = "SELECT * FROM Projects WHERE id = ?"
    params = (project_id,)
    return execute_query(query, params, fetch_one=True)


def get_projects_with_sites_and_dates():
    """Fetch projects with their associated sites, structure IDs, and dates."""
    query = """
        SELECT 
            p.project_number, 
            s.id AS structure_db_id,
            s.project_location, 
            s.structure_id, 
            s.collection_date
        FROM Projects p
        JOIN Structures s ON p.id = s.project_id
        ORDER BY p.project_number, s.project_location, s.collection_date
    """
    results = execute_query(query, fetch_all=True)

    # Organize data hierarchically
    projects = {}
    for row in results:
        project_number = row["project_number"]
        structure_db_id = row["structure_db_id"]  # New field
        site = row["project_location"]
        structure_id = row["structure_id"]
        collection_date = row["collection_date"]

        # Initialize project if not already present
        if project_number not in projects:
            projects[project_number] = {}

        # Initialize site if not already present
        if site not in projects[project_number]:
            projects[project_number][site] = []

        # Append structure information to the site
        projects[project_number][site].append({
            "structure_db_id": structure_db_id,  # Include structure_db_id
            "structure_id": structure_id,
            "date": collection_date
        })

    return projects


def delete_project(project_id):
    """Delete a project by its ID."""
    query = "DELETE FROM Projects WHERE id = ?"
    params = (project_id,)
    execute_query(query, params)


# --- CRUD for Structures ---
def insert_structure(project_id, project_location, structure_id, collection_date):
    """Insert or fetch a structure for a given project."""
    try:
        conn = connect_db()
        cursor = conn.cursor()

        # Check if the structure already exists
        cursor.execute(
            """
            SELECT id FROM Structures
            WHERE project_id = ? AND project_location = ? AND structure_id = ? AND collection_date = ?
            """,
            (project_id, project_location, structure_id, collection_date),
        )
        result = cursor.fetchone()

        # If the structure exists, return its ID
        if result:
            print(f"DEBUG: Structure already exists with ID: {result['id']}")
            return result["id"]

        # Otherwise, insert the new structure
        cursor.execute(
            """
            INSERT INTO Structures (project_id, project_location, structure_id, collection_date)
            VALUES (?, ?, ?, ?)
            """,
            (project_id, project_location, structure_id, collection_date),
        )
        conn.commit()
        structure_db_id = cursor.lastrowid
        print(f"DEBUG: Inserted new structure with ID: {structure_db_id}")
        return structure_db_id
    except Exception as e:
        print(f"ERROR inserting structure: {e}")
        raise
    finally:
        conn.close()



def get_structures_by_project(project_id):
    """Retrieve all structures for a given project."""
    query = "SELECT * FROM Structures WHERE project_id = ?"
    params = (project_id,)
    return execute_query(query, params, fetch_all=True)


def delete_structure(structure_id):
    """Delete a structure by its ID."""
    query = "DELETE FROM Structures WHERE id = ?"
    params = (structure_id,)
    execute_query(query, params)


def get_structure_by_id(structure_id):
    """Fetch a structure by its ID."""
    query = "SELECT * FROM Structures WHERE id = ?"
    params = (structure_id,)
    return execute_query(query, params, fetch_one=True)


def get_files_by_structure_and_date(structure_db_id, collection_date):
    """Fetch all files for a specific structure and date."""
    query = """
        SELECT filename, path
        FROM Files
        WHERE structure_id = ? AND path LIKE ?
    """
    params = (structure_db_id, f"%{collection_date}%")
    return execute_query(query, params, fetch_all=True)


# --- CRUD for Files ---
def insert_file(structure_id, filename, full_path):
    try:
        relative_path = Path(full_path).relative_to("data").as_posix()
        query = "INSERT INTO Files (structure_id, filename, path) VALUES (?, ?, ?)"
        params = (structure_id, filename, relative_path)
        print(f"DEBUG: Inserting file with params: {params}")
        result, file_id = execute_query(query, params, return_lastrowid=True)
        return file_id
    except Exception as e:
        print(f"ERROR inserting file record: {e}")
        raise



def get_files_by_structure(structure_id):
    """Retrieve all files for a given structure."""
    query = "SELECT * FROM Files WHERE structure_id = ?"
    params = (structure_id,)
    return execute_query(query, params, fetch_all=True)


def delete_file(file_id):
    """Delete a file by its ID."""
    query = "DELETE FROM Files WHERE id = ?"
    params = (file_id,)
    execute_query(query, params)


