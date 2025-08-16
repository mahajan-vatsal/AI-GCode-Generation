import xml.etree.ElementTree as ET
import os
import re

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

CANVAS_WIDTH = 85.0   # mm
CANVAS_HEIGHT = 54.0  # mm

def describe_position(x: float, y: float,
                      width: float = CANVAS_WIDTH,
                      height: float = CANVAS_HEIGHT) -> str:
    # y is in bottom-left origin here
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

def _parse_float(s, default=0.0):
    if s is None:
        return default
    try:
        # remove any unit suffix like "px", "mm", etc.
        return float(re.sub(r"[A-Za-z%]+$", "", str(s)).strip())
    except Exception:
        return default

def _get_root_scale(root):
    """
    Returns (minx, miny, sx, sy) to map document coords into CANVAS_* space.
    If viewBox exists, use it; else fall back to approximate px->mm scale (96dpi).
    """
    vb = root.attrib.get("viewBox")
    if vb:
        parts = [float(v) for v in vb.replace(",", " ").split()]
        if len(parts) == 4:
            minx, miny, vw, vh = parts
            sx = CANVAS_WIDTH / vw if vw else 1.0
            sy = CANVAS_HEIGHT / vh if vh else 1.0
            return (minx, miny, sx, sy)
    # Fallback heuristic: many tools assume 96 px per inch => 1px ≈ 0.264583 mm
    px_to_mm = 0.264583
    return (0.0, 0.0, px_to_mm, px_to_mm)

_TRANSLATE_RE = re.compile(
    r"translate\(\s*([-+]?\d*\.?\d+)(?:[ ,]\s*([-+]?\d*\.?\d+))?\s*\)",
    re.I
)

def _accumulate_translate(elem, parent_map):
    """
    Sum only translate(tx, ty) from this element up through ancestors.
    xml.etree doesn't have getparent natively, so we use a parent_map.
    """
    tx = 0.0
    ty = 0.0
    cur = elem
    visited = 0
    while cur is not None and visited < 512:
        tr = cur.attrib.get("transform", "")
        m = _TRANSLATE_RE.search(tr)
        if m:
            tx += float(m.group(1))
            ty += float(m.group(2) or 0.0)
        cur = parent_map.get(cur)
        visited += 1
    return tx, ty

def _infer_role(elem_type: str, content: str, w: float, h: float):
    name = (content or "").lower()
    if "qr" in name or abs(w - h) < 2.0:  # square-ish
        return "qr"
    if "nfc" in name or "rfid" in name:
        return "nfc"
    if elem_type == "image":
        return "logo"
    return "text"

def parse_svg_semantic(svg_path: str, save_id_patched_svg: bool = False):
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    tree = ET.parse(svg_path)
    root = tree.getroot()
    ns = {"svg": SVG_NS, "xlink": XLINK_NS}

    # Build a parent map so we can walk ancestors
    parent_map = {c: p for p in tree.iter() for c in p}

    minx, miny, sx, sy = _get_root_scale(root)

    items = []
    text_counter = 0
    image_counter = 0

    # ---- TEXT ----
    for txt in root.findall(".//svg:text", ns):
        # Local attributes
        x_local = _parse_float(txt.attrib.get("x"), 0.0)
        y_local = _parse_float(txt.attrib.get("y"), 0.0)

        # Accumulate parent translate
        tx, ty = _accumulate_translate(txt, parent_map)

        # Map to viewBox-adjusted space
        x_doc = (x_local + tx - minx) * sx
        y_doc = (y_local + ty - miny) * sy  # still SVG top-left

        # Convert to bottom-left for the LLM
        y_bottom = CANVAS_HEIGHT - y_doc

        content = (txt.text or "").strip()
        elem_id = txt.attrib.get("id")
        if elem_id is None:
            elem_id = f"text_{text_counter}"
            txt.set("id", elem_id)
            text_counter += 1

        pos_label = describe_position(x_doc, y_bottom)
        items.append({
            "id": elem_id,
            "type": "text",
            "content": content,
            "x": round(x_doc, 3),
            "y": round(y_bottom, 3),
            "width": None,
            "height": None,
            "role": _infer_role("text", content, 0.0, 0.0),
            "position": pos_label
        })

    # ---- IMAGE ----
    for img in root.findall(".//svg:image", ns):
        x_local = _parse_float(img.attrib.get("x"), 0.0)
        y_local = _parse_float(img.attrib.get("y"), 0.0)
        w_local = _parse_float(img.attrib.get("width"), 0.0)
        h_local = _parse_float(img.attrib.get("height"), 0.0)

        tx, ty = _accumulate_translate(img, parent_map)

        x_doc = (x_local + tx - minx) * sx
        y_doc = (y_local + ty - miny) * sy
        w_doc = w_local * sx
        h_doc = h_local * sy

        y_bottom = CANVAS_HEIGHT - y_doc

        href = img.attrib.get(f"{{{XLINK_NS}}}href", img.attrib.get("href", ""))
        content = "embedded-image" if href.startswith("data:") else os.path.basename(href)

        elem_id = img.attrib.get("id")
        if elem_id is None:
            elem_id = f"image_{image_counter}"
            img.set("id", elem_id)
            image_counter += 1

        pos_label = describe_position(x_doc, y_bottom)
        items.append({
            "id": elem_id,
            "type": "image",
            "content": content,
            "x": round(x_doc, 3),
            "y": round(y_bottom, 3),
            "width": round(w_doc, 3),
            "height": round(h_doc, 3),
            "role": _infer_role("image", content, w_doc, h_doc),
            "position": pos_label
        })

    # Optional save of ID-patched SVG
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
