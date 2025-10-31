#!/usr/bin/env python3
"""
Database management script for Oracle Chat API.

This script provides utilities for managing the database during development.
"""

import os
import sys
import argparse
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from config.database import init_database, cleanup_test_database, get_database_url
from sqlmodel import Session, create_engine, text


def clean_database():
    """Clean all data from the main database."""
    database_url = get_database_url()
    if "test_" in database_url:
        print("Cannot clean test database with this command. Use cleanup_test_database() instead.")
        return
    
    engine = create_engine(database_url)
    
    with Session(engine) as session:
        # Delete all messages first (foreign key constraint)
        result = session.exec(text("DELETE FROM message"))
        messages_deleted = result.rowcount
        
        # Delete all sessions
        result = session.exec(text("DELETE FROM session"))
        sessions_deleted = result.rowcount
        
        session.commit()
        
        print(f"Cleaned database: {messages_deleted} messages, {sessions_deleted} sessions deleted")


def reset_database():
    """Reset the database by dropping and recreating all tables."""
    database_url = get_database_url()
    if "test_" in database_url:
        print("Cannot reset test database with this command.")
        return
    
    # Remove the database file if it exists
    if database_url.startswith("sqlite:///"):
        db_file = database_url.replace("sqlite:///", "")
        if db_file.startswith("./"):
            db_file = db_file[2:]
        
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"Removed database file: {db_file}")
    
    # Recreate the database
    init_database()
    print("Database reset and initialized")


def show_stats():
    """Show database statistics."""
    database_url = get_database_url()
    engine = create_engine(database_url)
    
    try:
        with Session(engine) as session:
            # Count sessions
            session_count = session.exec(text("SELECT COUNT(*) FROM session")).first()
            
            # Count messages
            message_count = session.exec(text("SELECT COUNT(*) FROM message")).first()
            
            # Show recent sessions
            recent_sessions = session.exec(text(
                "SELECT id, title, message_count, created_at FROM session "
                "ORDER BY created_at DESC LIMIT 5"
            )).all()
            
            print(f"Database: {database_url}")
            print(f"Sessions: {session_count}")
            print(f"Messages: {message_count}")
            print("\nRecent sessions:")
            for session_data in recent_sessions:
                print(f"  {session_data[0]}: {session_data[1]} ({session_data[2]} messages) - {session_data[3]}")
                
    except Exception as e:
        print(f"Error reading database: {e}")


def main():
    parser = argparse.ArgumentParser(description="Oracle Chat Database Management")
    parser.add_argument("command", choices=["clean", "reset", "stats", "init"], 
                       help="Command to execute")
    
    args = parser.parse_args()
    
    if args.command == "clean":
        confirm = input("This will delete all sessions and messages. Continue? (y/N): ")
        if confirm.lower() == 'y':
            clean_database()
        else:
            print("Cancelled")
    elif args.command == "reset":
        confirm = input("This will completely reset the database. Continue? (y/N): ")
        if confirm.lower() == 'y':
            reset_database()
        else:
            print("Cancelled")
    elif args.command == "stats":
        show_stats()
    elif args.command == "init":
        init_database()
        print("Database initialized")


if __name__ == "__main__":
    main()