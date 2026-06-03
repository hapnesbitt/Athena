#!/bin/bash
cd "$(dirname "$0")" || exit 1
python3 polish.py all
echo "Polish complete. Compare scene_bookN.md vs scene_bookN_polished.md"
