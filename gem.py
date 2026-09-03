#!/usr/bin/env python3
import os
import sys
import subprocess
import edge_tts
asyncio = __import__('asyncio')

# Configuration - accept input file from command line argument if provided
AUDIOBOOK_OUT = "athena_audiobook.mp3"
INPUT_FILE = sys.argv[1] if len(sys.argv) > 1 else "ATHENA_manuscript.md"

def synthesize_speech():
    print(f"[*] Reading text directly from {INPUT_FILE}...")
    if not os.path.exists(INPUT_FILE):
        print(f"[!] Error: {INPUT_FILE} not found.")
        sys.exit(1)
        
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        text = f.read()
        
    print("[*] Generating text-to-speech audio via edge-tts...")
    voice = "en-US-ChristopherNeural"
    
    async def run_tts():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(AUDIOBOOK_OUT)
        
    asyncio.run(run_tts())
    print(f"[*] Audiobook compiled successfully to {AUDIOBOOK_OUT}")

if __name__ == "__main__":
    synthesize_speech()
