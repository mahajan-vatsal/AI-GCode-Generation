import os
import json
import base64
from PIL import Image
from dotenv import load_dotenv
from openai import OpenAI
from langchain_core.tools import tool

load_dotenv()

client = OpenAI(
    api_key=os.getenv("FIREWORKS_API_KEY"),
    base_url="https://api.fireworks.ai/inference/v1"
)

def encode_image_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

base_prompt = """
You are an intelligent assistant that extracts structured data from an image of a business card.

The image is a business card sized 85x54mm. The origin (0,0) is at the bottom-left corner.
Also mention which VLM model you are using to extract the information.

Please analyze the layout and return ONLY a JSON object with fields like:
- name
- title
- phone
- email
- address
- company
- website
- logo (if applicable, logo of what?)
- qr_code (if applicable, where?)
- nfc_chip (if applicable, where?)
- Conference Name (for example ICE, IEEE)
- Conference Year (for example 2023)
- Topic Name (for example ICPS)

Only include fields that appear explicitly in the image. Do not make up information. Be specific.
Respond only with the raw JSON object (no explanation or formatting).
"""


def get_llm_response(base64_img: str) -> str:
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": base_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]
        }
    ]

    try:
        response = client.chat.completions.create(
            model="accounts/fireworks/models/qwen2p5-vl-32b-instruct",
            messages=messages,
            temperature=0,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("LLM error:", e)
        return "{}"


@tool(description="Extract structured information from image-based OCR of a business card using a VLM model.")
def ocr_info_extraction(image_path: str) -> dict:
    base64_img = encode_image_base64(image_path)
    llm_output = get_llm_response(base64_img)

    # Strip Markdown code block if present
    if llm_output.startswith("```json"):
        llm_output = llm_output.strip("```json").strip("```").strip()
    elif llm_output.startswith("```"):
        llm_output = llm_output.strip("```").strip()

    try:
        parsed = json.loads(llm_output)
    except json.JSONDecodeError:
        print("Warning: Could not parse LLM output. Raw output:", llm_output)
        parsed = {}

    return parsed
