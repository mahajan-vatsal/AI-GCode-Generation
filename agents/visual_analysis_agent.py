from PIL import Image
from langchain_core.tools import tool
from pyzbar.pyzbar import decode
import cv2
import json
import dotenv   
dotenv.load_dotenv()

DEFAULT_CARD_WIDTH_MM = 85.0
DEFAULT_CARD_HEIGHT_MM = 54.0
DEFAULT_DPI = 300
MM_PER_INCH = 25.4

def get_px_to_mm_ratio(image_path: str, dpi: int = DEFAULT_DPI):
    with Image.open(image_path) as img:
        width_px, height_px = img.size
    width_mm = (width_px / dpi) * MM_PER_INCH
    height_mm = (height_px / dpi) * MM_PER_INCH
    return width_mm / width_px, width_px, height_px, height_mm


def get_bounding_boxes_qwen(image_path: str) -> list:
    from openai import OpenAI
    import base64
    import os
    import json
    import re

    client = OpenAI(
        api_key=os.getenv("FIREWORKS_API_KEY"),
        base_url="https://api.fireworks.ai/inference/v1"
    )

    with open(image_path, "rb") as f:
        b64_img = base64.b64encode(f.read()).decode("utf-8")

    prompt = """
You are a layout detection model.

Analyze this business card image and return bounding boxes for each visible item:
- Individual text elements (word-level only, no paragraphs or lines)
- QR code (if present)
- NFC chip (if present)
- Logos (brand or organizational symbols, usually top-left/top-right)
- Icons (phone, email, web, location, etc.)

Return the results as a **JSON array**. For each item, include:
{
  "type": ...,        # "name" | "university" | "designation" | "logo" | "icon" | "qr" | "nfc" | "text"
  "text": "...",      
  "x": ...,           
  "y": ...,           
  "width": ...,       
  "height": ...,      
  "font family": ...,  
  "label": ...,
  "confidence": ...,
  "font weight": ...,   # e.g., "normal", "bold"
  "alignment": ...      # "left", "center", or "right"
}

Do not include summaries or markdown. Return only the JSON array as valid output.
"""

    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
        ]
    }]

    try:
        response = client.chat.completions.create(
            model="accounts/fireworks/models/qwen2p5-vl-32b-instruct",
            messages=messages,
            temperature=0.2
        )
        raw = response.choices[0].message.content.strip()
        print("🧠 Qwen Raw Output:\n", raw)
    except Exception as e:
        raise RuntimeError(f"Error during Qwen2.5-VL API call: {e}")

    # First try to parse full response as JSON array directly
    try:
        if raw.startswith("[") and raw.endswith("]"):
            return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Fallback: Try extracting JSON array inside triple backticks
    match = re.search(r'```json\s*(\[\s*{.*?}\s*])\s*```', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Fallback: check if it contains a dict of coordinate arrays
    match = re.search(r'```json\s*({.*?})\s*```', raw, re.DOTALL)
    if match:
        try:
            fallback_dict = json.loads(match.group(1).strip())
            fallback_boxes = []
            for label, coords in fallback_dict.items():
                if not isinstance(coords, list) or len(coords) != 4:
                    continue
                x1, y1, x2, y2 = coords
                fallback_boxes.append({
                    "type": "text" if "name" not in label.lower() else "name",
                    "text": label,
                    "x": x1,
                    "y": y1,
                    "width": x2 - x1,
                    "height": y2 - y1,
                    "font family": "Arial",
                    "label": label,
                    "confidence": 0.5
                })
            return fallback_boxes
        except:
            pass

    raise ValueError("No valid JSON array or fallback bounding box dictionary found in Qwen response.")


def enrich_with_geometry(bboxes_px: list, px_to_mm_ratio: float, height_px: int) -> list:
    enriched = []
    for item in bboxes_px:
        x_px, y_px, w_px, h_px = item["x"], item["y"], item["width"], item["height"]

        y_mm = (height_px - y_px) * px_to_mm_ratio
        x_mm = x_px * px_to_mm_ratio
        width_mm = w_px * px_to_mm_ratio
        height_mm = h_px * px_to_mm_ratio
        font_size = round(height_mm, 2)

        enriched.append({
            "type": item["type"],
            "text": item.get("text", ""),
            "x": round(x_mm, 2),
            "y": round(y_mm, 2),
            "width": round(width_mm, 2),
            "height": round(height_mm, 2),
            "font_size": font_size,
            "font_family": item.get("font family", "Arial"),
            "label": item.get("label", ""),
            "confidence": item.get("confidence", None),
            "alignment": item.get("alignment", "left"),
            "font_weight": item.get("font weight", "normal")
        })
    return enriched


def scale_layout_items(layout_items: list, max_width: float = 85.0, max_height: float = 54.0):
    if not layout_items:
        return layout_items

    max_x = max(item["x"] + item.get("width", 0) for item in layout_items)
    max_y = max(item["y"] for item in layout_items)

    scale_x = max_width / max_x if max_x > max_width else 1.0
    scale_y = max_height / max_y if max_y > max_height else 1.0
    scale = min(scale_x, scale_y)

    for item in layout_items:
        item["x"] *= scale
        item["y"] *= scale
        item["width"] *= scale
        item["height"] *= scale
        item["font_size"] *= scale

    return layout_items


def decode_qr_from_image(image_path: str):
    image = cv2.imread(image_path)
    decoded_objs = decode(image)
    if not decoded_objs:
        return None
    return decoded_objs[0].data.decode("utf-8")  # Return first detected QR


def overlay_layout_debug(image_path: str, enriched_boxes: list, px_to_mm_ratio: float, height_px: int, save_path="debug_overlay.png"):
    img = cv2.imread(image_path)
    for item in enriched_boxes:
        x = int(item["x"] / px_to_mm_ratio)
        y = int(height_px - (item["y"] / px_to_mm_ratio))
        w = int(item["width"] / px_to_mm_ratio)
        h = int(item["height"] / px_to_mm_ratio)

        color = (0, 255, 0) if item["type"] in ("text", "name") else (255, 0, 0)
        label = item.get("text") or item.get("label") or item["type"]

        cv2.rectangle(img, (x, y - h), (x + w, y), color, 1)
        cv2.putText(img, label, (x, y - h - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    cv2.imwrite(save_path, img)
    print(f"🖼️ Debug overlay saved to {save_path}")


@tool(description="Fast hybrid layout analysis using Qwen2.5-VL for bounding boxes.")
def visual_analysis_agent(image_path: str, debug: bool = False) -> dict:
    px_to_mm_ratio, width_px, height_px, height_mm = get_px_to_mm_ratio(image_path)

    print("📸 Running Qwen2.5-VL for bounding boxes...")
    raw_boxes = get_bounding_boxes_qwen(image_path)
    print(f"📦 Detected {len(raw_boxes)} bounding boxes")

    if not isinstance(raw_boxes, list) or not all(isinstance(b, dict) for b in raw_boxes):
        raise ValueError("Invalid layout format from Qwen. Expected list of dicts.")

    enriched = enrich_with_geometry(raw_boxes, px_to_mm_ratio, height_px)
    enriched = scale_layout_items(enriched)

    qr_code = next((b for b in enriched if b["type"] == "qr"), None)
    nfc_chip = next((b for b in enriched if b["type"] == "nfc"), None)
    logos = [b for b in enriched if b["type"] == "logo"]
    icons = [b for b in enriched if b["type"] in ("icon", "emoji")]
    text_blocks = [b for b in enriched if b["type"] in (
        "text", "name", "university", "designation", "Conference Name", "Conference Year", "Topic Name (for example ICPS)"
    )]

    qr_data = decode_qr_from_image(image_path)
    if qr_code and qr_data:
        qr_code["decoded_content"] = qr_data

    if debug:
        print(json.dumps({
            "text_blocks": text_blocks,
            "qr_code": qr_code,
            "nfc_chip": nfc_chip,
            "logos": logos,
            "icons": icons
        }, indent=2))

        overlay_layout_debug(
            image_path=image_path,
            enriched_boxes=enriched,
            px_to_mm_ratio=px_to_mm_ratio,
            height_px=height_px,
            save_path="debug_overlay.png"
        )

    return {
        "text_blocks": text_blocks,
        "qr_code": qr_code,
        "logos": logos,
        "icons": icons,
        "nfc_chip": nfc_chip
    }
