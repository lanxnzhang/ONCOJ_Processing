from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = APP_ROOT.parent
SOURCE_XML = REPOSITORY_ROOT / "data" / "xml"
WORKSPACE = APP_ROOT / "workspace"
COLLECTIONS = ("text", "trees")

