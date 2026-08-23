"""
transcrever.py
──────────────
Passo 4 do Pipeline Canal Cortes.

Transcreve o áudio do trecho baixado usando faster-whisper
e gera arquivo SRT com timestamps precisos.
"""

import os
import subprocess
from faster_whisper import WhisperModel

ROOT_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PALAVRAS_BLOCO = 3   # Palavras por bloco de legenda

def _extrair_audio(video_path: str, output_dir: str) -> str:
    audio_path = os.path.join(output_dir, "audio_trecho.mp3")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-ar", "16000",
        "-ac", "1",
        "-b:a", "64k",
        audio_path,
    ]
    resultado = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if resultado.returncode != 0:
        raise RuntimeError(f"FFmpeg falhou ao extrair áudio:\n{resultado.stderr[-300:]}")
    return audio_path

def _segundos_para_srt(segundos: float) -> str:
    h   = int(segundos // 3600)
    m   = int((segundos % 3600) // 60)
    s   = int(segundos % 60)
    ms  = int(round((segundos - int(segundos)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def transcrever(video_path: str, output_dir: str) -> tuple:
    os.makedirs(output_dir, exist_ok=True)

    print("  🎵 Extraindo áudio para transcrição...")
    audio_path = _extrair_audio(video_path, output_dir)
    tamanho_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"     Áudio: {audio_path} ({tamanho_mb:.1f} MB)")

    print("  🎙️  Transcrevendo com faster-whisper (modelo base)...")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, language="pt", beam_size=5)

    linhas    = []
    idx       = 1
    texto_total_list = []

    for seg in segments:
        texto_total_list.append(seg.text)
        texto = seg.text.strip()
        if not texto: continue

        palavras       = texto.split()
        duracao_total  = seg.end - seg.start
        tempo_palavra  = duracao_total / len(palavras) if palavras else 0.1

        for i in range(0, len(palavras), PALAVRAS_BLOCO):
            bloco      = palavras[i: i + PALAVRAS_BLOCO]
            texto_bloco= " ".join(bloco).upper()
            t_inicio   = seg.start + i * tempo_palavra
            t_fim      = seg.start + (i + len(bloco)) * tempo_palavra

            linhas.append(
                f"{idx}\n"
                f"{_segundos_para_srt(t_inicio)} --> {_segundos_para_srt(t_fim)}\n"
                f"{texto_bloco}\n"
            )
            idx += 1

    srt_content = "\n".join(linhas)
    texto_total = " ".join(texto_total_list)

    if not srt_content.strip():
        srt_content = "1\n00:00:00,000 --> 00:00:05,000\n \n"

    srt_path  = os.path.join(output_dir, "legendas.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    print(f"  ✅ Legendas SRT salvas: {srt_path} ({idx-1} blocos)")
    if os.path.exists(audio_path):
        os.remove(audio_path)

    return texto_total, srt_path

if __name__ == "__main__":
    import sys
    video = sys.argv[1] if len(sys.argv) > 1 else "output/trecho_original.mp4"
    texto, srt = transcrever(video, "output")
    print(f"\nTexto:\n{texto[:500]}")
    print(f"\nSRT: {srt}")
