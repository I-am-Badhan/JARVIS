
Set WshShell = CreateObject("WScript.Shell")

WshShell.CurrentDirectory = "D:\JARVIS"

WshShell.Run """D:\JARVIS\.venv\Scripts\python.exe"" ""D:\JARVIS\start_jarvis.py""", 0, False

Set WshShell = Nothing
