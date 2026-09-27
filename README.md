# UE4 Mod Launcher

A desktop launcher for games built with Unreal Engine 4 that manage
their mods using `.pak` files. Instead of manually copying and pasting mods
into the game's `~mods` folder every time you want to play (and moving them
back out afterwards), the app handles this automatically, using a separate
profile for each game.

## What does it do?

- **Per-game profiles**: Each profile stores the path to the game's `.exe`,
the path to its `Paks` folder, and its own collection of mods.
- **Automatic deployment**: When you click "Play," the launcher moves the
profile's `.pak` files to the game's `~mods` folder, launches the executable,
waits for the game to close, and moves the mods back to the profile folder—all
without manual intervention.
- **Crash recovery**: If the launcher closes unexpectedly (crash, power
outage, forced shutdown) while mods were deployed, it automatically
recovers them the next time it opens, rather than leaving them stranded
inside the game folder.
- **In-app mod management**: Includes a button to add `.pak` files directly
(they are copied to the profile without altering the original) and another
to open the profile's mod folder in File Explorer.
- **Multilingual support**: Interface available in Spanish and English,
switchable via Settings.
- **AppData storage**: Profiles and settings are saved in
`%LOCALPDATA%\UE4ModLauncher`; operation does not depend on the `.exe`
location or require administrator privileges. ## Requirements

- Python 3.10+ (only if running or building from source)
- See `requirements.txt`:
- `customtkinter` — graphical user interface
- `Pillow` — for displaying the logo within the app
- `psutil` *(optional, recommended)* — allows for more reliable detection
of when the game has actually closed, even for titles that use a
"launcher" executable that starts the actual game and then closes itself

## Usage

1. Open the app and click **➕ New** to create a profile.
2. Select it from the dropdown menu: its settings will appear on the right.
3. Enter the path to the game's `.exe` and its `Paks` folder, then click
**Save** (or simply switch profiles / close the app — it saves
automatically).
4. Use **➕ Add mods** to include your `.pak` files in the profile.
5. Click **▶ Start game**.

## Building the .exe

```
pyinstaller --noconfirm --clean --onefile --windowed --icon=icon.ico --add-data "logo.png;." --add-data "icon.ico;." --name "UE4ModLauncher" main.py
```

The resulting executable is located at `dist\UE4ModLauncher.exe`.

## Project Structure

- `main.py` — graphical user interface (CustomTkinter)
- `core.py` — profile logic, mod moving, and game launching
- `config.py` — data paths, bundled resources (logo/icon), and interface
text (ES/EN)

## License

This project is distributed under the MIT License. See the
[`LICENSE`](LICENSE) file for details.

## Disclaimer

This launcher is an unofficial third-party tool. It is not affiliated with Epic Games or the developers of the games with which it is used. The use of mods may violate the terms of service of some games—check the rules before using it, especially for titles with anti-cheat systems or competitive multiplayer.
