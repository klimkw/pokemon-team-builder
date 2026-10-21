"""Read the release version from the project's existing source of truth."""
from pathlib import Path
import tomllib

APP_VERSION = tomllib.loads((Path(__file__).parents[1] / 'pyproject.toml').read_text())['project']['version']
