import xml.etree.ElementTree as ET
import re
from pathlib import Path
import os

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)
NS = {"svg": SVG_NS, "xlink": XLINK_NS}

# Keep CANVAS_HEIGHT consistent with mapper (bottom-left origin for API)
CANVAS_HEIGHT = 54.0  # mm

def to_svg_y(y_bottom_left: float) -> float:
    """Convert bottom-left y to SVG top-left y."""
    return CANVAS_HEIGHT - y_bottom_left

def dy_to_svg(dy_bottom_left: float) -> float:
    """Convert bottom-left dy to SVG dy (sign flip)."""
    return -dy_bottom_left

# Allow typical XML id characters: letters, digits, _, -, :, .
ID = r"([A-Za-z_][A-Za-z0-9_\-:.]*)"

# Accept move_by with optional dy (defaults to 0)
MOVE_BY_REGEX = rf"move_by\s+{ID}\s+dx=([-+]?\d*\.?\d+)(?:\s+dy=([-+]?\d*\.?\d+))?"
# Absolute move
MOVE_REGEX    = rf"move\s+{ID}\s+to\s+x=([-+]?\d*\.?\d+)\s+y=([-+]?\d*\.?\d+)"
# NEW: absolute resize (in mm)
RESIZE_REGEX  = rf"resize\s+{ID}\s+to\s+width=([-+]?\d*\.?\d+)\s+height=([-+]?\d*\.?\d+)"
# NEW: relative scale (uniform: s=..., or non-uniform: sx=... sy=...)
SCALE_BY_UNI  = rf"scale_by\s+{ID}\s+s=([-+]?\d*\.?\d+)"
SCALE_BY_BI   = rf"scale_by\s+{ID}\s+sx=([-+]?\d*\.?\d+)\s+sy=([-+]?\d*\.?\d+)"
REPLACE_REGEX = rf"replace\s+{ID}\s+(?:with\s+)?['\"](.+?)['\"]"
DELETE_REGEX  = rf"delete\s+{ID}"
_VERSION_RE   = re.compile(r"^(?P<stem>.*?)(?:_v(?P<n>\d{3}))?\.svg$", re.I)

def parse_commands(commands_str: str):
    commands = []
    for line in commands_str.strip().splitlines():
        line = line.strip("`- ").strip()
        if not line:
            continue

        m = re.match(MOVE_BY_REGEX, line, re.I)
        if m:
            dx = float(m.group(2))
            dy = float(m.group(3)) if m.group(3) is not None else 0.0  # default dy
            commands.append({"action": "move_by", "id": m.group(1), "dx": dx, "dy": dy})
            continue

        m = re.match(MOVE_REGEX, line, re.I)
        if m:
            commands.append({"action": "move", "id": m.group(1), "x": float(m.group(2)), "y": float(m.group(3))})
            continue

        # NEW: resize absolute
        m = re.match(RESIZE_REGEX, line, re.I)
        if m:
            commands.append({"action": "resize", "id": m.group(1), "width": float(m.group(2)), "height": float(m.group(3))})
            continue

        # NEW: scale_by uniform
        m = re.match(SCALE_BY_UNI, line, re.I)
        if m:
            s = float(m.group(2))
            commands.append({"action": "scale_by", "id": m.group(1), "sx": s, "sy": s})
            continue

        # NEW: scale_by non-uniform
        m = re.match(SCALE_BY_BI, line, re.I)
        if m:
            commands.append({"action": "scale_by", "id": m.group(1), "sx": float(m.group(2)), "sy": float(m.group(3))})
            continue

        m = re.match(DELETE_REGEX, line, re.I)
        if m:
            commands.append({"action": "delete", "id": m.group(1)})
            continue

        m = re.match(REPLACE_REGEX, line, re.I)
        if m:
            commands.append({"action": "replace", "id": m.group(1), "content": m.group(2)})
            continue

        print(f"⚠️ Warning: Could not parse command line: {line}")
    return commands

def normalize_commands(commands):
    """
    Additive safety: if both 'delete' and 'replace' exist for the same element id
    in one batch, skip the 'delete' so 'replace' can succeed. No change to other logic.
    """
    ids_with_replace = {c["id"] for c in commands if c["action"] == "replace"}
    if not ids_with_replace:
        return commands
    normalized = []
    for c in commands:
        if c["action"] == "delete" and c["id"] in ids_with_replace:
            print(f"ℹ️ Skipping delete for '{c['id']}' because a replace is present in this batch.")
            continue
        normalized.append(c)
    return normalized


