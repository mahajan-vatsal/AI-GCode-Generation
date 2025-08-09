# Updated generate_gcode.py as LangGraph-compatible node
from PIL import Image

def generate_scanline_gcode(
    bw_image_path,
    gcode_path,
    pixel_size_mm=0.1,
    feedrate=1000,
    laser_power=120,
    brightness_threshold=128
):
    img = Image.open(bw_image_path).convert('L')  # grayscale for brightness thresholding
    width, height = img.size

    gcode = []
    gcode.append("; Raster engraving from grayscale image")
    gcode.append("G90 ; Absolute positioning")
    gcode.append("G21 ; Units in mm")
    gcode.append(f"F{feedrate}")
    gcode.append("M5 ; Laser OFF")

    for row in range(height):
        y = pixel_size_mm * row
        img_row = height - 1 - row  # Flip Y-axis for correct bottom-up motion
        laser_on = False

        # Zig-zag motion
        cols = range(width) if row % 2 == 0 else range(width - 1, -1, -1)

        for col in cols:
            pixel_value = img.getpixel((col, img_row))
            x = pixel_size_mm * col

            if pixel_value < brightness_threshold:
                if not laser_on:
                    gcode.append(f"G0 X{x:.3f} Y{y:.3f}")
                    gcode.append(f"M3 S{laser_power}")
                    laser_on = True
                gcode.append(f"G1 X{x:.3f} Y{y:.3f}")
            else:
                if laser_on:
                    gcode.append("M5")
                    laser_on = False

        if laser_on:
            gcode.append("M5")

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

    gcode_text = generate_scanline_gcode(
        bw_image_path=bw_path,
        gcode_path=gcode_path,
        pixel_size_mm=0.1,
        feedrate=1200,
        laser_power=180,
        brightness_threshold=128
    )

    state["gcode_content"] = gcode_text
    return state
