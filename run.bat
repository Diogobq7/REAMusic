@echo off
title REA Music Launcher
echo Starting REA Music Desktop Player with active audio engine...

if exist "REAMusic.exe" (
    start "" "REAMusic.exe"
) else if exist "dist\REAMusic.exe" (
    start "" "dist\REAMusic.exe"
) else (
    python main.py
)
