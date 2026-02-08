import os
import json
from dotenv import load_dotenv
from google import genai
from schema import COREP_SCHEMA

# --------------------------------------------------
# Load environment variables
# --------------------------------------------------
load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

# --------------------------------------------------
# Helper: Extract JSON from LLM output
# (handles ```json ... ``` wrapping)
# --------------------------------------------------
def extract_json(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        # Remove markdown fences
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]

    return text.strip()

# --------------------------------------------------
# Step 1: User input (natural language)
# --------------------------------------------------
user_question = """
The bank has CET1 capital of £120 million
and Additional Tier 1 capital of £30 million.
"""

# --------------------------------------------------
# Step 2: Retrieve regulatory text (mock RAG)
# --------------------------------------------------
with open("rules/own_funds_rules.txt", "r") as f:
    regulatory_text = f.read()

# --------------------------------------------------
# Step 3: Prompt (STRICT JSON, units clarified)
# --------------------------------------------------
prompt = f"""
You are a regulatory reporting assistant.

Use ONLY the regulatory text below.
Do NOT invent rules.
Return STRICT JSON only.
Do not include explanations or markdown.

IMPORTANT:
- Values must be returned as absolute GBP amounts
  (e.g., £120 million = 120000000).

Regulatory Text:
{regulatory_text}

User Scenario:
{user_question}

Required JSON format:
{{
  "CET1 Capital": {{
    "value": number,
    "rule": "exact rule reference"
  }},
  "AT1 Capital": {{
    "value": number,
    "rule": "exact rule reference"
  }}
}}
"""

# --------------------------------------------------
# Step 4: Call Gemini 2.5 Flash
# --------------------------------------------------
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt
)

llm_output = response.text

# --------------------------------------------------
# Step 5: Parse JSON safely
# --------------------------------------------------
try:
    clean_json = extract_json(llm_output)
    data = json.loads(clean_json)
except Exception as e:
    raise ValueError(
        "LLM did not return valid JSON:\n\n" + llm_output
    ) from e

# --------------------------------------------------
# Step 6: Populate COREP schema
# --------------------------------------------------
for field in COREP_SCHEMA["fields"]:
    if field["name"] == "CET1 Capital":
        field["value"] = data["CET1 Capital"]["value"]
        field["rule"] = data["CET1 Capital"]["rule"]
    elif field["name"] == "AT1 Capital":
        field["value"] = data["AT1 Capital"]["value"]
        field["rule"] = data["AT1 Capital"]["rule"]

# --------------------------------------------------
# Step 7: Basic validation
# --------------------------------------------------
warnings = []

if COREP_SCHEMA["fields"][0]["value"] <= 0:
    warnings.append("CET1 Capital must be positive")

# --------------------------------------------------
# Step 8: Output results
# --------------------------------------------------
print("\n--- COREP TEMPLATE EXTRACT (C 01.00) ---")
for field in COREP_SCHEMA["fields"]:
    print(f"{field['code']} | {field['name']} | £{field['value']}")

print("\n--- VALIDATION ---")
if warnings:
    for w in warnings:
        print("WARNING:", w)
else:
    print("No validation issues found")

print("\n--- AUDIT LOG ---")
for field in COREP_SCHEMA["fields"]:
    print(f"{field['name']} justified by {field['rule']}")
