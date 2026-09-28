# Ameba Mini 語音控制 LED 系統

流程：電腦或手機麥克風 → 瀏覽器繁體中文語音辨識 → 電腦上的 Python → USB 串列埠 → AMB82-MINI 板載 LED。
板子一直以 USB 接電腦；手機使用時，手機與電腦另須有網路連線。

| 語音 | 動作 | USB 指令 |
| --- | --- | --- |
| 左邊開燈 | 左側藍燈開啟 | BLUE_ON |
| 右邊開燈 | 右側綠燈開啟 | GREEN_ON |
| 左邊關燈 | 左側藍燈關閉 | BLUE_OFF |
| 右邊關燈 | 右側綠燈關閉 | GREEN_OFF |
| 全部關燈 | 兩燈關閉 | ALL_OFF |

兩燈獨立控制，開啟其中一燈不會關閉另一燈。忽略空白及常見句末標點，也接受上述指令的簡體字。
為避免誤觸，只接受完整指令，不會把「不要左邊開燈」當成開燈。

## 1. 燒錄板端程式

依照 [官方 AMB82-MINI 入門指南](https://github.com/Ameba-AIoT/ameba-arduino-doc/blob/main/source/ameba_pro2/amb82-mini/Getting_Started/Getting%20Started%20with%20Ameba.rst) 安裝 Arduino IDE 的 AmebaPro2 板卡套件及 USB 驅動。
套件索引：

```text
https://github.com/Ameba-AIoT/ameba-arduino-pro2/raw/main/Arduino_package/package_realtek_amebapro2_index.json
```

1. 使用可傳資料的 Micro USB 線接上板子。
2. Arduino IDE 開啟 `firmware/voice_led/voice_led.ino`，選 AMB82-MINI 與正確 COM 埠，編譯並上傳。
3. 若使用手動燒錄模式，依官方指南按住 UART_DOWNLOAD、按放 RESET、放開 UART_DOWNLOAD 後上傳；完成後按 RESET 執行。
4. 可先用序列埠監控視窗，以 **115200 baud** 和換行結尾傳送 `BLUE_ON`、`GREEN_ON`、`ALL_OFF`。應收到 `OK BLUE_ON` 等對應回覆。
5. **關閉序列埠監控視窗**，讓 Python 使用此埠。

官方腳位表：藍燈 Arduino GPIO **23（PF9）**，綠燈 **24（PE6）**。PCB 上的「LED4」是元件標示，不能直接當成 GPIO 4。本程式使用官方藍／綠燈腳位；LED4 與實際顏色的對應尚未在你的板子上確認。
依此板實測，藍燈與綠燈均為高電位亮（HIGH=開、LOW=關）。

## 2. 啟動電腦程式

在本專案目錄開啟終端機（Python 3.10 或以上）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe 1.py --list-ports
.\.venv\Scripts\python.exe 1.py --port COM3
```

將 `COM3` 換成實際連接埠。開啟 **http://localhost:5000**，先用按鈕確認 USB 控制，再按「開始說話」，允許麥克風權限並說「左邊開燈」或「右邊開燈」。
可先用支援 Web Speech API 的 Chrome 測試；實際可用性取決於瀏覽器與語音服務。此功能可能需要網際網路並由瀏覽器服務處理音訊，並非離線辨識。[MDN 語音辨識說明](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition)

Python 只在收到板端對應的 `OK` 回覆後顯示成功；這表示韌體已執行 GPIO 寫入，不是光學感測結果。畫面顯示最後確認的指令結果，不會即時偵測板子斷線或重新啟動。若重新插拔 USB，重啟 Python。

## 3. 手機麥克風

1. 手機與電腦連上同一個區域網路，板子維持 USB 接電腦。
2. 準備手機信任且涵蓋電腦區域網路 IP／主機名稱的 TLS 憑證與私鑰（PEM 格式）。自簽憑證必須先讓手機信任簽發憑證；僅略過瀏覽器警告不保證麥克風可用。
3. 啟動：

```powershell
.\.venv\Scripts\python.exe 1.py --port COM3 --host 0.0.0.0 --cert cert.pem --key key.pem
```

4. 如 Windows 防火牆詢問，允許私人網路存取。手機使用支援語音辨識的瀏覽器開啟 `https://電腦區域網路IP:5000`，授權麥克風後操作。

`http://電腦IP:5000` 不符合此介面的麥克風使用條件；手機上的 `localhost` 指向手機自身。手機 HTTPS 憑證需依實際網路設定，專案未附憑證。服務供本機／可信任區域網路展示，沒有登入驗證，不要直接公開到網際網路。

## 驗證

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_voice_led
```

自動測試涵蓋指令解析、無效指令拒絕、兩種開燈 API、正確串列回覆及逾時失敗。實機驗收：逐一說兩種開燈指令，確認對應顏色點亮、另一燈保持原狀，再測試全部關燈；拔除 USB 後送出指令，畫面應顯示失敗而非成功。
