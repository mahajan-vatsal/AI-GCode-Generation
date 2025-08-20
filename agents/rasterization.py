from PIL import Image
import cairosvg
from typing import TypedDict

class WorkflowState(TypedDict, total=False):
    svg_content: str
    svg_path: str
    png_path: str
    bw_path: str

def svg_to_png(svg_path, png_path, dpi=254):
    with open(svg_path, 'rb') as svg_file:
        svg_data = svg_file.read()
    cairosvg.svg2png(
        bytestring=svg_data,
        write_to=png_path,
        dpi=dpi,
        background_color='white'
    )
    print(f"Rendered '{svg_path}' to '{png_path}' at {dpi} DPI.")

def binarize_image(png_path, bw_path, threshold=180):
    img = Image.open(png_path).convert("L")
    img.save("grayscale_preview.png")  # Optional
    bw = img.point(lambda x: 255 if x > threshold else 0, mode='1')
    bw.save(bw_path)
    print(f"Binarized '{png_path}' to '{bw_path}' with threshold {threshold}.")

def rasterization_node(state: WorkflowState) -> WorkflowState:
    svg_path = state["svg_path"]
    png_path = svg_path.replace(".svg", ".png")
    bw_path = svg_path.replace(".svg", "_bw.png")

    svg_to_png(svg_path, png_path, dpi=254)
    binarize_image(png_path, bw_path, threshold=128)

    state["png_path"] = png_path
    state["bw_path"] = bw_path
    state.setdefault("gcode_relative", True)
    state.setdefault("gcode_anchor", (4.0, 86.0))
    
    print(f"[rasterization_node] bw_path set to: {bw_path}")

    return state

