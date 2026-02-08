import os
from pathlib import Path

def get_project_root() -> Path:
    """Returns the absolute path to the project root directory."""
    # This assumes the file is in 'src/'
    return Path(__file__).resolve().parent.parent

PROJECT_ROOT = get_project_root()
