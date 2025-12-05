"""
Convenience entrypoint for the VortexAI portable assistant.

Allows running `python main.py` in addition to `python -m vortex_portable`.
"""

from vortex_portable.cli import main


if __name__ == "__main__":
    main()
