from langchain_core.tools import tool
import base64
from pathlib import Path
from io import BytesIO
import qrcode

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

    # Merge all layout items
    layout_items = text_blocks + logos + icons
    if user_override:
        layout_items += user_override

    for item in layout_items:
        x = item.get("x", 0)
        y = CARD_HEIGHT_MM - item.get("y", 0)
        width = item.get("width", 5)
        height = item.get("height", 5)

        if item["type"] in [
            "text", "name", "university", "designation",
            "Conference Name", "Conference Year", "Topic Name (for example ICPS)"
        ]:
            text = item.get("text", "")
            font_size = item.get("font_size", 10)
            font_family = item.get("font_family", "Arial")
            text_anchor = {
                "left": "start",
                "center": "middle",
                "right": "end"
            }.get(item.get("alignment", "left"), "start")
            font_weight = item.get("font_weight", "normal")

            svg_elements.append(
                f'<text x="{x}" y="{y}" font-size="{font_size}" '
                f'font-family="{font_family}" font-weight="{font_weight}" '
                f'text-anchor="{text_anchor}" dominant-baseline="text-before-edge" '
                f'fill="black">{text}</text>'
            )

        elif item["type"] in ["logo", "icon"]:
            label = item.get("label", "logo/icon")
            img_path = f"assets/{label.lower().replace(' ', '_')}.png"

            if Path(img_path).exists():
                b64_img = encode_image_to_base64(img_path)
                svg_elements.append(
                    f'<image href="data:image/png;base64,{b64_img}" '
                    f'x="{x}" y="{y - height}" width="{width}" height="{height}" />'
                )
            else:
                svg_elements.append(
                    f'<rect x="{x}" y="{y - height}" width="{width}" height="{height}" '
                    f'fill="none" stroke="black" stroke-dasharray="1"/>\n'
                    f'<text x="{x}" y="{y + 2}" font-size="2" fill="black">{label}</text>'
                )

    if qr_code:
        x = qr_code["x"]
        y = CARD_HEIGHT_MM - qr_code["y"]
        width = qr_code["width"]
        height = qr_code["height"]
        qr_data = qr_code.get("decoded_content")

        if qr_data:
            b64_qr = generate_qr_base64(qr_data)
            svg_elements.append(
                f'<image href="data:image/png;base64,{b64_qr}" '
                f'x="{x}" y="{y - height}" width="{width}" height="{height}" />'
            )
        else:
            svg_elements.append(
                f'<rect x="{x}" y="{y - height}" width="{width}" height="{height}" '
                f'fill="none" stroke="black" stroke-width="0.5"/>\n'
                f'<text x="{x}" y="{y + 2}" font-size="2.5" fill="black">QR</text>'
            )

    if nfc_chip:
        x = nfc_chip.get("x", 0)
        y = CARD_HEIGHT_MM - nfc_chip.get("y", 0)
        width = nfc_chip.get("width", 5)
        height = nfc_chip.get("height", 5)

        img_path = "assets/nfc_templates/nfc_chip2.png"
        if Path(img_path).exists():
            b64_nfc = encode_image_to_base64(img_path)
            svg_elements.append(
                f'<image href="data:image/png;base64,{b64_nfc}" '
                f'x="{x}" y="{y - height}" width="{width}" height="{height}" />'
            )
        else:
            print(f"⚠️ NFC image not found at {img_path}")
            svg_elements.append(
                f'<rect x="{x}" y="{y - height}" width="{width}" height="{height}" '
                f'fill="none" stroke="blue" stroke-width="0.5"/>\n'
                f'<text x="{x}" y="{y + 2}" font-size="2.5" fill="blue">NFC</text>'
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
        "svg_path": svg_output_path  # ✅ Fix for KeyError
    }
