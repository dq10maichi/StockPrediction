
import sys
import os
import argparse

# Add the 'script' directory to the system path to allow importing db_connector
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

from db_connector import DBConnector

def run_sql_file(file_path):
    """
    Executes the content of a given SQL file against the database.
    """
    db_connector = DBConnector()

    print(f"--- Attempting to execute SQL file: {file_path} ---")
    try:
        with open(file_path, 'r') as f:
            sql_content = f.read()
        
        with db_connector.connect() as conn:
            with conn.cursor() as cursor:
                print("Executing SQL...")
                cursor.execute(sql_content)
                print("SQL execution successful.")
            
            conn.commit()
            print("Changes have been committed to the database.")

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
    except Exception as e:
        print(f"An error occurred during SQL execution: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
        print("Changes have been rolled back.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Execute a SQL file on the project database.")
    parser.add_argument('sql_file', type=str, help="The path to the SQL file to execute.")
    args = parser.parse_args()
    
    # Ensure the path is absolute or resolve it relative to the project root
    # Assuming the script is run from the project root in the Docker container
    file_to_run = args.sql_file
    if not os.path.isabs(file_to_run):
        # In the Docker container, the app root is /app
        file_to_run = os.path.join('/app', file_to_run)

    run_sql_file(file_to_run)
