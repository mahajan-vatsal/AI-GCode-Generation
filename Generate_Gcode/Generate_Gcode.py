# from Generate_gcode.preview import GCodePreview
import os
import re


class Generate_Gcode:
    def __init__(self, variant="hs", offset=[4, 86]):
        self._variants = {
            "hs": {
                "variant": "hs",
                "title": ["35", "2.5"],
                "name": ["31", "4"],
                "division": ["27", "2.5"],
                "job_title": ["24", "2.5"],
                "phone": ["17", "2.5"],
                "fax": ["14", "2.5"],
                "mail": ["10", "2.5"],
                "x_offset": "5",
            },
            "blank": {
                "variant": "blank",
                "title": ["35", "2.5"],
                "name": ["31", "4"],
                "division": ["27", "2.5"],
                "job_title": ["24", "2.5"],
                "phone": ["17", "2.5"],
                "fax": ["14", "2.5"],
                "mail": ["10", "2.5"],
                "x_offset": "5",
            },
            "hs-simple": {
                "variant": "hs-simpe",
                "title": ["41.1", "2.5"],
                "name": ["20", "4"],
                "division": ["40.5", "4"],
                "x_offset": "5",
            },
            "zdin": {
                "variant": "zdin",
                "name": ["48", "4"],
                "job_title": ["44", "2.5"],
                "phone": ["9.8", "2.5"],
                "mail": ["6.3", "2.5"],
                "x_offset": "1.3",
            },
            "icps2025": {
                "variant": "icps2025",
                "name": ["20", "4"],
                "division": ["10", "2.5"],
                "job_title": ["10", "2.5"],
                "x_offset": "5",
                },
            "icps2025V2": {
                "variant": "icps2025V2",
                "name": ["20", "4"],
                "division": ["10", "2.5"],
                "job_title": ["10", "2.5"],
                "x_offset": "5",
                },
            "icps2025Blank": {
                "variant": "icps2025Blank",
                "name": ["20", "4"],
                "division": ["10", "2.5"],
                "job_title": ["10", "2.5"],
                "x_offset": "5",
                },
            "icps2025Logo": {
                "variant": "icps2025Logo",
                "name": ["20", "4"],
                "division": ["10", "2.5"],
                "job_title": ["10", "2.5"],
                "x_offset": "5",
                },
        }
        self._fonts = {"4": [1.5, 0.4], "2.5": [0.962, 0.267]}
        self._gcode_tamplet = ""
        self._gcode_data = ""
        self._offset = offset
        self._variant = variant
        self.path = os.path.dirname(os.path.abspath(__file__)) + "/"

    def set_variant(self, variant: str = ""):
        self._variant = self._variants[variant]
        self._gcode_tamplet = (
            "$H\nG90\nG1 X"
            + str(round(self._offset[0], 3))
            + "Y"
            + str(round(self._offset[1], 3))
            + "F5000S0\nG91\nG1"
        )
        with open(self.path + "Templets/" + variant + ".gc", "r") as file:
            self._gcode_tamplet += file.read()

    def set_offset(self, x, y):
        self._offset = [x, y]

    def get_gcode(self):
        return self._gcode_data

    def generate_gcode(self, info: list[str]):
        if info["variant"] is not self._variant:
            self.set_variant(info["variant"])
        self._gcode_data = self._gcode_tamplet
        for i in info:
            if i == "variant" or info[i] == "":
                continue
            try:
                self.add_text(i, info[i])
            except:
                continue

        self.clean_up()

    def add_text(self, type, text):
        self._gcode_data += (
            "G90\nG1 X"
            + str(round(self._offset[0], 3))
            + "Y"
            + str(round(self._offset[1], 3))
        )
        self._gcode_data += "F5000S0\nG91\nG1"
        self._gcode_data += (
            "X" + self._variant["x_offset"] + "Y" + self._variant[type][0] + "S0\n"
        )

        font_size = self._variant[type][1]
        offset = self.find_max(font_size)
        x_offset = 0
        for i in text:
            if i == " ":
                x_offset = self._fonts[font_size][0]
            else:
                i = "dot" if i == "." else i
                i = "slash" if i == "/" else i
                i = "backslash" if i == "\\" else i
                with open(
                    self.path + "Letters/" + font_size + "/" + i + ".gc", "r"
                ) as file:
                    letter = file.read()
                self._gcode_data += (
                    "G0 X" + str(x_offset) + "Y" + str(-offset[i][1]) + "\n" + letter
                )
                self._gcode_data += (
                    "G0 X"
                    + str(round(offset[i][0] + self._fonts[font_size][1], 3))
                    + "Y"
                    + str(offset[i][1])
                    + "\n"
                )
                x_offset = 0

    def find_max(self, font):
        letters = os.listdir(self.path + "Letters/" + font)
        letters.sort()
        offset = {}
        for letter in letters:
            x_max, x = 0, 0
            y_offset, y = 0, 0
            abs_mode = True
            power_on = False
            first_y = True
            s_value = 0
            with open(self.path + "Letters/" + font + "/" + letter, "r") as file:
                gcode = file.read()
            lines = gcode.strip().split("\n")
            for line in lines:
                if line.startswith(";") or not line.strip():
                    continue

                if line.startswith("G90"):
                    abs_mode = True
                elif line.startswith("G91"):
                    abs_mode = False
                elif line.startswith("M3") or line.startswith("M4"):
                    power_on = True
                elif line.startswith("M5"):
                    power_on = False

                if line.startswith(("G0", "G00", "G1", "G01")):
                    matches = re.findall(
                        r"X([-+]?[0-9]*\.?[0-9]+)|Y([-+]?[0-9]*\.?[0-9]+)|S([0-9]+)",
                        line,
                    )
                    for match in matches:
                        if match[0]:
                            x_new = float(match[0])
                            x = x_new if abs_mode else x + x_new
                        if match[1]:
                            y_new = float(match[1])
                            if line.startswith(("G0", "G00")) and first_y:
                                y_offset = y_new
                                first_y = False
                            y = y_new if abs_mode else y + y_new
                        if match[2]:
                            s_value = int(match[2])

                    if line.startswith(("G0", "G00")):
                        pass
                    elif power_on and (s_value is None or s_value > 0):
                        x_max = x if x > x_max else x_max
            offset[letter.removesuffix(".gc")] = [round(x_max, 3), round(y_offset, 3)]
        return offset

    def clean_up(self):
        self._gcode_data = self._gcode_data.replace("M2\n", "")
        # self._gcode_data = self._gcode_data.replace('M4\n', '')
        # self._gcode_data = self._gcode_data.replace('M5\n', '')
        self._gcode_data = self._gcode_data.replace("M8\n", "")
        self._gcode_data = self._gcode_data.replace("M9\n", "")
        self._gcode_data = self._gcode_data.replace("G00 G17 G40 G21 G54\n", "")
        self._gcode_data = "G00 G17 G40 G21 G54\nM4\n" + self._gcode_data
        self._gcode_data += "G1 S0\nM5\nM2"


if __name__ == "__main__":
    gcode_data = ""
    gcode = Generate_Gcode()
    gcode.set_offset(4, 86)
    gcode.generate_gcode(
        {
            "variant": "hs",
            "title": "Student",
            "name": "Yaman Alsaady",
            "division": "Fachbereich Technik",
            "job_title": "Studentische Hilfskraft",
            "phone": "Tel.: 01577 7777777",
            "fax": "Fax: \\_(-_-)_/",
            "mail": "yaman.alsaady@stud.hs-emden-leer.de",
        }
    )
    # gcode_data = gcode.generate_Gcode(
    #     {
    #         "variant": "zdin",
    #         "name": "Yaman Alsaady",
    #         "job_title": "Studentische Hilfskraft",
    #         "phone": "Tel.: 01577 7777777",
    #         "mail": "yaman.alsaady@zdin.de",
    #     }
    # )

    gcode_data = gcode.get_gcode()
    # prev = GCodePreview(offset=[4, 86])
    # prev.generate_preview(gcode_data).show()
    # with open("test_Generate.gc", "w") as outfile:
    #     outfile.write(gcode_data)
