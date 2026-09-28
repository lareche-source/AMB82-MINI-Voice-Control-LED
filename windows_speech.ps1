$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Speech

$culture = [System.Globalization.CultureInfo]::GetCultureInfo('zh-TW')
$recognizerInfo = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() |
    Where-Object { $_.Culture.Name -eq 'zh-TW' } |
    Select-Object -First 1

if (-not $recognizerInfo) {
    [Console]::Error.WriteLine('Windows 未安裝繁體中文語音辨識引擎。')
    exit 2
}

$engine = [System.Speech.Recognition.SpeechRecognitionEngine]::new()
try {
    $phrases = [System.Speech.Recognition.Choices]::new()
    $phrases.Add([string[]]@(
        '左邊開燈', '左邊開藍燈', '開藍燈', '打開左邊的燈',
        '右邊開燈', '右邊開綠燈', '開綠燈', '打開右邊的燈',
        '左邊關燈', '關藍燈', '右邊關燈', '關綠燈', '全部關燈'
    ))
    $builder = [System.Speech.Recognition.GrammarBuilder]::new()
    $builder.Culture = $culture
    $builder.Append($phrases)
    $engine.LoadGrammar([System.Speech.Recognition.Grammar]::new($builder))
    $engine.SetInputToDefaultAudioDevice()
    $result = $engine.Recognize([TimeSpan]::FromSeconds(7))
    if ($null -eq $result) { exit 3 }
    $payload = @{
        text = $result.Text
        confidence = $result.Confidence
    } | ConvertTo-Json -Compress
    [Console]::Out.WriteLine($payload)
} catch {
    [Console]::Error.WriteLine('無法使用電腦麥克風：' + $_.Exception.Message)
    exit 4
} finally {
    $engine.Dispose()
}
