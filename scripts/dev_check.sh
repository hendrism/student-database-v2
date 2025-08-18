#!/bin/bash
set -e
python3 -m py_compile $(git ls-files '*.py')
pytest -q
