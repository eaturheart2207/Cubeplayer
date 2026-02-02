#!/usr/bin/env python3
"""
ASCII Music Player (cross-platform)

Dependencies:
  - pygame (pip install pygame)
  - optional: mutagen (pip install mutagen) for accurate duration and tag display

Usage:
  python ascii_player.py [file-or-folder] [more files/folders]
  python ascii_player.py

Notes:
  If no paths are provided and a last folder exists, playback starts from it.
  Otherwise a folder browser opens.
  The last selected folder is stored in ~/.ascii_player_last_dir.

  Quick launch: add the project folder to PATH and run `cubeplayer`.
  - Linux/macOS: ln -s /path/to/project/cubeplayer ~/.local/bin/cubeplayer
  - Windows: add project folder to PATH, then run cubeplayer (cubeplayer.cmd)
  - PowerShell: run cubeplayer.ps1 or add folder to PATH

Keys:
  Space      Play/Pause
  Up/Down   Move selection
  Enter     Play selected
  n         Next track
  p         Previous track
  s         Stop
  r         Toggle repeat
  h         Toggle shuffle
  b         Browse folder
  + / -     Volume up/down
  q         Quit
"""

from __future__ import annotations

import argparse
import curses
import math
import os
import random
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

CONFIG_PATH = os.path.expanduser("~/.ascii_player_last_dir")

import pygame

SUPPORTED_EXTS = {".mp3", ".wav", ".ogg", ".flac"}

try:
    from mutagen import File as MutagenFile  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    MutagenFile = None


@dataclass
class Track:
    path: str
    title: str
    duration: Optional[float]

def human_time(seconds: Optional[float]) -> str:
    if seconds is None or seconds < 0:
        return "--:--"
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes:02d}:{secs:02d}"


def get_duration(path: str) -> Optional[float]:
    if MutagenFile is None:
        return None
    try:
        audio = MutagenFile(path)
        if audio is None or audio.info is None:
            return None
        return float(audio.info.length)
    except Exception:
        return None


def _first_tag_value(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value)


def get_title_from_tags(path: str) -> Optional[str]:
    if MutagenFile is None:
        return None
    try:
        audio = MutagenFile(path, easy=True)
    except Exception:
        return None
    if audio is None or not audio.tags:
        return None
    value = audio.tags.get("title")
    title = _first_tag_value(value)
    if title:
        return title
    return None


def get_tags_summary(path: str) -> List[str]:
    if MutagenFile is None:
        return ["Tags unavailable (install mutagen)"]
    try:
        audio = MutagenFile(path, easy=True)
    except Exception:
        return ["Tags unavailable (install mutagen)"]
    if audio is None or not audio.tags:
        return ["Tags unavailable (install mutagen)"]

    def tag_or_unknown(key: str) -> str:
        return _first_tag_value(audio.tags.get(key)) or "unknown"

    return [
        f"Title: {tag_or_unknown('title')}",
        f"Artist: {tag_or_unknown('artist')}",
        f"Album: {tag_or_unknown('album')}",
        f"Year: {tag_or_unknown('date')}",
        f"Genre: {tag_or_unknown('genre')}",
        f"Track#: {tag_or_unknown('tracknumber')}",
    ]


def collect_tracks(paths: List[str]) -> List[Track]:
    files: List[str] = []
    for path in paths:
        if os.path.isdir(path):
            for root, _, filenames in os.walk(path):
                for name in filenames:
                    ext = os.path.splitext(name)[1].lower()
                    if ext in SUPPORTED_EXTS:
                        files.append(os.path.join(root, name))
        else:
            files.append(path)

    tracks: List[Track] = []
    for file_path in sorted(set(files)):
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in SUPPORTED_EXTS:
            continue
        title = get_title_from_tags(file_path) or os.path.splitext(os.path.basename(file_path))[0]
        duration = get_duration(file_path)
        tracks.append(Track(path=file_path, title=title, duration=duration))
    return tracks


