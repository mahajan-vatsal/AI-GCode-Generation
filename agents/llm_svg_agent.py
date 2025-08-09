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

You are given a list of elements from an SVG file. Each element has:
- id
- type (text or image)
- content (text or href)
- x, y (position)
- position label (e.g., top-left, center-right)

SVG Elements:
{elements_str}

User wants to make the following changes:
\"\"\"
{user_instruction}
\"\"\"

Only use `move` when the user explicitly requests it. Prefer referencing element IDs over guessing.
Respond ONLY with actionable edit commands in one of these formats:
- move <element_id> to x=<x_value> y=<y_value>
- delete <element_id>
- replace <element_id> with '<new_text_or_image>'

Don't perform any action that is not explicitly requested by the user.
"""
    return prompt

def generate_edit_commands(prompt, max_tokens=300):
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "user", "content": prompt}
        ],
        extra_headers={
            "HTTP-Referer": REFERER,
            "X-Title": TITLE,
        },
        max_tokens=max_tokens,
        temperature=0.4,
    )

    return response.choices[0].message.content.strip()

def llm_svg_node(state):
    svg_elements = state["svg_elements"]
    user_instruction = state.get("edit_instruction", "Move logo to top-right")

    prompt = prepare_prompt(svg_elements, user_instruction)
    edit_commands = generate_edit_commands(prompt)
    state["edit_commands"] = edit_commands
    return state