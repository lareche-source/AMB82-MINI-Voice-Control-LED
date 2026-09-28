import importlib.util
from pathlib import Path
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("voice_led", Path(__file__).with_name("1.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class VoiceLedTests(unittest.TestCase):
    def test_commands_and_rejection(self):
        for text, expected in [("左邊開燈", "BLUE_ON"), ("打開左邊的燈", "BLUE_ON"),
                               ("右边开灯。", "GREEN_ON"), ("右邊開綠燈", "GREEN_ON"),
                               (" 左邊 關燈！", "BLUE_OFF"), ("全部關燈", "ALL_OFF")]:
            self.assertEqual(module.parse_command(text), expected)
        for text in [None, [], 42, "不要左邊開燈", "左邊開燈右邊開燈", "開燈", "x" * 101]:
            self.assertIsNone(module.parse_command(text))

    @patch.object(module.list_ports, "comports")
    def test_detects_single_usb_serial_port(self, comports):
        port = Mock(device="COM4", description="USB-SERIAL CH340")
        comports.return_value = [port]
        self.assertEqual(module.detect_port(), "COM4")

    @patch.object(module.list_ports, "comports")
    def test_does_not_guess_between_multiple_usb_ports(self, comports):
        comports.return_value = [
            Mock(device="COM4", description="USB-SERIAL CH340"),
            Mock(device="COM5", description="USB Serial Device"),
        ]
        self.assertIsNone(module.detect_port())

    def test_api_dispatch_and_invalid_input(self):
        board = Mock()
        client = module.create_app(board).test_client()
        for text, expected in [("左邊開燈", "BLUE_ON"), ("右邊開燈", "GREEN_ON")]:
            response = client.post("/api/command", json={"text": text})
            self.assertEqual(response.status_code, 200)
            board.send.assert_called_with(expected)
        board.reset_mock()
        for data in [{"text": "不要開燈"}, {"text": []}, [], {}]:
            self.assertEqual(client.post("/api/command", json=data).status_code, 400)
        board.send.assert_not_called()
        with client.get("/") as response:
            self.assertEqual(response.status_code, 200)

    def test_timeout_is_not_success(self):
        board = Mock()
        board.send.side_effect = TimeoutError("no acknowledgment")
        response = module.create_app(board).test_client().post("/api/command", json={"text": "左邊開燈"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("error", response.get_json())

    @patch.object(module.subprocess, "run")
    def test_windows_speech_dispatch(self, run):
        run.return_value = SimpleNamespace(
            returncode=0, stdout='{"text":"左邊開燈","confidence":0.92}\n', stderr="")
        board = Mock()
        response = module.create_app(board).test_client().post("/api/listen")
        self.assertEqual(response.status_code, 200)
        board.send.assert_called_once_with("BLUE_ON")

    @patch.object(module.subprocess, "run")
    def test_low_confidence_speech_does_not_control_board(self, run):
        run.return_value = SimpleNamespace(
            returncode=0, stdout='{"text":"右邊開燈","confidence":0.45}\n', stderr="")
        board = Mock()
        response = module.create_app(board).test_client().post("/api/listen")
        self.assertEqual(response.status_code, 400)
        board.send.assert_not_called()

    def test_usb_exact_ack_ignores_boot_logs(self):
        board = module.Board.__new__(module.Board)
        board.lock = threading.Lock()
        board.connection = Mock()
        board.connection.readline.side_effect = [b"READY VOICE_LED\n", b"OK GREEN_ON\n", b"OK BLUE_ON\r\n"]
        board.send("BLUE_ON")
        board.connection.write.assert_called_once_with(b"BLUE_ON\n")
        self.assertEqual(board.connection.readline.call_count, 3)

    def test_usb_timeout(self):
        board = module.Board.__new__(module.Board)
        board.lock = threading.Lock()
        board.connection = Mock()
        board.connection.readline.return_value = b""
        with patch.object(module.time, "monotonic", side_effect=[0, 0, 4]):
            with self.assertRaises(TimeoutError):
                board.send("GREEN_ON")


if __name__ == "__main__":
    unittest.main()
