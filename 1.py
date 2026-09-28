"""AMB82-MINI USB bridge. Run: python 1.py --port COM3."""
import argparse
import atexit
import base64
import json
import re
import subprocess
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
import serial
from serial.tools import list_ports


COMMANDS = {
    # Installed orientation: blue is left, green is right.
    "左邊開燈": "BLUE_ON", "打開左邊的燈": "BLUE_ON", "開啟左邊燈": "BLUE_ON",
    "右邊開燈": "GREEN_ON", "打開右邊的燈": "GREEN_ON", "開啟右邊燈": "GREEN_ON",
    "藍燈開燈": "BLUE_ON", "開藍燈": "BLUE_ON", "左邊開藍燈": "BLUE_ON",
    "綠燈開燈": "GREEN_ON", "開綠燈": "GREEN_ON", "右邊開綠燈": "GREEN_ON",
    "左邊關燈": "BLUE_OFF", "右邊關燈": "GREEN_OFF",
    "關藍燈": "BLUE_OFF", "關綠燈": "GREEN_OFF",
    "全部關燈": "ALL_OFF",
}


def detect_port():
    """Return the only serial port, preferring a single CH340/USB serial adapter."""
    ports = list(list_ports.comports())
    usb_ports = [
        port for port in ports
        if any(name in (port.description or "").lower()
               for name in ("ch340", "usb-serial", "usb serial"))
    ]
    candidates = usb_ports or ports
    return candidates[0].device if len(candidates) == 1 else None


def parse_command(text):
    if not isinstance(text, str) or len(text) > 100:
        return None
    normalized = re.sub(r"[\s，。！？,.!?]", "", text)
    normalized = normalized.translate(str.maketrans("边开灯蓝绿关", "邊開燈藍綠關"))
    return COMMANDS.get(normalized)


class Board:
    def __init__(self, port):
        self.lock = threading.Lock()
        self.connection = serial.Serial(port, 115200, timeout=0.2, write_timeout=2)
        time.sleep(2)

    def close(self):
        self.connection.close()

    def send(self, command):
        with self.lock:
            self.connection.reset_input_buffer()
            self.connection.write((command + "\n").encode("ascii"))
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                reply = self.connection.readline(128).decode("ascii", errors="replace").strip()
                if reply == "OK " + command:
                    return
                if reply.startswith("ERR "):
                    raise RuntimeError("板子拒絕指令：" + reply)
            raise TimeoutError("板子未回覆，無法確認燈號；請檢查 USB、韌體並重試。")


def create_app(board):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 2048

    @app.get("/")
    def index():
        return send_from_directory(Path(__file__).parent / "static", "index.html")

    @app.post("/api/command")
    def command():
        data = request.get_json(silent=True)
        text = data.get("text") if isinstance(data, dict) else None
        parsed = parse_command(text)
        if not parsed:
            return jsonify(error="未辨識到支援的指令，請說「左邊開燈」或「右邊開燈」。"), 400
        try:
            board.send(parsed)
        except (serial.SerialException, OSError, RuntimeError) as exc:
            return jsonify(error=str(exc)), 503
        return jsonify(command=parsed, message="板子已確認執行：" + text)

    @app.post("/api/listen")
    def listen():
        script = Path(__file__).parent / "windows_speech.ps1"
        encoded_script = base64.b64encode(
            script.read_text(encoding="utf-8").encode("utf-16le")
        ).decode("ascii")
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-EncodedCommand", encoded_script],
                capture_output=True, text=True, encoding="utf-8", timeout=12,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return jsonify(error="語音辨識逾時，請靠近麥克風再試一次。"), 408
        output = result.stdout.strip().lstrip("\ufeff")
        if result.returncode != 0 or not output:
            detail = result.stderr.strip()
            return jsonify(error=detail or "沒有聽到支援的指令，請再試一次。"), 400
        try:
            speech = json.loads(output)
            text = speech["text"]
            confidence = float(speech["confidence"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return jsonify(error="語音辨識引擎回傳格式錯誤。"), 500
        if confidence < 0.70:
            return jsonify(error="不確定是否聽到「%s」（信心 %.0f%%），未執行任何燈號。" %
                                 (text, confidence * 100), text=text,
                           confidence=confidence), 400
        parsed = parse_command(text)
        if not parsed:
            return jsonify(error="聽到「%s」，但不是支援的指令。" % text), 400
        try:
            board.send(parsed)
        except (serial.SerialException, OSError, RuntimeError) as exc:
            return jsonify(error=str(exc), text=text), 503
        return jsonify(command=parsed, text=text, confidence=confidence,
                       message="辨識到「%s」（信心 %.0f%%），板子已確認執行。" %
                               (text, confidence * 100))

    return app


def main():
    parser = argparse.ArgumentParser(description="AMB82-MINI USB 語音控制 LED")
    parser.add_argument("--port", help="USB 串列埠，例如 COM3")
    parser.add_argument("--list-ports", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--http-port", type=int, default=5000)
    parser.add_argument("--cert", help="手機使用的受信任 HTTPS 憑證 PEM")
    parser.add_argument("--key", help="HTTPS 私鑰 PEM")
    args = parser.parse_args()
    if args.list_ports:
        ports = list(list_ports.comports())
        for port in ports:
            print(f"{port.device}: {port.description}")
        if not ports:
            print("未找到串列埠，請接上板子並確認 USB 驅動程式。")
        return
    if not args.port:
        args.port = detect_port()
    if not args.port:
        parser.error("無法自動選擇串列埠；請用 --list-ports 查看後指定 --port COM4。")
    if bool(args.cert) != bool(args.key):
        parser.error("--cert 和 --key 必須同時提供。")
    try:
        board = Board(args.port)
    except serial.SerialException as exc:
        parser.exit(1, f"無法開啟 USB 串列埠：{exc}\n請關閉 Arduino 序列埠監控視窗。\n")
    atexit.register(board.close)
    context = (args.cert, args.key) if args.cert else None
    create_app(board).run(host=args.host, port=args.http_port, ssl_context=context,
                          debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
