"""
Database migration utilities.
"""
import os
from sqlalchemy import text
from . import engine


def run_sql_migrations():
    """
    Run all SQL migration files in the migrations directory.
    
    Migration files should:
    - Be named with a sortable prefix (e.g., 001_initial.sql, 002_add_columns.sql)
    - End with .sql extension
    - Be idempotent (safe to run multiple times)
    
    Raises:
        Exception: If any migration fails
    """
    # Get migrations directory path
    # Assuming migrations/ is at the same level as app/
    app_dir = os.path.dirname(__file__)
    migrations_dir = os.path.join(app_dir, "scripts")
    print("migration dir", migrations_dir)
    
    if not os.path.exists(migrations_dir):
        print(f"Warning: Migrations directory not found at {migrations_dir}")
        return
    
    # Get all .sql files and sort them
    migration_files = sorted(
        f for f in os.listdir(migrations_dir) 
        if f.endswith(".sql")
    )
    
    if not migration_files:
        print("No migration files found")
        return
    
    # Execute each migration
    with engine.begin() as conn:
        print("migration_files", migration_files)
        for filename in migration_files:
            filepath = os.path.join(migrations_dir, filename)
            print(f"Running migration: {filename}")
            
            with open(filepath, "r", encoding="utf-8") as f:
                sql = f.read()
            
            conn.execute(text(sql))
            print(f"✓ Completed: {filename}")
    
    print(f"Successfully executed {len(migration_files)} migration(s)")
