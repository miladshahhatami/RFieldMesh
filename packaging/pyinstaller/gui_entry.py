"""PyInstaller entry point kept outside the importable package."""

from rfieldmesh.gui.application import main

if __name__ == "__main__":
    raise SystemExit(main())
