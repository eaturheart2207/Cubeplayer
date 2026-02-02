Write-Output "cubeplayer"
python -m pip install --upgrade pip
python -m pip install pygame mutagen
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
python "$ScriptDir\ascii_player.py" $args
