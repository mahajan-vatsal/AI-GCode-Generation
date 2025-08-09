import xml.etree.ElementTree as ET
import os

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

CANVAS_WIDTH = 85.0   # mm
CANVAS_HEIGHT = 54.0  # mm

def describe_position(x: float, y: float,
                      width: float = CANVAS_WIDTH,
                      height: float = CANVAS_HEIGHT) -> str:
    if y > 2 * height / 3:
        vert = "top"
    elif y < height / 3:
        vert = "bottom"
    else:
        vert = "center"
    if x < width / 3:
        hori = "left"
    elif x > 2 * width / 3:
        hori = "right"
    else:
        hori = "center"
    return f"{vert}-{hori}"

def parse_svg_semantic(svg_path: str, save_id_patched_svg: bool = False):  # MODIFIED
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    tree = ET.parse(svg_path)
    root = tree.getroot()
    ns = {"svg": SVG_NS, "xlink": XLINK_NS}

    items = []
    text_counter = 0
    image_counter = 0

    for txt in root.findall(".//svg:text", ns):
        x = float(txt.attrib.get("x", 0))
        y_svg = float(txt.attrib.get("y", 0))
        y = CANVAS_HEIGHT - y_svg
        content = (txt.text or "").strip()
        elem_id = txt.attrib.get("id", None)
        if elem_id is None:
            elem_id = f"text_{text_counter}"
            txt.set("id", elem_id)  # NEW: assign ID in XML tree
            text_counter += 1
        pos_label = describe_position(x, y)
        items.append({
            "id": elem_id,
            "type": "text",
            "content": content,
            "x": x,
            "y": y,
            "position": pos_label
        })

    for img in root.findall(".//svg:image", ns):
        x = float(img.attrib.get("x", 0))
        y_svg = float(img.attrib.get("y", 0))
        y = CANVAS_HEIGHT - y_svg
        href = img.attrib.get(f"{{{XLINK_NS}}}href", img.attrib.get("href", ""))
        content = "embedded-image" if href.startswith("data:") else os.path.basename(href)
        elem_id = img.attrib.get("id", None)
        if elem_id is None:
            elem_id = f"image_{image_counter}"
            img.set("id", elem_id)  # NEW: assign ID in XML tree
            image_counter += 1
        pos_label = describe_position(x, y)
        items.append({
            "id": elem_id,
            "type": "image",
            "content": content,
            "x": x,
            "y": y,
            "position": pos_label
        })

    # NEW: Optional save of ID-patched SVG
    output_path = None
    if save_id_patched_svg:
        output_path = os.path.splitext(svg_path)[0] + "_with_ids.svg"
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        print(f"[INFO] ID-patched SVG saved to: {output_path}")

    return items, output_path

def svg_semantic_mapper_node(state):
    svg_path = state["svg_path"]
    elements, output_path = parse_svg_semantic(svg_path, save_id_patched_svg=True)
    state["svg_elements"] = elements
    state["svg_id_patched_path"] = output_path
    return state