def draw_ui(
    stdscr: curses.window,
    tracks: List[Track],
    current_index: int,
    selection_index: int,
    elapsed: float,
    paused: bool,
    repeat: bool,
    shuffle: bool,
    volume: float,
    status_message: str,
    show_keys: bool,
    viz_phase: float,
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()

    def draw_box(y: int, title: str, lines: List[str]) -> int:
        inner_width = max(10, width - 4)
        top = f"┌{title.center(inner_width, '─')}┐"
        stdscr.addstr(y, 1, top[: width - 2])
        y += 1
        for line in lines:
            padded = line.ljust(inner_width)
            stdscr.addstr(y, 1, f"│{padded}│"[: width - 2])
            y += 1
        stdscr.addstr(y, 1, f"└{'─' * inner_width}┘"[: width - 2])
        return y + 1

    if not tracks:
        draw_box(1, " No tracks ", ["No tracks found."])
        stdscr.refresh()
        return

    banner = [
        "_________  ____ __________________________________.____       _____ _____.___._____________________ ",
        "\\_   ___ \\|    |   \\______   \\_   _____/\\______   \\    |     /  _  \\\\__  |   |\\_   _____/\\______   \\",
        "/    \\  \/|    |   /|    |  _/|    __)_  |     ___/    |    /  /_\\  \\/   |   | |    __)_  |       _/",
        "\\     \\___|    |  / |    |   \\|        \\ |    |   |    |___/    |    \\____   | |        \\ |    |   \\",
        " \\______  /______/  |______  /_______  / |____|   |_______ \\____|__  / ______|/_______  / |____|_  /",
        "        \/                 \/        \/                   \/       \/\/               \/         \/",
    ]
    for idx, line in enumerate(banner):
        if idx >= height:
            break
        stdscr.addstr(idx, max(0, (width - len(line)) // 2), line[: width - 1])

    current = tracks[current_index]
    status = "Paused" if paused else "Playing"
    volume_pct = int(volume * 100)
    status_line = (
        f"{status}  Repeat:{'ON' if repeat else 'OFF'}  "
        f"Shuffle:{'ON' if shuffle else 'OFF'}  Vol:{volume_pct}%"
    )
    duration = current.duration
    time_line = f"{human_time(elapsed)} / {human_time(duration)}"

    bar_width = max(10, width - 6)
    if duration and duration > 0:
        filled = int((elapsed / duration) * (bar_width - 2))
        filled = max(0, min(filled, bar_width - 2))
    else:
        filled = 0
    bar = "[" + "█" * filled + "·" * (bar_width - 2 - filled) + "]"

    tags_summary = get_tags_summary(current.path)

    y = min(len(banner) + 1, height - 1)

    y = draw_box(
        y,
        " Now Playing ",
        [
            f"Track: {current.title}",
            status_line,
            time_line,
            bar,
        ],
    )

    inner_width = max(10, width - 4)
    bars = max(10, inner_width // 2)
    max_height = 8
    viz_lines = []
    for row in range(max_height, 0, -1):
        line_chars = []
        for idx in range(bars):
            wave = (1 + math.sin(viz_phase + idx * 0.5)) / 2
            level = 1 + int(wave * (max_height - 1))
            line_chars.append("█" if level >= row else " ")
            line_chars.append(" ")
        line = "".join(line_chars)[:inner_width].ljust(inner_width)
        viz_lines.append(line)
    y = draw_box(y, " Visualizer ", viz_lines)

    y = draw_box(y, " Tags ", tags_summary)

    if show_keys:
        keys_lines = [
            "Space: Play/Pause",
            "Enter: Play selected",
            "Up/Down: Select track",
            "Left/Right: Seek ±5s",
            "n/p (т/з): Next/Prev track",
            "s (ы): Stop",
            "r (к): Repeat",
            "h (р): Shuffle",
            "b (и): Browse folder",
            "k (л): Toggle keys panel",
            "q (й): Quit",
            "+/-: Volume",
        ]
        y = draw_box(y, " Keys ", keys_lines)

    list_height = max(3, height - y - 3)
    start = max(0, selection_index - list_height // 2)
    end = min(len(tracks), start + list_height)
    playlist_lines: List[str] = []
    for idx in range(start, end):
        is_current = idx == current_index
        is_selected = idx == selection_index
        prefix = ">" if is_current else " "
        selector = "*" if is_selected else " "
        playlist_lines.append(f"{selector}{prefix} {idx + 1:02d}. {tracks[idx].title}")
    if not playlist_lines:
        playlist_lines = ["<empty>"]

    y = draw_box(y, " Tracklist ", playlist_lines)

    footer = "[Space]Play/Pause [n/p]Track [k]Keys [q]Quit"
    if status_message:
        footer = f"{footer} | {status_message}"
    stdscr.addstr(height - 1, 0, footer[: width - 1])
    stdscr.refresh()


def play_track(track: Track) -> None:
    pygame.mixer.music.load(track.path)
    pygame.mixer.music.play()


def load_last_dir() -> Optional[str]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
            path = handle.read().strip()
        return path if path else None
    except OSError:
        return None


def save_last_dir(path: str) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
            handle.write(path)
    except OSError:
        pass


def browse_for_folder(
    stdscr: curses.window,
    start_dir: str,
    allow_files: bool = False,
    filter_exts: Optional[Tuple[str, ...]] = None,
) -> Optional[str]:
    curses.curs_set(0)
    stdscr.nodelay(False)
    current_dir = os.path.abspath(start_dir)
    selection = 0

    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        title = "Select path (Enter=open, Space=choose, Backspace=up, q=cancel)"
        stdscr.addstr(0, 2, title[: width - 4])
        stdscr.addstr(1, 2, f"Current: {current_dir}"[: width - 4])

        entries: List[Tuple[str, bool]] = []
        try:
            for name in os.listdir(current_dir):
                full = os.path.join(current_dir, name)
                if os.path.isdir(full):
                    entries.append((name, True))
                elif allow_files:
                    if filter_exts is None or os.path.splitext(name)[1].lower() in filter_exts:
                        entries.append((name, False))
        except OSError:
            entries = []

        entries.sort(key=lambda item: (not item[1], item[0].lower()))
        if current_dir != os.path.abspath(os.sep):
            entries.insert(0, ("..", True))

        if not entries:
            stdscr.addstr(3, 2, "<empty>")

        list_height = height - 6
        start = max(0, selection - list_height // 2)
        end = min(len(entries), start + list_height)
        for idx in range(start, end):
            name, is_dir = entries[idx]
            marker = ">" if idx == selection else " "
            suffix = "/" if is_dir else ""
            line = f"{marker} {name}{suffix}"
            stdscr.addstr(3 + idx - start, 2, line[: width - 4])

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord('q'), ord('Q')):
            return None
        if key in (curses.KEY_UP, ord('k')):
            selection = max(0, selection - 1)
        elif key in (curses.KEY_DOWN, ord('j')):
            selection = min(len(entries) - 1, selection + 1)
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            current_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
            selection = 0
        elif key in (curses.KEY_ENTER, 10, 13):
            if not entries:
                continue
            chosen, is_dir = entries[selection]
            if chosen == "..":
                current_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
                selection = 0
            elif is_dir:
                current_dir = os.path.join(current_dir, chosen)
                selection = 0
        elif key in (ord(' '),):
            if not entries:
                continue
            chosen, is_dir = entries[selection]
            if chosen == "..":
                continue
            if is_dir:
                return os.path.join(current_dir, chosen)
            if allow_files:
                return os.path.join(current_dir, chosen)


def main(stdscr: curses.window, tracks: List[Track]) -> None:
    curses.curs_set(0)
    stdscr.nodelay(True)
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()

    pygame.init()
    pygame.mixer.init()
    pygame.mixer.music.set_endevent(pygame.USEREVENT)

    current_index = 0
    selection_index = 0
    paused = False
    repeat = False
    shuffle = False
    show_keys = False
    volume = 0.7
    pygame.mixer.music.set_volume(volume)
    elapsed = 0.0
    last_tick = time.monotonic()
    status_message = ""
    status_until = 0.0
    input_block_until = 0.0
    viz_phase = 0.0

    if tracks:
        play_track(tracks[current_index])

    while True:
        now = time.monotonic()
        delta = now - last_tick
        last_tick = now

        if pygame.mixer.music.get_busy() and not paused:
            elapsed += delta
            viz_phase += delta * 4.0
        if status_message and time.monotonic() > status_until:
            status_message = ""

        for event in pygame.event.get():
            if event.type == pygame.USEREVENT:
                if repeat:
                    play_track(tracks[current_index])
                    elapsed = 0.0
                else:
                    if shuffle:
                        current_index = random.randrange(len(tracks))
                    else:
                        current_index = (current_index + 1) % len(tracks)
                    selection_index = current_index
                    play_track(tracks[current_index])
                    elapsed = 0.0

        try:
            key = stdscr.get_wch()
        except curses.error:
            key = None

        if key is not None and time.monotonic() >= input_block_until:
            if key in ('q', 'Q', 'й', 'Й'):
                break
            if key == ' ':
                if paused:
                    pygame.mixer.music.unpause()
                    paused = False
                else:
                    pygame.mixer.music.pause()
                    paused = True
            elif key in ('n', 'N', 'т', 'Т'):
                current_index = (current_index + 1) % len(tracks)
                selection_index = current_index
                play_track(tracks[current_index])
                elapsed = 0.0
            elif key in ('p', 'P', 'з', 'З'):
                current_index = (current_index - 1) % len(tracks)
                selection_index = current_index
                play_track(tracks[current_index])
                elapsed = 0.0
            elif key == curses.KEY_UP:
                selection_index = max(0, selection_index - 1)
            elif key == curses.KEY_DOWN:
                selection_index = min(len(tracks) - 1, selection_index + 1)
            elif key in (curses.KEY_ENTER, 10, 13, '\n', '\r'):
                current_index = selection_index
                play_track(tracks[current_index])
                elapsed = 0.0
                paused = False
            elif key in ('s', 'S', 'ы', 'Ы'):
                pygame.mixer.music.stop()
                paused = False
                elapsed = 0.0
            elif key in ('r', 'R', 'к', 'К'):
                repeat = not repeat
            elif key in ('h', 'H', 'р', 'Р'):
                shuffle = not shuffle
            elif key == curses.KEY_LEFT:
                elapsed = max(0.0, elapsed - 5.0)
                pygame.mixer.music.play(start=elapsed)
                if paused:
                    pygame.mixer.music.pause()
            elif key == curses.KEY_RIGHT:
                elapsed += 5.0
                pygame.mixer.music.play(start=elapsed)
                if paused:
                    pygame.mixer.music.pause()
            elif key in ('b', 'B', 'и', 'И'):
                stdscr.nodelay(False)
                start_dir = load_last_dir() or os.path.expanduser("~")
                chosen = browse_for_folder(stdscr, start_dir)
                stdscr.nodelay(True)
                if chosen:
                    save_last_dir(chosen)
                    new_tracks = collect_tracks([chosen])
                    if new_tracks:
                        tracks[:] = new_tracks
                        current_index = 0
                        selection_index = 0
                        elapsed = 0.0
                        paused = False
                        play_track(tracks[current_index])
            elif key in ('k', 'K', 'л', 'Л'):
                show_keys = not show_keys
            elif key in ('+', '='):
                volume = min(1.0, volume + 0.05)
                pygame.mixer.music.set_volume(volume)
            elif key in ('-', '_'):
                volume = max(0.0, volume - 0.05)
                pygame.mixer.music.set_volume(volume)
        draw_ui(
            stdscr,
            tracks,
            current_index,
            selection_index,
            elapsed,
            paused,
            repeat,
            shuffle,
            volume,
            status_message,
            show_keys,
            viz_phase,
        )
        time.sleep(0.05)

    pygame.mixer.music.stop()
    pygame.mixer.quit()
    pygame.quit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ASCII music player for terminal")
    parser.add_argument("paths", nargs="*", help="Files or folders to play")
    return parser.parse_args()


def _select_paths_via_browser() -> List[str]:
    selected: List[str] = []

    def _inner(stdscr: curses.window) -> None:
        nonlocal selected
        start_dir = load_last_dir() or os.path.expanduser("~")
        choice = browse_for_folder(stdscr, start_dir)
        if choice:
            save_last_dir(choice)
            selected = [choice]

    curses.wrapper(_inner)
    return selected


def run() -> None:
    print("thank you for using cubeplayer")
    args = parse_args()
    paths = args.paths
    if not paths:
        last_dir = load_last_dir()
        if last_dir:
            paths = [last_dir]
        else:
            paths = _select_paths_via_browser()
    if not paths:
        print("No paths provided. Pass files/folders or choose a folder.")
        return
    tracks = collect_tracks(paths)
    if not tracks:
        print("No supported audio files found.")
        return
    curses.wrapper(main, tracks)
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")
    print("thank you for using cubeplayer")


if __name__ == "__main__":
    run()
