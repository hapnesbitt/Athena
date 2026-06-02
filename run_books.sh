#!/bin/bash
# Run Books 1-12 sequentially, logging each to its own log file.
# Log-and-continue: if a book hiccups it is recorded and the run keeps going,
# so all 12 attempt unattended even if one fails.
# Usage: bash run_books.sh
# Watch: tail -f clb_run.log (updates per book)

cd "$(dirname "$0")" || exit 1

BOOKS="1 2 3 4 5 6 7 8 9 10 11 12"
FAILED=""

for book in $BOOKS; do
    echo ""
    echo "========================================"
    echo "  Starting Book $book — $(date)"
    echo "========================================"
    if python3 scribe.py "$book"; then
        cp clb_run.log "clb_run_book${book}.log"
        echo "  Book $book complete. Log saved to clb_run_book${book}.log"
    else
        status=$?
        cp clb_run.log "clb_run_book${book}.log" 2>/dev/null
        echo "  !! Book $book FAILED (exit $status) — continuing. Log saved to clb_run_book${book}.log"
        FAILED="$FAILED $book"
    fi
done

echo ""
echo "========================================"
if [ -n "$FAILED" ]; then
    echo "  ALL 12 BOOKS ATTEMPTED — $(date)"
    echo "  FAILED books:$FAILED"
else
    echo "  ALL 12 BOOKS COMPLETE — $(date)"
fi
echo "========================================"
