#!/bin/bash
# Run Books 13-24 sequentially, log-and-continue.
# Usage: bash run_books_back.sh
cd "$(dirname "$0")" || exit 1

BOOKS="13 14 15 16 17 18 19 20 21 22 23 24"
FAILED=""

for book in $BOOKS; do
    echo ""
    echo "========================================"
    echo "  Starting Book $book — $(date)"
    echo "========================================"
    if python3 scribe.py $book; then
        cp clb_run.log "clb_run_book${book}.log"
        echo "  Book $book complete. Log saved to clb_run_book${book}.log"
    else
        rc=$?
        FAILED="$FAILED $book"
        [ -f clb_run.log ] && cp clb_run.log "clb_run_book${book}.log"
        echo "  !! Book $book FAILED (exit $rc) — continuing"
    fi
done

echo ""
echo "========================================"
if [ -z "$FAILED" ]; then
    echo "  ALL 12 BOOKS COMPLETE — $(date)"
else
    echo "  ALL 12 BOOKS ATTEMPTED — $(date)"
    echo "  FAILED books:$FAILED"
fi
echo "========================================"
