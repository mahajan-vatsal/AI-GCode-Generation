from sys import argv
import threading
import serial
from time import sleep, time
import os
import websocket

DOWN = 255
UP = 230

class Laser:
    def __init__(
        self,
        port: str = "/dev/ttyUSB2",
        baudrate: int = 115200,
        timeout: int = 1,
        gcode_dir="/gcode_shared/",
        esp_ip = "192.168.157.20:81",
        dummy=False,
    ):
        self.port = "/dev/ttyUSB2",
        self.baudrate = 115200,
        self.timeout = 1,

        self._feed = 5000
        self.delay_time = 0.05
        self.is_connected = False
        self.is_ESP32_connected = False
        self.is_running = False
        self._stop_file = False
        self._stop_sending = True
        self._filename = str()
        self._command = str()
        self._gcode_dir = gcode_dir
        self._break_time = 5
        self.esp_ip = "ws://" + esp_ip
        self.dummy = dummy
        self.rpi = None
        self.actuator = None
        self.progress = 0
        if not self.dummy:
            import revpimodio2
        if not self.dummy:
            try:
                self.ser = serial.Serial(port, baudrate, timeout=timeout)
                self.is_connected = self.ser.is_open
                self.rpi = revpimodio2.RevPiModIO(
                    autorefresh=True,
                )
                self.fan_control(False)
            except:
                pass
            try:
                self.actuator = websocket.create_connection(self.esp_ip)
                self.is_ESP32_connected = True
            except:
                self.is_ESP32_connected = True
        else:
            self.is_connected = True
            self.is_ESP32_connected = True
            self._gcode_dir = (
                os.path.dirname(os.path.abspath(__file__)) + "/GcodeShared/"
            )

    def __del__(self):
        self.fan_control(False)
        if self.is_connected and not self.dummy:
            self.ser.close()
            self.rpi.exit()

    def connect(self):
        if not self.is_connected and not self.dummy:
                self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
                self.is_connected = self.ser.is_open
                self.rpi = revpimodio2.RevPiModIO(
                    autorefresh=True,
                )
                self.fan_control(False)

        if self.is_connected and self.is_ESP32_connected and not self.dummy:
            try:
                self.actuator = websocket.create_connection(self.esp_ip)
                self.is_ESP32_connected = True
            except:
                self.is_ESP32_connected = True

    def connected(self) -> bool:
        return self.is_connected

    def esp_connected(self) -> bool:
        return self.is_ESP32_connected

    def running(self) -> bool:
        return self.is_running

    def get_delay_time(self):
        return self.delay_time

    def set_delay_time(self, dt: float):
        self.delay_time = dt

    def get_progress(self) -> int:
            return self.progress

    def move_actuator_hight(self, angle):
        if not self.is_ESP32_connected:
            return False
        return self.actuator.send('h:' + str(angle))

    def move_actuator_push(self, angle):
        if not self.is_ESP32_connected:
            return False
        return self.actuator.send('p:' + str(angle))
    
    def _send_command(self, command: str):
        if not self.is_connected:
            return
        # if self.is_running:
        #     return
        self.is_running = True
        self._stop_sending = False

        command = command.strip()
        timeout = time() + self._break_time
        if not self.dummy:
            self.ser.write((command + "\r\n").encode())
        else:
            sleep(1)
        print(command + "\r\n", end="")

        count = 0
        while not self._stop_sending:
            if time() > timeout:
                break
            if count == 2:
                break
            line = b"ok\r\n"
            if not self.dummy:
                line = self.ser.readline()
            if line == b"ok\r\n":
                print(line)
                count += 1
        self.is_running = False
        self._stop_sending = True

    def send_command(self, command: str):
        if not self.is_connected:
            return -1
        threading.Thread(target=self._send_command, args=[command], daemon=True).start()
        return 0

    def _run_code(self, codes: list[str]):
        if not self.is_connected:
            return
        if self.is_running:
            return
        self.fan_control(True)
        self.is_running = True
        self._stop_file = False

        self.progress = 0

        codes.insert(0, "G90")
        executable_lines = [
            code for code in codes
            if not code.strip().startswith(";") and not code.isspace() and len(code.strip()) > 0
        ]
        total_lines = len(executable_lines)
        current_line = 0
        print(total_lines)

        for code in codes:
            if self._stop_file:
                print("File stoped")
                break

            if code.strip().startswith(";") or code.isspace() or len(code) <= 0:
                code = ""
            code = code.strip()
            timeout = time() + self._break_time

            if code:
                current_line += 1
                self.progress = round((current_line / total_lines) * 100, 2)

            count = 0
            print(code + "\r\n", end="")
            if not self.dummy:
                self.ser.write((code + "\r\n").encode())
            while not self._stop_file:
                if time() > timeout:
                    self._stop_sending = True
                    print("Time out")
                    break
                if count == 2:
                    break
                line = b"ok\r\n"
                if not self.dummy:
                    line = self.ser.readline()
                else:
                    sleep(0.01)
                if line == b"ok\r\n":
                    count += 1
        sleep(5)
        self.fan_control(False)
        self.is_running = False

    def run_file(self, filename: str):
        if self.dummy:
            sleep(2)
        print("Run File")
        if not self.is_connected:
            return -1
        if self.is_running:
            return -1
        try:
            f = open(self._gcode_dir + filename, "r")
            codes = [code for code in f]
            f.close()
        except:
            print("File not opened")
            return -1

        print(self._gcode_dir + filename)
        threading.Thread(target=self._run_code, args=[codes], daemon=True).start()
        return 0

    def get_gcode(self, filename: str):
        # print(self._gcode_dir + filename)
        if not self.is_connected:
            return ""
        try:
            f = open(self._gcode_dir + filename, "r")
            codes = f.read()
            f.close()
        except:
            print("File not opened")
            return ""
        return codes

    def run_code(self, codes: list[str]):
        if not self.is_connected:
            return -1
        if self.is_running:
            return -1
        threading.Thread(target=self._run_code, args=[codes], daemon=True).start()
        return 0

    def stop(self):
        self._stop_sending = True
        self._stop_file = True
        sleep(0.001)
        self._stop_sending = True
        self._stop_file = True

    def reference(self) -> int:
        if not self.is_connected:
            return -1
        self.move_actuator_hight(UP)
        return self.send_command("$H")

    def move_relativ(self, xval: int = 0, yval: int = 0) -> int:
        if not self.is_connected:
            return -1
        xval = str(float(int(xval)))
        yval = str(float(int(yval)))
        feed = str(int(self._feed))
        self._send_and_wait("M5 S0")
        return self.send_command("$J=G91" + "X" + xval + "Y" + yval + "F" + feed)

    def move_absolut(self, xval: int = 0, yval: int = 0, feed: int = 5000) -> int:
        if not self.is_connected:
            return -1
        xval = str(float(int(xval)))
        yval = str(float(int(yval)))
        feed = str(int(feed))
        self._send_and_wait("M5 S0")
        return self.send_command("$J=G90" + "X" + xval + "Y" + yval + "F" + feed)

    def pointer(self, on: bool):
        if not self.is_connected:
            return -1
        if on:
            self.send_command("M3 S5")
            while self.is_running:
                pass
            self.send_command("G1 F1000")
        else:
            self.send_command("M5 S0")
            while self.is_running:
                pass
            self.send_command("G0")
        return 0

    def list_files(self) -> list[str]:
        return os.listdir(self._gcode_dir)

    def fan_control(self, onoff: bool = True):
        if not self.rpi:
            return -1
        print("Fan: " + str(onoff))
        if not self.dummy:
            self.rpi.io.O_1(onoff)
            sleep(1)
            self.rpi.io.O_1(onoff)
        return 0

    def _send_and_wait(self, command: str):
        timeout = time() + self._break_time
        if not self.dummy:
            self.ser.write((command.strip() + "\r\n").encode())
        else:
            sleep(1)

        count = 0
        while True:
            if time() > timeout:
                break
            if count == 2:
                break
            line = b"ok\r\n"
            if not self.dummy:
                line = self.ser.readline()
            if line == b"ok\r\n":
                count += 1

    def push_card_in(self):
        if not self.is_connected:
            return -1
        if not self.is_ESP32_connected:
            return -1
        if self.is_running:
            return -1
        threading.Thread(target=self._push_card_in, daemon=True).start()

    def _push_card_in(self):
        self.is_running = True
        self._stop_sending = False
        self._send_and_wait("M5 S0")
        self.move_actuator_hight(UP)
        self.move_actuator_push(0)
        self._send_and_wait("$J=G90X100Y385F10000")
        sleep(3)
        self.move_actuator_push(270)
        sleep(1)
        self.move_actuator_hight(DOWN)
        sleep(2)
        self._send_and_wait("$J=G90X100Y169F10000")
        sleep(3)
        self.move_actuator_hight(UP)
        sleep(2)
        self.is_running = False

    def push_card_out(self):
        if not self.is_connected:
            return -1
        if not self.is_ESP32_connected:
            return -1
        if self.is_running:
            return -1
        threading.Thread(target=self._push_card_out, daemon=True).start()

    def _push_card_out(self):
        self.is_running = True
        self._stop_sending = False
        self._send_and_wait("M5 S0")
        self.move_actuator_hight(UP)
        # self.move_absolut(50, 142)
        self._send_and_wait("$J=G90X50Y142F10000")
        sleep(2)
        self.move_actuator_hight(DOWN+1)
        sleep(2)
        # self.move_absolut(157, 142)
        self._send_and_wait("$J=G90X157Y142F10000")
        sleep(2)

        self.move_actuator_hight(UP)
        sleep(1)
        # self.move_absolut(201, 104)
        self._send_and_wait("$J=G90X201Y104F10000")
        sleep(1)
        self.move_actuator_hight(DOWN+1)
        sleep(2)
        # self.move_absolut(201, 384)
        self._send_and_wait("$J=G90X201Y384F10000")
        sleep(3)
        self.move_actuator_hight(UP)
        self.move_absolut(201, 350)
        self._send_and_wait("$J=G90X201Y350F10000")
        self.is_running = False

if __name__ == "__main__":
    laser = Laser()
    laser.run_file()

