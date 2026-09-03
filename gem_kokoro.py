#!/usr/bin/env python3
import os
import sys
import torch
from kokoro import KPipeline
from IPython.display import Audio

INPUT_FILE = sys.argv[1] if len(sys.argv) > 1 else "ATHENA_manuscript.md"
AUDIOBOOK_OUT = "athena_audiobook.wav"

def generate_audio():
    print(f"[*] Reading manuscript from {INPUT_FILE}...")
    if not os.path.exists(INPUT_FILE):
        print(f"[!] Error: {INPUT_FILE} not found.")
        sys.exit(1)
        
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        text = f.read()

    print("[*] Initializing Kokoro pipeline (cuda/gpu)...")
    # lang_code 'a' for American English, or 'b' for British English
    pipeline = KPipeline(lang_code='a')

    print("[*] Generating speech locally via Kokoro...")
    # Using a standard voice like 'af_sarah' or 'am_adam'
    generator = pipeline(text, voice='af_sarah', speed=1.0, split_pattern=r'\n+')

    import soundfile as sf
    all_audio = []
    
    for i, (gs, ps, audio) in enumerate(generator):
        print(f"[{i}] Generated segment length: {len(audio)}")
        all_audio.append(audio)

    if all_audio:
        import numpy as np
        combined_audio = np.concatenate(all_audio)
        sf.write(AUDIOBOOK_OUT, combined_audio, 24000)
        print(f"[*] Kokoro audiobook compiled successfully to {AUDIOBOOK_OUT}")
    else:
        print("[!] Warning: No audio generated.")

if __name__ == "__main__":
    generate_audio()
