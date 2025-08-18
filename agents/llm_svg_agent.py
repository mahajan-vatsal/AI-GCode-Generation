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

Each element includes:
- id
- type (text or image)
- content (text or basename)
- x, y (bottom-left mm)
- width, height (mm if available)
- role (logo / qr / nfc / icon / text)
- position label (e.g., top-left, center-right)

SVG Elements:
{elements_str}

User wants to make the following changes:
\"\"\"
{user_instruction}
\"\"\"

STRICT targeting rules:
- If the user mentions NFC, choose ONLY elements with role == "nfc". If none exist, output nothing.
- If the user mentions QR, choose ONLY elements with role == "qr". If none exist, output nothing.
- If the user mentions logo, choose elements with role == "logo".
- Never choose text elements when the user refers to NFC/QR/logo/icon.

Size changes:
- Use 'resize <id> to width=<mm> height=<mm>' for absolute size in mm.
- Use 'scale_by <id> s=<factor>' for uniform relative scaling.
- Use 'scale_by <id> sx=<fx> sy=<fy>' for non-uniform relative scaling.

Adding new content:
- Add text:  add_text <new_id> at x=<mm> y=<mm> text='<content>' [size=<mm>] [family='<font>'] [weight=normal|bold] [anchor=start|middle|end]
- Add logo:  add_logo <new_id> at x=<mm> y=<mm> width=<mm> height=<mm> src='<asset_name>'
- Add image: add_image <new_id> at x=<mm> y=<mm> width=<mm> height=<mm> src='<asset_or_url_or_datauri>' [role=logo|icon|qr|nfc|image] [name='<display_name>']
  * For logo/icon/qr/nfc image sources, prefer the asset NAME only (e.g., 'xyz_logo'); the system will resolve it locally.

Respond ONLY with edit commands (one per line):
- move <element_id> to x=<x_value> y=<y_value>
- move_by <element_id> dx=<number> dy=<number>
- delete <element_id>
- replace <element_id> with '<new_text_or_image>'
- resize <element_id> to width=<number> height=<number>
- scale_by <element_id> s=<number>
- scale_by <element_id> sx=<number> sy=<number>
- add_text <new_id> at x=<number> y=<number> text='<text>' [size=<number>] [family='<font>'] [weight=normal|bold] [anchor=start|middle|end]
- add_logo <new_id> at x=<number> y=<number> width=<number> height=<number> src='<asset_name>'
- add_image <new_id> at x=<number> y=<number> width=<number> height=<number> src='<token>' [role=logo|icon|qr|nfc|image] [name='<display_name>']
"""
    return prompt

SYSTEM_MSG = """You write ONLY edit commands for an SVG editor.
Valid commands (one per line):
- move <element_id> to x=<number> y=<number>
- move_by <element_id> dx=<number> dy=<number>
- delete <element_id>
- replace <element_id> with '<new_text_or_image_href>'
- resize <element_id> to width=<number> height=<number>
- scale_by <element_id> s=<number>
- scale_by <element_id> sx=<number> sy=<number>
- add_text <new_id> at x=<number> y=<number> text='<text>' [size=<number>] [family='<font>'] [weight=normal|bold] [anchor=start|middle|end]
- add_logo <new_id> at x=<number> y=<number> width=<number> height=<number> src='<asset_name>'
- add_image <new_id> at x=<number> y=<number> width=<number> height=<number> src='<token>' [role=logo|icon|qr|nfc|image] [name='<display_name>']

Assumptions:
- The origin is bottom-left; increasing y moves up.

Rules:
- No explanations or prose.
- No variables or expressions. Only numbers.
- Do NOT change element IDs on existing elements or suggest creating IDs for them.
- For adding NEW elements, choose a simple, human-readable new_id (e.g., 'logo_bmw', 'text_tagline'). The system will make it unique if needed.
- Select elements whose role matches the user's target (nfc/qr/logo/icon). If none, output nothing.
- Use move_by for relative movement (left/right/up/down by ...).
- For TEXT or IMAGE content changes, use ONLY 'replace' (never 'delete' and 'replace' on the same element).
- For logo/icon/qr/nfc image swaps or additions, output the asset NAME only (e.g., 'xyz_logo' without path or extension). The system will resolve it to a local asset.
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
