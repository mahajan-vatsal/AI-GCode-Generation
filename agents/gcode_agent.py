# Updated generate_gcode.py as LangGraph-compatible node
from PIL import Image

def generate_scanline_gcode(
    bw_image_path,
    gcode_path,
    pixel_size_mm=0.1,
    feedrate=4000,
    laser_power=400,
    brightness_threshold=128,
    use_relative=False,             # NEW: enable G91-style relative positioning
    anchor=(0.0, 0.0),              # NEW: optional absolute anchor like Generate_gcode.py
):
    """
    If use_relative is True:
      - Header: G90 to anchor (if any), then switch to G91 (relative).
      - All subsequent G0/G1 moves are emitted as relative deltas but follow
        the exact same toolpath you already generate.
    If use_relative is False:
      - Behavior is unchanged from your original absolute-position generator.
    """
    img = Image.open(bw_image_path).convert('L')  # grayscale for brightness thresholding
    width, height = img.size

    gcode = []
    gcode.append("; Raster engraving from grayscale image")
    gcode.append("G90 ; Absolute positioning")
    gcode.append("G21 ; Units in mm")
    gcode.append(f"F{feedrate}")
    gcode.append("M5 ; Laser OFF")

    # Track the last absolute position we *intended* to be at (for relative deltas)
    last_pos = [0.0, 0.0]

    if use_relative:
        ax, ay = anchor
        # Move to anchor in absolute mode (like Generate_gcode.py), then switch to relative
        if abs(ax) > 1e-9 or abs(ay) > 1e-9:
            gcode.append(f"G1 X{ax:.3f} Y{ay:.3f} S0")
            last_pos = [ax, ay]
        else:
            last_pos = [0.0, 0.0]
        gcode.append("G91 ; Relative positioning")

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
            # Avoid emitting pure zero-delta moves
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
                    # Travel move to start of dark segment
                    emit_move(tx, ty, rapid=True)
                    gcode.append(f"M3 S{laser_power}")
                    laser_on = True
                # Cutting move along the same Y to current X
                emit_move(tx, ty, rapid=False)
            else:
                if laser_on:
                    gcode.append("M5")
                    laser_on = False

        if laser_on:
            gcode.append("M5")
            laser_on = False

    # Return to origin (keep original behavior)
    if use_relative:
        gcode.append("G90 ; Back to absolute for return")
    gcode.append("G0 X0 Y0 ; Return to origin")
    gcode.append("M2 ; End of program")

    with open(gcode_path, "w") as f:
        f.write("\n".join(gcode))

    print(f"✅ G-code successfully written to '{gcode_path}'.")
    return "\n".join(gcode)  # Return G-code as string


def gcode_generation_node(state):
    print(f"[gcode_generation_node] state keys: {list(state.keys())}")
    bw_path = state.get("bw_path")
    if not bw_path:
        raise ValueError("Missing 'bw_path' in state from rasterization step.")

    gcode_path = bw_path.replace("_bw.png", ".gcode")

    print(f"[gcode_generation_node] Using bw_path: {bw_path}")
    print(f"[gcode_generation_node] Output gcode_path: {gcode_path}")

    # NEW: optional controls from state (default keeps your old behavior)
    use_relative = bool(state.get("gcode_relative", False))
    anchor = state.get("gcode_anchor", (0.0, 0.0))
    if isinstance(anchor, (list, tuple)) and len(anchor) == 2:
        anchor = (float(anchor[0]), float(anchor[1]))
    else:
        anchor = (0.0, 0.0)

    gcode_text = generate_scanline_gcode(
        bw_image_path=bw_path,
        gcode_path=gcode_path,
        pixel_size_mm=0.1,
        feedrate=4000,
        laser_power=400,
        brightness_threshold=128,
        use_relative=use_relative,  # NEW
        anchor=anchor,              # NEW
    )

    state["gcode_content"] = gcode_text
    return state
