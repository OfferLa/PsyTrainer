import streamlit as st
import os
import litellm
import random  # We'll use this to pick a random question
from knowledge_base import knowledge_base

st.title("🎓 Psymon - המורה הפרטי שלך")

# For now, just display one random topic and question to prove it works
random_unit = random.choice(knowledge_base)

st.header(f"נושא: {random_unit['topic']}")
st.subheader(f"שאלה לדוגמה (מעמוד {random_unit['page_number']}):")
st.write(random_unit['question'])

st.info("בסיס הידע נטען בהצלחה! אנחנו מוכנים להתחיל לבנות את הלוגיקה של הבוט.")