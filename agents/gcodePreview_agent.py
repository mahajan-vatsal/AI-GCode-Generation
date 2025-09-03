# agents/gcode_preview_agent.py
import multiprocessing
import os
import re
from typing import Dict, Any, Tuple, Optional

from PIL import Image, ImageDraw, ImageTk
import tkinter as tk


class GCodePreview:
    def __init__(
        self,
        card_width: float = 85.0,   # mm
        card_height: float = 54.0,  # mm
        scale_factor: int = 8,      # px per mm
        background_color: str = "#FFFFFF",
        forground_color: str = "#000000",
        offset: Tuple[float, float] = (4.0, 86.0),  # anchor in mm
        line_width: int = 1,
    ):
        self.card_width = card_width
        self.card_height = card_height
        self.scale_factor = scale_factor
        self.background_color = background_color
        self.forground_color = forground_color
        self.line_width = line_width
        self.offset = offset

        self.img_width = int(self.card_width * self.scale_factor)
        self.img_height = int(self.card_height * self.scale_factor)

        # Precompute anchor in *pixels* so we can subtract it from absolute coords
        self.anchor_px = (
            float(self.offset[0]) * self.scale_factor,
            float(self.offset[1]) * self.scale_factor,
        )

        # Regexes
        self._word_re = re.compile(r'([A-Z])\s*([-+]?[0-9]*\.?[0-9]+)')
        self._s_re = re.compile(r'\bS\s*([-+]?[0-9]*\.?[0-9]+)')

    def _parse_numbers(self, line: str) -> Dict[str, float]:
        """Return dict of any X/Y/Z/F found on the line (floats)."""
        out: Dict[str, float] = {}
        for w, val in self._word_re.findall(line):
            if w in ("X", "Y", "Z", "F"):
                try:
                    out[w] = float(val)
                except ValueError:
                    pass
        return out

    def parse_gcode(self, draw: ImageDraw.ImageDraw, gcode: str) -> None:
        lines = gcode.splitlines()

        # Machine state (in *pixel* coordinates)
        abs_mode = True
        power_on = False
        s_value = 0

        x = 0.0
        y = 0.0
        current_position = [x, y]

        initialized_rel_origin = False  # NEW: shift origin once on first G91

        for raw in lines:
            line = raw.strip()
            if not line or line.startswith((';', '(')):
                continue

            # Mode toggles
            if line.startswith('G90'):
                abs_mode = True
                continue
            if line.startswith('G91'):
                abs_mode = False
                # Shift drawing origin once so the relative anchor (e.g. X4 Y86)
                # lands near (0,0) on the canvas.
                if not initialized_rel_origin:
                    x = -self.anchor_px[0]
                    y = -self.anchor_px[1]
                    current_position = [x, y]
                    initialized_rel_origin = True
                continue

            # Spindle / Laser on/off
            if line.startswith(('M3', 'M03', 'M4', 'M04')):
                power_on = True
                # keep s_value as-is unless this line also has S
            elif line.startswith(('M5', 'M05')):
                power_on = False
                s_value = 0
                continue  # nothing to draw on this line

            # Update S if present anywhere on this line (motion or not)
            mS = self._s_re.search(line)
            if mS:
                try:
                    s_value = int(float(mS.group(1)))
                except ValueError:
                    pass

            # Motions
            if line.startswith(('G0', 'G00', 'G1', 'G01')):
                nums = self._parse_numbers(line)
                is_rapid = line.startswith(('G0', 'G00'))

                # Start with current coords
                tx, ty = x, y

                # X/Y updates
                if 'X' in nums:
                    # Convert mm->px and apply abs/rel
                    val_px = nums['X'] * self.scale_factor
                    tx = (val_px - self.anchor_px[0]) if abs_mode else (x + val_px)
                if 'Y' in nums:
                    val_px = nums['Y'] * self.scale_factor
                    ty = (val_px - self.anchor_px[1]) if abs_mode else (y + val_px)

                new_position = [tx, ty]

                # Draw only if it's a real move
                if (tx != x) or (ty != y):
                    if (not is_rapid) and power_on and (s_value > 0):
                        # Cutting move
                        draw.line(
                            [tuple(current_position), tuple(new_position)],
                            fill=self.forground_color,
                            width=self.line_width,
                        )
                    # Rapids are skipped visually
                    x, y = tx, ty
                    current_position = new_position

    def generate_preview(self, gcode_data: str) -> Image.Image:
        image = Image.new(
            "RGB", (self.img_width, self.img_height), self.background_color
        )
        draw = ImageDraw.Draw(image)
        self.parse_gcode(draw, gcode_data)
        # Flip so origin behaves like your earlier preview (bottom-left)
        image = image.transpose(method=Image.FLIP_TOP_BOTTOM)
        return image


# --------------------- LangGraph node helpers ---------------------

def _choose_preview_path(state: Dict[str, Any]) -> str:
    """
    Choose a save path for the preview image.
    Priority: gcode_path dir -> bw_path dir -> png_path dir -> svg_path dir -> CWD.
    """
    base_dir: Optional[str] = None
    for key in ("gcode_path", "bw_path", "png_path", "svg_path"):
        p = state.get(key)
        if isinstance(p, str) and p:
            base_dir = os.path.dirname(os.path.abspath(p))
            break
    if base_dir is None:
        base_dir = os.getcwd()
    return os.path.join(base_dir, "gcode_preview.png")


