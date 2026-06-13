# 🧱 Voxel Sandbox

Prosta gra sandbox w stylu Minecraft napisana w Pythonie z użyciem silnika [Ursina Engine](https://www.ursinaengine.org/). Projekt zrobiony w celach nauki — eksperymentowanie z grafiką 3D, chunk meshingiem i fizyką gracza w Pythonie.

## Funkcje

- generowanie terenu z chunków (grass / dirt / stone)
- stawianie i niszczenie bloków (8 typów)
- zapis i wczytywanie świata z pliku JSON
- tryb latania (`F`)
- vertex shading — każda ściana bloku ma inny odcień
- hotbar z wyborem bloku kółkiem myszy lub klawiszami 1–8

## Sterowanie

| Klawisz | Akcja |
|---|---|
| `WSAD` | ruch |
| `LPM` | usuń blok |
| `PPM` | postaw blok |
| `1–8` / scroll | zmień blok |
| `F` | włącz/wyłącz latanie |
| `P` | zapisz świat |
| `F11` | pełny ekran |

## Uruchomienie

```bash
pip install ursina
python voxel.py
```

## Technologie

- Python 3.10+
- [Ursina Engine](https://www.ursinaengine.org/)

## Uwagi

Projekt zrobiony głównie do nauki Pythona i podstaw grafiki 3D. Przy pisaniu kodu wspomagałem się modelami AI
