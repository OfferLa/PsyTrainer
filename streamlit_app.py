import streamlit as st
import os
import litellm
import random
# We import our hardcoded knowledge base
from knowledge_base import knowledge_base

# --- API KEY SETUP (from your code) ---
# This is the correct way to handle multiple keys
try:
    # os.environ['OPENROUTER_API_KEY'] = st.secrets["OPENROUTER_API_KEY"]
    print(st.secrets["GEMINI_API_KEY"])
    # api_key = "AIzaSyDsL4KAoLPn8JYuEh0SZch_AmZKrTKqjmc"
    api_key = st.secrets["GEMINI_API_KEY"]
    print(f"api_key: {api_key}")
    print(api_key)
    os.environ['GEMINI_API_KEY'] = api_key
    print(f"environ: {os.environ['GEMINI_API_KEY']}")
except Exception:
    st.error("One or more API keys are missing. Please check your .streamlit/secrets.toml file.")
    st.stop()

litellm.set_verbose = True

# --- STREAMLIT PAGE SETUP ---
st.title("🎓  המורה הפרטי שלך")

# --- CORE LOGIC ---
# We use session_state to remember which question was asked
if 'current_question_unit' not in st.session_state:
    st.session_state.current_question_unit = random.choice(knowledge_base)

# Get the current question from session state
current_unit = st.session_state.current_question_unit

# Display the question
st.header(f"נושא: {current_unit['topic']}")
st.subheader(f"שאלה לדוגמה (מעמוד {current_unit['page_number']}):")
st.write(current_unit['question'])

st.divider() # Add a visual separator

# --- Wait for the student's answer ---
# st.text_area is better for longer, multi-line answers
student_answer = st.text_area("הקלידי את תשובתך כאן:", height=150)

# The "Evaluate" button
if st.button("הערך את תשובתי"):
    if not student_answer.strip():
        st.warning("אנא הקלידי תשובה לפני הלחיצה על הכפתור.")
    else:
        # --- LLM EVALUATION LOGIC ---
        with st.spinner("המערכת מעריכה את תשובתך..."):
            
            # This is the highly structured prompt for the Gemini model
            evaluation_prompt = f"""
            You are an assistant that evaluates a student's answer against an ideal answer from a textbook.
            The interaction must be in HEBREW, Female form.

            **Sample of an Ideal Answer (in Hebrew) to this question:**
            {current_unit['ideal_answer']}

            **Key Concepts the student should mention (in Hebrew):**
            {current_unit['key_concepts']}

            **Student's Answer (in Hebrew):**
            {student_answer}

            ---
            Based ONLY on the information above, perform the following tasks in HEBREW:
            1.  Provide a score from 1 (completely wrong) to 5 (perfect).
            2.  Provide a short, one-sentence justification for your score.
            3.  Provide friendly and constructive feedback to help the student learn.

            Format your response exactly as follows:
            **ציון:** [Score]/5
            **נימוק:** [Justification]
            **משוב:** [Feedback]
            """
            
            try:
                # This is the actual LLM call using litellm
                evaluation_response = litellm.completion(
                    # We specify the gemini flash model directly
                    model="gemini/gemini-1.5-flash-latest",
                    messages=[{"role": "user", "content": evaluation_prompt}]
                )
                
                feedback_text = evaluation_response.choices[0].message.content
                st.markdown("---")
                st.subheader("הערכה של תשובתך:")
                st.markdown(feedback_text)

            except Exception as e:
                st.error(f"An error occurred while calling the AI model: {e}")