def _show_with_tk(img: Image.Image, window_title: str = "G-code Preview") -> None:
    """
    Show the PIL image in a Tk window and block until the window is closed.
    """
    root = tk.Tk()
    root.title(window_title)
    # Convert PIL image to a Tk-compatible PhotoImage
    photo = ImageTk.PhotoImage(img)
    canvas = tk.Canvas(root, width=photo.width(), height=photo.height(), bg="white", highlightthickness=0)
    canvas.pack()
    canvas.create_image(0, 0, anchor="nw", image=photo)

    # Quality-of-life: allow Esc / q to close
    root.bind("<Escape>", lambda e: root.destroy())
    root.bind("q", lambda e: root.destroy())

    # Ensure clean close on window manager action
    root.protocol("WM_DELETE_WINDOW", root.destroy)

    # Block here until the window is closed
    root.mainloop()


def _preview_worker(
    gcode_text: str,
    save_path: str,
    cfg: Dict[str, Any],
    open_viewer: bool,
    window_title: str = "G-code Preview",
) -> None:
    """
    Run preview generation in a separate process so LangGraph doesn't block the main loop.
    If `open_viewer` is True, this function will block until the Tk window is closed.
    """
    preview = GCodePreview(
        card_width=float(cfg.get("card_width", 85.0)),
        card_height=float(cfg.get("card_height", 54.0)),
        scale_factor=int(cfg.get("scale_factor", 8)),
        background_color=str(cfg.get("background_color", "#FFFFFF")),
        forground_color=str(cfg.get("forground_color", "#000000")),
        offset=tuple(cfg.get("offset", (4.0, 86.0))),
        line_width=int(cfg.get("line_width", 1)),
    )
    img = preview.generate_preview(gcode_text)

    # Save PNG
    try:
        img.save(save_path)
        print(f"[gcode_preview_node] Saved preview to: {save_path}")
    except Exception as e:
        print(f"[gcode_preview_node] Failed to save preview: {e}")

    # Show and BLOCK until closed
    if open_viewer:
        try:
            _show_with_tk(img, window_title=window_title)
        except Exception as e:
            # Fallback: if Tk is unavailable, at least open system viewer (non-blocking)
            print(f"[gcode_preview_node] Tk viewer failed ({e}); opening system viewer (non-blocking).")
            try:
                img.show()
            except Exception as ee:
                print(f"[gcode_preview_node] Fallback viewer failed: {ee}")


# --------------------- LangGraph-compatible node ---------------------

def gcode_preview_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph-compatible node that renders a PNG preview from G-code and
    **waits until the preview window is closed** (when open_gcode_preview=True).
    """
    gcode_text = state.get("gcode_content")
    if not gcode_text or not isinstance(gcode_text, str) or not gcode_text.strip():
        raise ValueError("Missing or empty 'gcode_content' in state.")

    # Build config from state (non-breaking; uses your defaults)
    cfg: Dict[str, Any] = dict(state.get("gcode_preview_config", {}) or {})

    # Allow anchor overrides via either key
    if "gcode_anchor" in state and "offset" not in cfg:
        cfg["offset"] = tuple(state["gcode_anchor"])
    if "offset" in state and "offset" not in cfg:
        cfg["offset"] = tuple(state["offset"])
    if "offset" not in cfg:
        cfg["offset"] = (4.0, 86.0)

    # Save path handling
    save_path = state.get("gcode_preview_save_path") or _choose_preview_path(state)
    open_viewer = bool(state.get("open_gcode_preview", True))
    window_title = str(state.get("preview_window_title", "G-code Preview"))

    print("[gcode_preview_node] Launching preview in a separate process...")
    proc = multiprocessing.Process(
        target=_preview_worker,
        args=(gcode_text, save_path, cfg, open_viewer, window_title),
    )
    proc.start()
    # IMPORTANT: This blocks the main process until the preview window is closed
    proc.join()

    # Return path in state for downstream use
    state["gcode_preview_path"] = save_path
    return state


# --------------------- Optional: CLI test ---------------------

if __name__ == "__main__":
    # Standalone test usage (not used by LangGraph)
    test_file = "output.gcode"
    if os.path.exists(test_file):
        with open(test_file, "r") as f:
            gcode_data = f.read()
    else:
        raise SystemExit(f"Missing test file: {test_file}")

    st = {
        "gcode_content": gcode_data,
        # Optional overrides:
        "gcode_preview_config": {
            "background_color": "#000000",
            "forground_color": "#FFFFFF",
            "line_width": 1,
            "scale_factor": 8,
            "card_width": 85.0,
            "card_height": 54.0,
            # "offset": (4.0, 86.0),
        },
        "open_gcode_preview": True,  # will BLOCK until the window is closed
        "preview_window_title": "G-code Preview (Press Esc or q to close)",
        # "gcode_preview_save_path": "./gcode_preview.png",
    }

    out = gcode_preview_node(st)
    print("Preview saved at:", out.get("gcode_preview_path"))
