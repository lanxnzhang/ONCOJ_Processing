"""pytest configuration — add src/ to sys.path and expose shared fixtures."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

DATA_DIR  = os.path.join(os.path.dirname(__file__), "..", "data", "txt")
DICT_FILE = os.path.join(DATA_DIR, "dict", "dictionary.txt")
TEXT_DIR  = os.path.join(DATA_DIR, "text")


@pytest.fixture(scope="session")
def dict_file():
    return DICT_FILE


@pytest.fixture(scope="session")
def text_dir():
    return TEXT_DIR


@pytest.fixture(scope="session")
def sample_corpus_file():
    return os.path.join(TEXT_DIR, "EN_01.txt")
