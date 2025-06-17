import streamlit as st
import re
import mysql.connector
import json

# --- HELPER FUNCTION: Parse Score ---
def parse_score_from_feedback(feedback_text):
    match = re.search(r'\*\*?ציון:\*\*?\s*(\d+)\s*/\s*5', feedback_text)
    if match:
        return int(match.group(1))
    return None


# --- HELPER FUNCTION: Log to Database (Connect-on-Demand version) ---
def log_event_to_mysql(session_id, event_type, details_dict, topic=None, difficulty=None, scope=None, score=None):
    """
    Establishes a new connection, logs an event, and closes the connection.
    """
    conn = None  # Initialize conn to None to ensure it's available in the finally block
    try:
        # 1. Establish a new connection for this specific event
        conn = mysql.connector.connect(
            host=st.secrets["mysql"]["host"],
            port=st.secrets["mysql"]["port"],
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"],
            database=st.secrets["mysql"]["database"]
        )
        
        # 2. Use a 'with' statement for the cursor to ensure it's closed
        with conn.cursor() as cursor:
            details_json = json.dumps(details_dict, ensure_ascii=False)
            insert_query = """
            INSERT INTO session_logs (session_id, event_type, details, topic, difficulty, scope, score)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            record = (session_id, event_type, details_json, topic, difficulty, scope, score)
            cursor.execute(insert_query, record)
            conn.commit()

    except mysql.connector.Error as err:
        # Log the error to the Streamlit console for debugging
        st.error(f"Database Error: {err}")
        
    finally:
        # 3. IMPORTANT: Always close the connection
        if conn and conn.is_connected():
            conn.close()


# --- HELPER FUNCTION: Display RTL Text ---
def st_rtl_write(text: str):
    """
    A helper function to display text in Streamlit with RTL direction and right alignment.
    """
    st.markdown(
        f'<div style="direction: rtl; text-align: right;">{text}</div>',
        unsafe_allow_html=True
    )
