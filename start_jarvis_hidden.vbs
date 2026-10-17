
Option Explicit

Dim WshShell

Set WshShell = CreateObject("WScript.Shell")

WshShell.CurrentDirectory = "D:\JARVIS"

WshShell.Environment("PROCESS")("PYTHONUTF8") = "1"
WshShell.Environment("PROCESS")("PYTHONIOENCODING") = "utf-8"

WshShell.Run """D:\JARVIS\.venv\Scripts\python.exe"" ""D:\JARVIS\start_jarvis.py""", 0, False

Set WshShell = Nothing
