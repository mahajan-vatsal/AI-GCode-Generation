import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = "mistralai/mistral-7b-instruct:free"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

REFERER = "http://localhost"
TITLE = "SVG Card Editor"

def prepare_prompt(svg_elements, user_instruction):
    elements_str = json.dumps(svg_elements, indent=2)

    prompt = f"""
You are a helpful assistant that edits SVG business cards.

Coordinate system: The origin is BOTTOM-LEFT. Increasing y goes UP.

You are given a list of elements from an SVG file. Each element has:
- id
- type (text or image)
- content (text or href basename)
- x, y (bottom-left mm)
- width, height (mm if available)
- role (heuristic: logo / qr / nfc / text)
- position label (e.g., top-left, center-right)

SVG Elements:
{elements_str}

User wants to make the following changes:
\"\"\"
{user_instruction}
\"\"\"

Rules for targeting:
- Always select by the exact element id from the list above.
- Prefer elements whose 'role' matches the user's intent (e.g., nfc, qr, logo).
- Use absolute 'move' only if the user gives explicit absolute coordinates.
- Use 'move_by' for relative motions like left/right/up/down by N.

Respond ONLY with actionable edit commands (one per line), using this grammar:
- move <element_id> to x=<x_value> y=<y_value>
- move_by <element_id> dx=<number> dy=<number>
- delete <element_id>
- replace <element_id> with '<new_text_or_image>'

Do not output anything else.
"""
    return prompt

SYSTEM_MSG = """You write ONLY edit commands for an SVG editor.
Valid commands (one per line):
- move <element_id> to x=<number> y=<number>
- move_by <element_id> dx=<number> dy=<number>
- delete <element_id>
- replace <element_id> with '<new_text_or_image_href>'

Assumptions:
- The origin is bottom-left; increasing y moves up.

Rules:
- No explanations or prose.
- No variables or expressions. Only numbers.
- Do NOT change element IDs or suggest creating IDs.
- Use move_by for relative movement when user says 'left/right/up/down by ...'.
- If instruction is unclear or impossible with these commands, output nothing.
"""

def generate_edit_commands(prompt, max_tokens=200):
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user", "content": prompt}
        ],
        extra_headers={"HTTP-Referer": REFERER, "X-Title": TITLE},
        max_tokens=max_tokens,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()

def llm_svg_node(state):
    svg_elements = state["svg_elements"]
    user_instruction = state.get("edit_instruction", "Move logo to top-right")

    prompt = prepare_prompt(svg_elements, user_instruction)
    edit_commands = generate_edit_commands(prompt)
    state["edit_commands"] = edit_commands
    return state
