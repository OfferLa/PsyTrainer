# test_db.py
import mysql.connector
import json
import uuid
import toml

print("--- Starting Database Connection Test ---")

try:
    # Load secrets from the .toml file
    secrets = toml.load(".streamlit/secrets.toml")
    db_secrets = secrets.get("mysql", {})
    
    if not db_secrets:
        print("Error: [mysql] section not found in .streamlit/secrets.toml")
        exit()

    print("Successfully loaded database credentials.")

    # --- Establish the Database Connection ---
    # NOTE: This is the NON-SSL version. 
    conn = mysql.connector.connect(
        host=db_secrets["host"],
        port=db_secrets["port"],
        user=db_secrets["user"],
        password=db_secrets["password"],
        database=db_secrets["database"]
    )
    print("SUCCESS: Connection to the database was established.")

    # --- Test Writing to the Database ---
    print("Attempting to write a test record...")
    
    # Use 'with' statement for the cursor to ensure it's closed properly
    with conn.cursor() as cursor:
        test_session_id = str(uuid.uuid4())
        test_event_type = "CONNECTION_TEST"
        test_details = {"status": "success", "message": "This is a test record."}
        
        insert_query = """
        INSERT INTO session_logs (session_id, event_type, details)
        VALUES (%s, %s, %s)
        """
        record = (test_session_id, test_event_type, json.dumps(test_details))
        
        cursor.execute(insert_query, record)
        conn.commit()

    print("SUCCESS: A test record was written to the 'session_logs' table.")
    print("--- Test Completed Successfully! ---")

except mysql.connector.Error as e:
    print(f"\n!!! DATABASE ERROR !!!")
    print(f"An error occurred: {e}")
    print("\nTroubleshooting:")
    print("1. Double-check your host, user, password, and database name in secrets.toml.")
    print("2. Ensure your computer's IP address is allowed to connect if Aiven has IP whitelisting.")
    print("3. The most common error is needing an SSL connection. If the error mentions SSL, you will need to use the SSL version of the connection code.")

except FileNotFoundError:
    print("\nError: Could not find the '.streamlit/secrets.toml' file.")
    print("Please ensure the test script is in the same parent folder as the .streamlit directory.")

finally:
    # Ensure the connection is closed
    if 'conn' in locals() and conn.is_connected():
        conn.close()
        print("\nConnection closed.")
