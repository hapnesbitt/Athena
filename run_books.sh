#!/bin/bash
# Run Books 1-12 sequentially, logging each to its own log file.
# Usage: bash run_books.sh
# Watch: tail -f clb_run.log (updates per book)

set -e
cd "$(dirname "$0")"

BOOKS="1 2 3 4 5 6 7 8 9 10 11 12"

for book in $BOOKS; do
    echo ""
    echo "========================================"
    echo "  Starting Book $book — $(date)"
    echo "========================================"
    python3 scribe.py $book
    cp clb_run.log "clb_run_book${book}.log"
    echo "  Book $book complete. Log saved to clb_run_book${book}.log"
done

echo ""
echo "========================================"
echo "  ALL 12 BOOKS COMPLETE — $(date)"
echo "========================================"
