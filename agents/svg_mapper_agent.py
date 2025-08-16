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
    # y is bottom-left origin here
    if y > 2 * height / 3:
        vert = "top"
    elif y < 1 * height / 3:
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
        return float(re.sub(r"[A-Za-z%]+$", "", str(s)).strip())
    except Exception:
        return default

def _get_root_scale(root):
    vb = root.attrib.get("viewBox")
    if vb:
        parts = [float(v) for v in vb.replace(",", " ").split()]
        if len(parts) == 4:
            minx, miny, vw, vh = parts
            sx = CANVAS_WIDTH / vw if vw else 1.0
            sy = CANVAS_HEIGHT / vh if vh else 1.0
            return (minx, miny, sx, sy)
    # Fallback ~96dpi
    px_to_mm = 0.264583
    return (0.0, 0.0, px_to_mm, px_to_mm)

_TRANSLATE_RE = re.compile(
    r"translate\(\s*([-+]?\d*\.?\d+)(?:[ ,]\s*([-+]?\d*\.?\d+))?\s*\)",
    re.I
)

def _accumulate_translate(elem, parent_map):
    tx = 0.0
    ty = 0.0
    cur = elem
    steps = 0
    while cur is not None and steps < 512:
        tr = cur.attrib.get("transform", "")
        m = _TRANSLATE_RE.search(tr)
        if m:
            tx += float(m.group(1))
            ty += float(m.group(2) or 0.0)
        cur = parent_map.get(cur)
        steps += 1
    return tx, ty

def _infer_role_from_all(elem_type: str, elem_id: str, content: str, w: float, h: float, role_attr: str):
    if role_attr:
        return role_attr.lower()

    name = (content or "").lower()
    idname = (elem_id or "").lower()

    # Strong signals
    if "nfc" in idname or "nfc" in name:
        return "nfc"
    if "qr" in idname or "qr" in name or abs(w - h) < 2.0:
        return "qr"
    if elem_type == "image":
        return "logo"
    return "text"

def _content_pretty(img_elem, href, default="embedded-image"):
    # Prefer data-name if present (so base64 images still show a meaningful name)
    dn = img_elem.attrib.get("data-name")
    if dn:
        return os.path.basename(dn)
    if href and not str(href).startswith("data:"):
        return os.path.basename(href)
    return default

def parse_svg_semantic(svg_path: str, save_id_patched_svg: bool = False):
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    tree = ET.parse(svg_path)
    root = tree.getroot()
    ns = {"svg": SVG_NS, "xlink": XLINK_NS}

    parent_map = {c: p for p in tree.iter() for c in p}
    minx, miny, sx, sy = _get_root_scale(root)

    items = []
    text_counter = 0
    image_counter = 0

    # TEXT
    for txt in root.findall(".//svg:text", ns):
        x_local = _parse_float(txt.attrib.get("x"), 0.0)
        y_local = _parse_float(txt.attrib.get("y"), 0.0)
        tx, ty = _accumulate_translate(txt, parent_map)
        x_doc = (x_local + tx - minx) * sx
        y_doc = (y_local + ty - miny) * sy
        y_bottom = CANVAS_HEIGHT - y_doc

        elem_id = txt.attrib.get("id")
        if elem_id is None:
            elem_id = f"text_{text_counter}"
            txt.set("id", elem_id)
            text_counter += 1

        content = (txt.text or "").strip()
        role_attr = txt.attrib.get("data-role", None)
        role = _infer_role_from_all("text", elem_id, content, 0.0, 0.0, role_attr)

        items.append({
            "id": elem_id,
            "type": "text",
            "content": content,
            "x": round(x_doc, 3),
            "y": round(y_bottom, 3),
            "width": None,
            "height": None,
            "role": role,
            "position": describe_position(x_doc, y_bottom)
        })

    # IMAGE
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
        elem_id = img.attrib.get("id")
        if elem_id is None:
            elem_id = f"image_{image_counter}"
            img.set("id", elem_id)
            image_counter += 1

        content = _content_pretty(img, href)
        role_attr = img.attrib.get("data-role", None)
        role = _infer_role_from_all("image", elem_id, content, w_doc, h_doc, role_attr)

        items.append({
            "id": elem_id,
            "type": "image",
            "content": content,
            "x": round(x_doc, 3),
            "y": round(y_bottom, 3),
            "width": round(w_doc, 3),
            "height": round(h_doc, 3),
            "role": role,
            "position": describe_position(x_doc, y_bottom)
        })

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
