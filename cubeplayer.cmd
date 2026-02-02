@echo off
echo cubeplayer
python -m pip install --upgrade pip
python -m pip install pygame mutagen
set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%ascii_player.py" %*
