# Instant Easel (drawing app): where everything is

```
Instant Easel/
├── main.py                  start here: the window, logo, splash/load bar, the two tabs
├── PaintEngine.spec         how the .exe is built (PyInstaller)
├── build_windows.bat        build the .exe on your own PC (double-click)
├── requirements.txt         what Python needs: numpy, scipy, Pillow
├── EXE Build/               InstantEasel.exe (rebuilt by GitHub every time the code changes)
├── systems/
│   ├── Core/                shared by everything: theme, skins, prefs, paths, crash recovery, shortcuts, tab list
│   ├── Drawing/             the drawing studio (canvas, tools, layers, colour)
│   │   └── Brushes/         the brushes, brush catalog, brush window, custom-brush naming
│   └── Settings/            the Settings pages (General, Display, Shortcuts, Backup & Reset)
├── images/UI/               every picture the app shows, sorted by the area it belongs to
├── fonts/                   the app's fonts
├── .json/                   your theme and settings
├── logs/                    error log, crash log, test results
├── tests/                   full_app_test.py: clicks through the whole app
└── docs/                    this file
```

Tabs: **Drawing** (the studio fills the whole page; no side menu) and **Settings** (Theme, General, Display, Shortcuts, Backup & Reset, About).

The full app with the AI tabs is the separate **Instant Easel Pro** folder.
