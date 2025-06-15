# File: debug_gemini.py
import os
import litellm

# --- FOR DEBUGGING ONLY ---
# Paste your actual key here.
# WARNING: DO NOT COMMIT THIS FILE TO GITHUB!
GEMINI_API_KEY = "AIzaSyDsL4KAoLPn8JYuEh0SZch_AmZKrTKqjmc"
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

# --- THIS IS THE KEY ---
# Tell litellm to print everything
litellm.set_verbose = True

print("Attempting to call Gemini API...")

try:
    response = litellm.completion(
        model="gemini/gemini-1.5-flash-latest",
        messages=[{"role": "user", "content": "hello, how are you?"}]
    )
    print("\n--- SUCCESS! ---")
    print(response)

except Exception as e:
    print(f"\n--- FAILED! ---")
    print(f"Error: {e}")