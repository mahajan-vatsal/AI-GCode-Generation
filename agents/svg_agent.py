from langchain_core.tools import tool
import base64
from pathlib import Path
from io import BytesIO
import qrcode
import re

SVG_HEADER = '''<svg xmlns="http://www.w3.org/2000/svg" width="85mm" height="54mm" viewBox="0 0 85 54" version="1.1">'''
CARD_HEIGHT_MM = 54.0  # used for flipping Y-axis

def encode_image_to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def generate_qr_base64(qr_data: str) -> str:
    qr = qrcode.QRCode(box_size=10, border=0)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def _slug(s: str, fallback: str) -> str:
    if not s:
        return fallback
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9_\-:.]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or fallback

def _xml_escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

@tool(description="Generate SVG content from layout elements.")
def generate_svg_from_layout(
    text_blocks: list,
    qr_code: dict = None,
    nfc_chip: dict = None,
    logos: list = [],
    icons: list = [],
    user_override: list = []
) -> dict:
    """
    Generate an SVG string from layout elements.
    Positions must be in millimeters (origin: bottom-left).
    """

    svg_elements = []
    # Stable counters for deterministic IDs
    text_idx = 0
    logo_idx = 0
    icon_idx = 0

    # Merge all layout items (excluding QR/NFC which we render explicitly)
    layout_items = list(text_blocks) + list(logos) + list(icons)
    if user_override:
        layout_items += user_override

    for item in layout_items:
        x = item.get("x", 0.0)
        y = CARD_HEIGHT_MM - item.get("y", 0.0)  # convert to SVG top-left
        width = item.get("width", 5.0)
        height = item.get("height", 5.0)
        align = item.get("alignment", "left")
        font_weight = item.get("font_weight", "normal")

        if item["type"] in [
            "text", "name", "university", "designation",
            "Conference Name", "Conference Year", "Topic Name (for example ICPS)"
        ]:
            text = _xml_escape(item.get("text", ""))
            font_size = item.get("font_size", 10.0)
            font_family = item.get("font_family", "Arial")
            text_anchor = {"left": "start", "center": "middle", "right": "end"}.get(align, "start")
            elem_id = f"text_{text_idx}"
            text_idx += 1

            svg_elements.append(
                f'<text id="{elem_id}" x="{x}" y="{y}" font-size="{font_size}" '
                f'font-family="{font_family}" font-weight="{font_weight}" '
                f'text-anchor="{text_anchor}" dominant-baseline="text-before-edge" '
                f'fill="black" data-role="text">{text}</text>'
            )

        elif item["type"] == "logo":
            label = item.get("label") or item.get("text") or "logo"
            slug = _slug(label, f"logo{logo_idx}")
            elem_id = f"logo_{slug}"
            logo_idx += 1
            # Try asset path, else draw placeholder
            img_path = f"assets/{slug}.png"
            if Path(img_path).exists():
                b64_img = encode_image_to_base64(img_path)
                svg_elements.append(
                    f'<image id="{elem_id}" data-role="logo" data-name="{slug}.png" '
                    f'href="data:image/png;base64,{b64_img}" x="{x}" y="{y - height}" width="{width}" height="{height}" />'
                )
            else:
                svg_elements.append(
                    f'<g id="{elem_id}" data-role="logo" data-name="{slug}.png">'
                    f'<rect x="{x}" y="{y - height}" width="{width}" height="{height}" '
                    f'fill="none" stroke="black" stroke-dasharray="1"/>'
                    f'<text x="{x}" y="{y + 2}" font-size="2" fill="black">{_xml_escape(label)}</text>'
                    f'</g>'
                )

        elif item["type"] in ["icon", "emoji"]:
            label = item.get("label") or item.get("text") or "icon"
            slug = _slug(label, f"icon{icon_idx}")
            elem_id = f"icon_{slug}"
            icon_idx += 1
            img_path = f"assets/{slug}.png"
            if Path(img_path).exists():
                b64_img = encode_image_to_base64(img_path)
                svg_elements.append(
                    f'<image id="{elem_id}" data-role="icon" data-name="{slug}.png" '
                    f'href="data:image/png;base64,{b64_img}" x="{x}" y="{y - height}" width="{width}" height="{height}" />'
                )
            else:
                svg_elements.append(
                    f'<g id="{elem_id}" data-role="icon" data-name="{slug}.png">'
                    f'<rect x="{x}" y="{y - height}" width="{width}" height="{height}" '
                    f'fill="none" stroke="black" stroke-dasharray="1"/>'
                    f'<text x="{x}" y="{y + 2}" font-size="2" fill="black">{_xml_escape(label)}</text>'
                    f'</g>'
                )

    # QR (explicit)
    if qr_code:
        x = qr_code["x"]
        y = CARD_HEIGHT_MM - qr_code["y"]
        width = qr_code["width"]
        height = qr_code["height"]
        qr_data = qr_code.get("decoded_content")
        elem_id = "qr_1"
        if qr_data:
            b64_qr = generate_qr_base64(qr_data)
            svg_elements.append(
                f'<image id="{elem_id}" data-role="qr" data-name="qr.png" '
                f'href="data:image/png;base64,{b64_qr}" x="{x}" y="{y - height}" width="{width}" height="{height}" />'
            )
        else:
            svg_elements.append(
                f'<g id="{elem_id}" data-role="qr" data-name="qr.png">'
                f'<rect x="{x}" y="{y - height}" width="{width}" height="{height}" '
                f'fill="none" stroke="black" stroke-width="0.5"/>'
                f'<text x="{x}" y="{y + 2}" font-size="2.5" fill="black">QR</text>'
                f'</g>'
            )

    # NFC (explicit)
    if nfc_chip:
        x = nfc_chip.get("x", 0.0)
        y = CARD_HEIGHT_MM - nfc_chip.get("y", 0.0)
        width = nfc_chip.get("width", 5.0)
        height = nfc_chip.get("height", 5.0)

        img_path = "assets/nfc_templates/nfc_chip2.png"
        elem_id = "nfc_1"
        if Path(img_path).exists():
            b64_nfc = encode_image_to_base64(img_path)
            svg_elements.append(
                f'<image id="{elem_id}" data-role="nfc" data-name="nfc_chip2.png" '
                f'href="data:image/png;base64,{b64_nfc}" x="{x}" y="{y - height}" width="{width}" height="{height}" />'
            )
        else:
            print(f"⚠️ NFC image not found at {img_path}")
            svg_elements.append(
                f'<g id="{elem_id}" data-role="nfc" data-name="nfc_chip2.png">'
                f'<rect x="{x}" y="{y - height}" width="{width}" height="{height}" '
                f'fill="none" stroke="blue" stroke-width="0.5"/>'
                f'<text x="{x}" y="{y + 2}" font-size="2.5" fill="blue">NFC</text>'
                f'</g>'
            )

    # Wrap elements directly — no global flipping
    svg_content = f"""{SVG_HEADER}
{'\n'.join(svg_elements)}
</svg>"""

    svg_output_path = "output.svg"
    with open(svg_output_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print(f"📄 SVG saved to {svg_output_path}")

    return {
        "svg_content": svg_content,
        "svg_path": svg_output_path
    }
