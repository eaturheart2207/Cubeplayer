# cubeplayer

`cubeplayer` is a lightweight terminal music player that plays local audio files directly from the command line. It focuses on simplicity and a clean user experience, providing basic playback controls without unnecessary complexity. Great for quick listening sessions when you don’t want to open a full GUI player.

## Features
- Simple command-line usage
- Minimal interface
- Plays local audio files
- Designed for quick and distraction-free playback

## Installation
Make sure Python 3 is installed. Required packages will be installed automatically on first run:

```bash
./cubeplayer path/to/song.mp3
```

(Windows: use `cubeplayer.cmd` or `cubeplayer.ps1`)

### Disclaimer
Installation scripts may not work in all environments. If the launcher scripts fail, run the player directly with Python and install dependencies manually:

```bash
python3 -m pip install --user pygame mutagen
python3 ascii_player.py path/to/song.mp3
```

## Usage

```bash
./cubeplayer "music/track.mp3"
```

You can pass any local audio file supported by your system libraries.

## Controls
- **Space** — Play/Pause
- **Up/Down** — Move selection
- **Enter** — Play selected
- **Left/Right** — Seek ±5s
- **n / p** — Next / Previous track
- **s** — Stop
- **r** — Toggle repeat
- **h** — Toggle shuffle
- **b** — Browse folder
- **k** — Toggle keys panel
- **+ / -** — Volume up/down
- **q** — Quit

## Music tags
Tag display requires the optional `mutagen` package. If you see “Tags unavailable”, install it:

```bash
python3 -m pip install --user mutagen
```

## Screenshot


<img width="1920" height="1080" alt="изображение" src="https://github.com/user-attachments/assets/0a48f6d7-17b9-4eff-a03e-2810fb3df4b1" />


---

# Русский

`cubeplayer` — это лёгкий терминальный музыкальный плеер для воспроизведения локальных аудиофайлов прямо из командной строки. Он делает упор на простоту и удобство, предоставляя базовые элементы управления без лишней сложности. Отлично подходит для быстрого прослушивания, когда не хочется запускать графический плеер.

## Возможности
- Простой запуск из командной строки
- Минималистичный интерфейс
- Воспроизведение локальных аудиофайлов
- Для быстрого и ненавязчивого прослушивания

## Установка
Нужен Python 3. Зависимости устанавливаются автоматически при первом запуске:

```bash
./cubeplayer путь/к/треку.mp3
```

(Windows: используйте `cubeplayer.cmd` или `cubeplayer.ps1`)

### Дисклеймер
Скрипты установки могут не работать в некоторых окружениях. Если запуск через скрипты не работает, запустите плеер напрямую через Python и установите зависимости вручную:

```bash
python3 -m pip install --user pygame mutagen
python3 ascii_player.py путь/к/треку.mp3
```

## Использование

```bash
./cubeplayer "music/track.mp3"
```

Поддерживается любой локальный аудиофайл, который может воспроизвести ваша система.

## Управление
- **Space** — Пауза/воспроизведение
- **Up/Down** — Перемещение по списку
- **Enter** — Запустить выбранный трек
- **Left/Right** — Перемотка ±5 сек
- **n / p** — Следующий / предыдущий трек
- **s** — Стоп
- **r** — Повтор
- **h** — Перемешивание
- **b** — Выбор папки
- **k** — Показать/скрыть подсказки
- **+ / -** — Громкость
- **q** — Выход

## Теги музыки
Отображение тегов требует опциональный пакет `mutagen`. Если видишь “Tags unavailable”, установи его:

```bash
python3 -m pip install --user mutagen
```

## Скриншот


<img width="1920" height="1080" alt="изображение" src="https://github.com/user-attachments/assets/b0e75cb3-afa4-4986-b92d-814d55ae9c78" />
