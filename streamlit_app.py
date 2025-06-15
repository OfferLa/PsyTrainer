import streamlit as st
import os
import litellm
import random
import uuid
import json
import mysql.connector
import re
from helper_functions import parse_score_from_feedback, log_event_to_mysql
# import helper_functions


from knowledge_base import knowledge_base

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    os.environ['GEMINI_API_KEY'] = api_key
except KeyError:
    st.error("API key for Gemini is missing. Please check your .streamlit/secrets.toml file.")
    st.stop()

litellm.set_verbose = True

# --- PAGE LAYOUT AND STATE MANAGEMENT ---
st.title("🎓  המורה הפרטי שלך")

if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if 'current_question_unit' not in st.session_state:
    current_unit = random.choice(knowledge_base)
    st.session_state.current_question_unit = current_unit

# current_unit = st.session_state.current_question_unit

# if 'last_logged_topic' not in st.session_state or st.session_state.last_logged_topic != current_unit['topic']:
log_event_to_mysql(
        session_id=st.session_state.session_id, 
        event_type="QUESTION_PRESENTED", 
        details_dict={"questionText": current_unit['question']},
        topic=current_unit['topic'],
        difficulty=current_unit['difficulty'],
        scope=current_unit['scope']
    )
#    st.session_state.last_logged_topic = current_unit['topic']

st.header(f"נושא: {current_unit['topic']}")
st.subheader(f"שאלה לדוגמה (מעמוד {current_unit['page_number']}):")
st.write(current_unit['question'])
st.divider()
student_answer = st.text_area("הקלידי את תשובתך כאן:", height=150)

# --- THE CORRECTED AGENTIC WORKFLOW ---
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
    
    try:
        if not student_answer.strip():
            st.warning("אנא הקלידי תשובה לפני הלחיצה על הכפתור.")
            log_event_to_mysql(session_id, "TRIAGE_RESULT", {"classification": "empty_answer"})
        else:
            # --- AGENT 1: Triage Agent ---
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

            # --- CORRECTED LOGIC: The evaluation is now NESTED inside the 'valid_attempt' block ---
            if "valid_attempt" in classification:
                # --- AGENT 2: Evaluator Agent ---
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

            elif "no_knowledge" in classification:
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
            
            else: # Fallback for unknown classification from Triage Agent
                st.error("התרחשה שגיאה בניתוח התשובה. אנא נסי שוב.")
                log_event_to_mysql(session_id, "ERROR", {"source": "triage_logic", "message": "Unknown classification"})

    except Exception as e:
        st.error(f"An error occurred: {e}")
        log_event_to_mysql(session_id, "ERROR", {"source": "main_logic_block", "message": str(e)})