def apply_edit_commands_to_svg(svg_input_path, commands_str, svg_output_path):
    commands = parse_commands(commands_str)
    if not commands:
        raise ValueError(f"No commands recognized by parser. Raw:\n{commands_str}")

    commands = normalize_commands(commands)

    tree = ET.parse(svg_input_path)
    root = tree.getroot()

    def first_float(val):
        if val is None or val == "":
            return 0.0
        return float(str(val).split()[0])

    for cmd in commands:
        elem_id = cmd["id"]
        # Attribute match doesn't need explicit NS
        elem = root.find(f".//*[@id='{elem_id}']")
        if elem is None:
            print(f"⚠️ Element with id '{elem_id}' not found.")
            continue

        tag = elem.tag.split("}")[-1]

        if cmd["action"] == "move_by":
            if tag in ["text", "image"]:
                cur_x = first_float(elem.get("x"))
                cur_y = first_float(elem.get("y"))
                new_x = cur_x + cmd["dx"]
                new_y = cur_y + dy_to_svg(cmd["dy"])
                elem.set("x", str(new_x))
                elem.set("y", str(new_y))
            else:
                prev = (elem.get("transform") or "").strip()
                dx = cmd["dx"]
                dy = dy_to_svg(cmd["dy"])
                elem.set("transform", f"{prev} translate({dx} {dy})".strip())
            print(f"✅ Moved '{elem_id}' by dx={cmd['dx']}, dy={cmd['dy']} (bottom-left dy)")

        elif cmd["action"] == "move":
            if tag in ["text", "image"]:
                elem.set("x", str(cmd["x"]))
                elem.set("y", str(to_svg_y(cmd["y"])))
                print(f"✅ Moved '{elem_id}' to x={cmd['x']}, y={cmd['y']} (bottom-left)")
            else:
                prev = (elem.get("transform") or "").strip()
                elem.set("transform", f"{prev} translate({cmd['x']} {to_svg_y(cmd['y'])})".strip())
                print(f"✅ Applied translate({cmd['x']} {to_svg_y(cmd['y'])}) to '{elem_id}' (best-effort)")

        # NEW: absolute resize (mm). Keeps current x/y (top-left anchor for images).
        elif cmd["action"] == "resize":
            w = cmd["width"]
            h = cmd["height"]
            if tag == "image":
                elem.set("width", str(w))
                elem.set("height", str(h))
                print(f"✅ Resized image '{elem_id}' to width={w}, height={h}")
            elif tag == "g":
                # Try to resize common children (image/rect) inside the group
                resized = False
                for child in list(elem):
                    ctag = child.tag.split("}")[-1]
                    if ctag in ("image", "rect"):
                        child.set("width", str(w))
                        child.set("height", str(h))
                        resized = True
                if resized:
                    print(f"✅ Resized group '{elem_id}' children to width={w}, height={h}")
                else:
                    print(f"⚠️ Resize for group '{elem_id}' had no resizable children")
            else:
                print(f"⚠️ Resize not supported for tag '{tag}' (id='{elem_id}')")

        # NEW: relative scale. For images: multiply width/height. For groups: append scale().
        elif cmd["action"] == "scale_by":
            sx = cmd["sx"]
            sy = cmd["sy"]
            if tag == "image":
                cur_w = first_float(elem.get("width"))
                cur_h = first_float(elem.get("height"))
                elem.set("width", str(cur_w * sx))
                elem.set("height", str(cur_h * sy))
                print(f"✅ Scaled image '{elem_id}' by sx={sx}, sy={sy}")
            elif tag == "g":
                prev = (elem.get("transform") or "").strip()
                elem.set("transform", f"{prev} scale({sx} {sy})".strip())
                print(f"✅ Applied scale({sx} {sy}) to group '{elem_id}'")
            else:
                print(f"⚠️ scale_by not supported for tag '{tag}' (id='{elem_id}')")

        elif cmd["action"] == "delete":
            parent = root.find(f".//*[@id='{elem_id}']/..")
            if parent is not None:
                parent.remove(elem)
                print(f"✅ Deleted element '{elem_id}'")
            else:
                print(f"⚠️ Could not find parent to delete element '{elem_id}'")

        elif cmd["action"] == "replace":
            if tag == "text":
                elem.text = cmd["content"]
                print(f"✅ Replaced text in '{elem_id}' with '{cmd['content']}'")
            elif tag == "image":
                elem.set(f"{{{XLINK_NS}}}href", cmd["content"])
                print(f"✅ Replaced image href in '{elem_id}' with '{cmd['content']}'")
            else:
                print(f"⚠️ Replace not supported for tag '{tag}'")

    tree.write(svg_output_path, encoding="utf-8", xml_declaration=True)
    print(f"\n✅ Edited SVG saved as: {svg_output_path}")

def extract_valid_commands(command_str):
    valid = []
    for line in command_str.strip().splitlines():
        line = line.strip("`- ").strip()
        if line.lower().startswith(("move_by", "move", "delete", "replace", "resize", "scale_by")):
            valid.append(line)
    return "\n".join(valid)

def next_version_path(current_svg_path: str) -> str:
    p = Path(current_svg_path)
    m = _VERSION_RE.match(p.name)
    if not m:
        return str(p.with_name(p.stem + "_v002.svg"))
    stem = m.group("stem") or p.stem
    n = int(m.group("n")) + 1 if m.group("n") else 2
    return str(p.with_name(f"{stem}_v{n:03d}.svg"))

def svg_editor_node(state):
    print("State keys:", state.keys())
    print("svg_id_patched_path:", state.get("svg_id_patched_path"))
    print("svg_path:", state.get("svg_path"))
    print("edit_commands:", state.get("edit_commands"))

    input_path = state.get("svg_id_patched_path") or state.get("svg_path")
    if not input_path:
        raise ValueError("Missing 'svg_id_patched_path' or 'svg_path' in state.")
    if not os.path.exists(input_path):
        print(f"⚠️ Patched SVG not found at {input_path}; falling back to original svg_path.")
        input_path = state.get("svg_path")
    if not input_path or not os.path.exists(input_path):
        raise FileNotFoundError(f"SVG not found at {input_path}")

    commands = state.get("edit_commands")
    if not commands:
        raise ValueError("Missing 'edit_commands' in state.")

    commands = extract_valid_commands(commands)
    if not commands.strip():
        raise ValueError("No valid edit commands parsed from LLM output.")

    base_for_version = state.get("svg_path") or input_path
    output_path = next_version_path(base_for_version)

    apply_edit_commands_to_svg(input_path, commands, output_path)

    with open(output_path, "r", encoding="utf-8") as f:
        state["svg_content"] = f.read()

    state["svg_path"] = output_path
    state["svg_history"] = (state.get("svg_history") or []) + [state["svg_path"]]
    state["svg_version"] = (state.get("svg_version") or 1) + 1
    state["svg_id_patched_path"] = None
    return state
