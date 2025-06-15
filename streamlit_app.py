# =================================================================
# ===          CORRECTED AND REFACTORED streamlit_app.py        ===
# =================================================================

import streamlit as st
import os
import litellm
import random
import uuid
import json
import mysql.connector
import re # We need this for the score parser

# --- HELPER FUNCTION: Parse Score (This was the missing piece) ---
def parse_score_from_feedback(feedback_text):
    """
    Uses regular expressions to find and extract the score from the feedback string.
    Example input: "**ציון:** 4/5\n**נימוק:** ..."
    Returns: The integer 4, or None if not found.
    """
    # This regex looks for the pattern "ציון:", optional bolding/spaces, a number, a slash, and a 5.
    match = re.search(r'\*\*?ציון:\*\*?\s*(\d+)\s*/\s*5', feedback_text)
    if match:
        return int(match.group(1))
    return None # Return None if the pattern isn't found

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

conn = init_connection()

# --- HELPER FUNCTION: Log to Database ---
def log_event_to_mysql(session_id, event_type, details_dict, topic=None, difficulty=None, scope=None, score=None):
    """Formats and logs an event to the MySQL database."""
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
            conn.reconnect()
            cursor = conn.cursor()
            cursor.execute(insert_query, record)
            conn.commit()
        else:
            st.error(f"Database Error: {err}")
    finally:
        if 'cursor' in locals() and cursor.is_open():
            cursor.close()

# --- SETUP AND IMPORTS ---
from knowledge_base import knowledge_base

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    os.environ['GEMINI_API_KEY'] = api_key
except Exception:
    st.error("API key for Gemini is missing. Please check your .streamlit/secrets.toml file.")
    st.stop()

litellm.set_verbose = False # Set to False for cleaner output

# --- PAGE LAYOUT AND STATE MANAGEMENT ---
st.title("🎓  המורה הפרטי שלך")

if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if 'current_question_unit' not in st.session_state:
    st.session_state.current_question_unit = random.choice(knowledge_base)

current_unit = st.session_state.current_question_unit

if 'last_logged_topic' not in st.session_state or st.session_state.last_logged_topic != current_unit['topic']:
    log_event_to_mysql(
        session_id=st.session_state.session_id, 
        event_type="QUESTION_PRESENTED", 
        details_dict={"questionText": current_unit['question']},
        topic=current_unit['topic'],
        difficulty=current_unit['difficulty'],
        scope=current_unit['scope']
    )
    st.session_state.last_logged_topic = current_unit['topic']

st.header(f"נושא: {current_unit['topic']}")
st.subheader(f"שאלה לדוגמה (מעמוד {current_unit['page_number']}):")
st.write(current_unit['question'])
st.divider()
student_answer = st.text_area("הקלידי את תשובתך כאן:", height=150)

# --- THE REFACTORED AGENTIC WORKFLOW ---
if st.button("הערך את תשובתי"):
    session_id = st.session_state.session_id
    
    log_event_to_mysql(
        session_id=session_id, 
        event_type="SUBMISSION_ATTEMPT", 
        details_dict={"questionText": current_unit['question'], "studentAnswer": student_answer},
        topic=current_unit['topic'],
        difficulty=current_unit['difficulty'],
        scope=current_unit['scope']
    )
    
    # We now wrap the entire logic in ONE try...except block for robustness
    try:
        if not student_answer.strip():
            st.warning("אנא הקלידי תשובה לפני הלחיצה על הכפתור.")
            log_event_to_mysql(session_id, "TRIAGE_RESULT", {"classification": "empty_answer"})
        else:
            with st.spinner("...קורא את התשובה"):
                triage_prompt = f"""
                You are a text classification agent. Classify the student's answer into one of these three categories:
                - `valid_attempt`: The student is trying to answer the question.
                - `no_knowledge`: The student states they don't know the answer or are unsure.
                - `gibberish`: The answer is nonsense or random characters.
                Student's Answer: "{student_answer}"
                ---
                Respond with ONLY ONE WORD: valid_attempt, no_knowledge, or gibberish.
                """
                triage_response = litellm.completion(model="gemini/gemini-1.5-flash-latest", messages=[{"role": "user", "content": triage_prompt}])
                classification = triage_response.choices[0].message.content.strip().lower()
                log_event_to_mysql(session_id, "TRIAGE_RESULT", {"classification": classification})

            if "no_knowledge" in classification:
                response_text = (
                    "אין שום בעיה! זו הרגשה טבעית לגמרי בתהליך למידה. "
                    f"הנושא הזה מופיע בעמוד {current_unit['page_number']}. נסי לקרוא שוב את החלק הרלוונטי ולנסות שוב!"
                )
                st.info(response_text)
                log_event_to_mysql(session_id, "SYSTEM_RESPONSE", {"type": "hint_and_encourage", "text": response_text})

            elif "gibberish" in classification:
                response_text = "נראה שהתשובה שהוקלדה אינה ברורה. אנא נסי לנסח תשובה מלאה."
                st.warning(response_text)
                log_event_to_mysql(session_id, "SYSTEM_RESPONSE", {"type": "request_clearer_answer", "text": response_text})

            elif "valid_attempt" in classification:
                with st.spinner("המערכת מעריכה את תשובתך..."):
                    evaluation_prompt = f"""
                    You are an assistant that evaluates a student's answer against an ideal answer from a textbook. The interaction must be in HEBREW, Female form.
                    **Sample of an Ideal Answer (in Hebrew) to this question:** {current_unit['ideal_answer']}
                    **Key Concepts the student should mention (in Hebrew):** {current_unit['key_concepts']}
                    **Student's Answer (in Hebrew):** {student_answer}
                    ---
                    Based ONLY on the information above, perform the following tasks in HEBREW:
                    1. Provide a score from 1 (completely wrong) to 5 (perfect).
                    2. Provide a short, one-sentence justification for your score.
                    3. Provide friendly and constructive feedback to help the student learn.
                    Format your response exactly as follows:
                    **ציון:** [Score]/5
                    **נימוק:** [Justification]
                    **משוב:** [Feedback]
                    """
                    evaluation_response = litellm.completion(model="gemini/gemini-1.5-flash-latest", messages=[{"role": "user", "content": evaluation_prompt}])
                    feedback_text = evaluation_response.choices[0].message.content
                    st.markdown("---"); st.subheader("הערכה של תשובתך:"); st.markdown(feedback_text)
                    
                    numeric_score = parse_score_from_feedback(feedback_text)
                    
                    log_event_to_mysql(
                        session_id=session_id,
                        event_type="EVALUATION_RESULT",
                        details_dict={"rawFeedback": feedback_text},
                        topic=current_unit['topic'],
                        difficulty=current_unit['difficulty'],
                        scope=current_unit['scope'],
                        score=numeric_score
                    )
            
            else: # Fallback for unknown classification
                st.error("התרחשה שגיאה בניתוח התשובה. אנא נסי שוב.")
                log_event_to_mysql(session_id, "ERROR", {"source": "triage_logic", "message": "Unknown classification"})

    except Exception as e:
        st.error(f"An error occurred while calling the AI model: {e}")
        log_event_to_mysql(session_id, "ERROR", {"source": "llm_call", "message": str(e)})