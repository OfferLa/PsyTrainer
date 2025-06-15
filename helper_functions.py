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


# --- DATABASE CONNECTION ---
@st.cache_resource
def init_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        port=st.secrets["mysql"]["port"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )



# --- HELPER FUNCTION: Log to Database ---
def log_event_to_mysql(conn, session_id, event_type, details_dict, topic=None, difficulty=None, scope=None, score=None):
    try:
        cursor = conn.cursor()
        details_json = json.dumps(details_dict, ensure_ascii=False)
        insert_query = """
        INSERT INTO session_logs (session_id, event_type, details, topic, difficulty, scope, score)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        record = (session_id, event_type, details_json, topic, difficulty, scope, score)
        cursor.execute(insert_query, record)
        conn.commit()
    except mysql.connector.Error as err:
        if err.errno == mysql.connector.errorcode.CR_SERVER_LOST:
            try:
                conn.reconnect()
                cursor = conn.cursor()
                cursor.execute(insert_query, record)
                conn.commit()
            except mysql.connector.Error as recon_err:
                 st.error(f"Database Reconnect Error: {recon_err}")
        else:
            st.error(f"Database Error: {err}")
    # finally:
        # cursor.close()
