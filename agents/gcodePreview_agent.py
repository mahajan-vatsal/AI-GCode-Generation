# agents/gcode_preview_agent.py
import multiprocessing
import re
import tkinter as tk

class GCodePreview:
    def __init__(self, gcode_text, canvas_width=800, canvas_height=600):
        self.gcode_text = gcode_text
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.gcode_commands = self._parse_gcode()

    def _parse_gcode(self):
        commands = []
        for line in self.gcode_text.splitlines():
            line = line.strip()
            if not line or line.startswith("("):
                continue
            parts = re.findall(r"([A-Z])([-+]?[0-9]*\.?[0-9]+)", line)
            cmd = {}
            for letter, value in parts:
                if letter in ["G", "M"]:
                    cmd[letter] = int(float(value))
                else:
                    cmd[letter] = float(value)
            commands.append(cmd)
        return commands

    def _extract_segments(self):
        segments = []
        last_pos = (0.0, 0.0)
        laser_on = False
        for cmd in self.gcode_commands:
            g = cmd.get("G")
            x = cmd.get("X", last_pos[0])
            y = cmd.get("Y", last_pos[1])
            if cmd.get("M") == 3 and "S" in cmd:
                laser_on = True
            elif cmd.get("M") == 5:
                laser_on = False
            if g in [0, 1]:
                pos = (x, y)
                segments.append((last_pos, pos, laser_on))
                last_pos = pos
        return segments

    def show(self):
        root = tk.Tk()
        root.title("G-code Preview")
        canvas = tk.Canvas(root, width=self.canvas_width, height=self.canvas_height, bg="white")
        canvas.pack()
        segments = self._extract_segments()
        if not segments:
            print("⚠️ No segments to display.")
            return
        all_x = [pt[0] for seg in segments for pt in [seg[0], seg[1]]]
        all_y = [pt[1] for seg in segments for pt in [seg[0], seg[1]]]
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        gcode_width = max_x - min_x
        gcode_height = max_y - min_y
        if gcode_width == 0 or gcode_height == 0:
            print("⚠️ Zero width/height in bounding box — check G-code content.")
            return
        scale_x = self.canvas_width / gcode_width
        scale_y = self.canvas_height / gcode_height
        scale = min(scale_x, scale_y) * 0.9
        offset_x = (self.canvas_width - gcode_width * scale) / 2
        offset_y = (self.canvas_height - gcode_height * scale) / 2

        def transform(x, y):
            x_draw = offset_x + (x - min_x) * scale
            y_draw = self.canvas_height - (offset_y + (y - min_y) * scale)
            return x_draw, y_draw

        for (x0, y0), (x1, y1), power_on in segments:
            tx0, ty0 = transform(x0, y0)
            tx1, ty1 = transform(x1, y1)
            color = "black" if power_on else "lightgray"
            canvas.create_line(tx0, ty0, tx1, ty1, fill=color, width=1)

        root.mainloop()


def _run_preview(gcode_text):
    GCodePreview(gcode_text).show()


def gcode_preview_node(state: dict) -> dict:
    gcode_text = state.get("gcode_content")
    if not gcode_text or not gcode_text.strip():
        raise ValueError("Missing or empty 'gcode_content' in state.")

    print("[gcode_preview_node] Launching preview in a separate process...")
    proc = multiprocessing.Process(target=_run_preview, args=(gcode_text,))
    proc.start()
    proc.join()  # Wait until window is closed

    return state
