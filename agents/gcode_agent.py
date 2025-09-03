# gcode_agent.py
# Updated generate_gcode.py as LangGraph-compatible node
from PIL import Image
from pathlib import Path

def generate_scanline_gcode(
    bw_image_path,
    gcode_path,
    pixel_size_mm=0.1,
    feedrate=4000,
    laser_power=400,
    brightness_threshold=128,
    use_relative=False,             # Enable G91-style relative positioning
    anchor=(0.0, 0.0),              # Anchor like Generate_gcode.py
):
    """
    If use_relative is True:
      - Header: start in G91 (relative) immediately (no G90 line).
      - If anchor != (0,0): do a relative move to that anchor (G1 Xax Yay S0).
      - Subsequent moves are emitted as relative deltas (same path as before).

    If use_relative is False:
      - Same as before: start in absolute (G90) and emit absolute X/Y.
    """
    img = Image.open(bw_image_path).convert('L')
    width, height = img.size

    gcode = []
    gcode.append("; Raster engraving from grayscale image")
    gcode.append("G21 ; Units in mm")
    gcode.append(f"F{feedrate}")
    gcode.append("M5 ; Laser OFF")

    # Track the last absolute position we *intend* (used to compute deltas in relative mode)
    last_pos = [0.0, 0.0]

    if use_relative:
        # Start directly in relative mode (requested change)
        gcode.append("G91 ; Relative positioning")
        ax, ay = anchor
        if abs(ax) > 1e-9 or abs(ay) > 1e-9:
            # Make the initial anchor move as a *relative* move
            gcode.append(f"G1 X{ax:.3f} Y{ay:.3f} S0")
            last_pos = [ax, ay]
        else:
            last_pos = [0.0, 0.0]
    else:
        # Original behavior
        gcode.append("G90 ; Absolute positioning")

    def emit_move(x_abs, y_abs, rapid=False):
        """
        Emit a move to absolute target (x_abs, y_abs), but:
          - in absolute mode: write absolute X/Y
          - in relative mode: write deltas (dx, dy) from last_pos and update last_pos
        """
        nonlocal last_pos
        code = "G0" if rapid else "G1"

        if use_relative:
            dx = x_abs - last_pos[0]
            dy = y_abs - last_pos[1]
            if abs(dx) > 1e-9 or abs(dy) > 1e-9:
                gcode.append(f"{code} X{dx:.3f} Y{dy:.3f}")
                last_pos[0] = x_abs
                last_pos[1] = y_abs
        else:
            gcode.append(f"{code} X{x_abs:.3f} Y{y_abs:.3f}")
            last_pos[0] = x_abs
            last_pos[1] = y_abs

    # Helper to optionally offset absolute coordinates by anchor when in relative mode
    def with_anchor(x, y):
        if use_relative:
            return (anchor[0] + x, anchor[1] + y)
        return (x, y)

    for row in range(height):
        y = pixel_size_mm * row
        img_row = height - 1 - row  # Flip Y-axis for correct bottom-up motion
        laser_on = False

        # Zig-zag motion
        cols = range(width) if row % 2 == 0 else range(width - 1, -1, -1)

        for col in cols:
            pixel_value = img.getpixel((col, img_row))
            x = pixel_size_mm * col

            tx, ty = with_anchor(x, y)

            if pixel_value < brightness_threshold:
                if not laser_on:
                    emit_move(tx, ty, rapid=True)
                    gcode.append(f"M3 S{laser_power}")
                    laser_on = True
                emit_move(tx, ty, rapid=False)
            else:
                if laser_on:
                    gcode.append("M5")
                    laser_on = False

        if laser_on:
            gcode.append("M5")
            laser_on = False

    # Return to origin (unchanged)
    if use_relative:
        gcode.append("G90 ; Back to absolute for return")
    gcode.append("G0 X0 Y0 ; Return to origin")
    gcode.append("M2 ; End of program")

    # Ensure output directory exists
    out_path = Path(gcode_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(gcode))

    print(f"✅ G-code successfully written to '{out_path}'.")
    return "\n".join(gcode)


def gcode_generation_node(state):
    print(f"[gcode_generation_node] state keys: {list(state.keys())}")
    bw_path = state.get("bw_path")
    if not bw_path:
        raise ValueError("Missing 'bw_path' in state from rasterization step.")

    bw_p = Path(bw_path)
    parent = bw_p.parent if bw_p.parent.as_posix() not in ("", ".") else Path(".")

    # Derive a stable .gcode name next to the BW image
    name = bw_p.name
    if name.endswith("_bw.png"):
        out_name = name.replace("_bw.png", ".gcode")
    else:
        out_name = bw_p.stem + ".gcode"

    gcode_path = parent / out_name

    print(f"[gcode_generation_node] Using bw_path: {bw_path}")
    print(f"[gcode_generation_node] Output gcode_path: {gcode_path}")

    # Optional controls from state
    use_relative = bool(state.get("gcode_relative", False))
    anchor = state.get("gcode_anchor", (0.0, 0.0))
    if isinstance(anchor, (list, tuple)) and len(anchor) == 2:
        anchor = (float(anchor[0]), float(anchor[1]))
    else:
        anchor = (0.0, 0.0)

    gcode_text = generate_scanline_gcode(
        bw_image_path=str(bw_p),
        gcode_path=str(gcode_path),
        pixel_size_mm=0.1,
        feedrate=4000,
        laser_power=400,
        brightness_threshold=128,
        use_relative=use_relative,  # Start directly in G91 if True
        anchor=anchor,
    )

    state["gcode_content"] = gcode_text
    state["gcode_path"] = str(gcode_path)
    state["gcode_output_path"] = str(gcode_path)
    return state
