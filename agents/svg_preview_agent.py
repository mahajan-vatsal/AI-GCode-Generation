# svg_preview_agent.py
from pathlib import Path
from multiprocessing import Process
import tkinter as tk
from PIL import Image, ImageTk
import cairosvg
import io


class ZoomPanCanvas(tk.Canvas):
    def __init__(self, master, pil_image, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master

        # Store the original image
        self.original_image = pil_image
        self.image_scale = 1.0  # current zoom level
        self.tk_image = ImageTk.PhotoImage(self.original_image)
        self.image_id = self.create_image(0, 0, image=self.tk_image, anchor="nw")

        # Scrollbars
        self.config(scrollregion=self.bbox(tk.ALL))
        self.bind("<MouseWheel>", self._on_zoom)
        self.bind("<ButtonPress-1>", self._start_pan)
        self.bind("<B1-Motion>", self._on_pan)

        self.pan_start = None

    def _on_zoom(self, event):
        # Wheel up → zoom in, Wheel down → zoom out
        if event.delta > 0:
            self.image_scale *= 1.1
        else:
            self.image_scale /= 1.1

        # Scale limit
        self.image_scale = max(0.1, min(self.image_scale, 10))

        # Resize image
        new_size = (
            int(self.original_image.width * self.image_scale),
            int(self.original_image.height * self.image_scale)
        )
        resized = self.original_image.resize(new_size, Image.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)

        # Update image on canvas
        self.itemconfig(self.image_id, image=self.tk_image)
        self.config(scrollregion=self.bbox(tk.ALL))

    def _start_pan(self, event):
        self.scan_mark(event.x, event.y)
        self.pan_start = (event.x, event.y)

    def _on_pan(self, event):
        self.scan_dragto(event.x, event.y, gain=1)


def _run_tkinter_preview(svg_path: str):
    """Open zoomable/pannable SVG preview in a standalone Tkinter window."""
    # Convert SVG to PNG in memory
    png_data = cairosvg.svg2png(url=svg_path)
    img = Image.open(io.BytesIO(png_data))

    # Window
    root = tk.Tk()
    root.title(f"SVG Preview - {Path(svg_path).name}")

    # Create scrollable + zoomable canvas
    frame = tk.Frame(root)
    frame.pack(fill="both", expand=True)

    hbar = tk.Scrollbar(frame, orient="horizontal")
    hbar.pack(side="bottom", fill="x")

    vbar = tk.Scrollbar(frame, orient="vertical")
    vbar.pack(side="right", fill="y")

    canvas = ZoomPanCanvas(frame, img, bg="white",
                           xscrollcommand=hbar.set,
                           yscrollcommand=vbar.set)
    canvas.pack(side="left", fill="both", expand=True)

    hbar.config(command=canvas.xview)
    vbar.config(command=canvas.yview)

    # Close button
    tk.Button(root, text="Close", command=root.destroy).pack(pady=5)

    root.mainloop()


def svg_preview_node(state: dict):
    svg_path = state.get("svg_path")
    if not svg_path or not Path(svg_path).exists():
        raise ValueError("Missing or invalid 'svg_path' in state.")

    # Run preview in separate process
    p = Process(target=_run_tkinter_preview, args=(str(svg_path),))
    p.start()

    state["preview_count"] = state.get("preview_count", 0) + 1
    return state
