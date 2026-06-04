#!/bin/bash
cd /home/www/Athena_clb
python3 build_athena_site.py ATHENA_manuscript.md site images
echo "Rebuilt → https://athena.arc-codex.com"
