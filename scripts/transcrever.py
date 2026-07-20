"""
transcrever.py
──────────────
Passo 4 do Pipeline Canal Cortes.

Transcreve o áudio do trecho baixado usando Groq Whisper
(whisper-large-v3-turbo) e gera arquivo SRT com timestamps precisos.

Baseado no sistema de legendas do Canal Oração, adaptado para:
  - Áudio de podcast com múltiplos falantes
  - Segmentos maiores (1-2 min)
  - Blocos de 5-7 palavras por legenda (ideal para Shorts verticais)
"""

import os
import subprocess
import json
import re

from groq import Groq

ROOT_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PALAVRAS_BLOCO = 3   # Palavras por bloco de legenda (ideal para Shorts com fonte grande)


def _extrair_audio(video_path: str, output_dir: str) -> str:
    """Extrai apenas o áudio do vídeo para envio ao Groq."""
    audio_path = os.path.join(output_dir, "audio_trecho.mp3")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",               # Sem vídeo
        "-ar", "16000",      # 16kHz — ideal para Whisper
        "-ac", "1",          # Mono
        "-b:a", "64k",
        audio_path,
    ]
    resultado = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if resultado.returncode != 0:
        raise RuntimeError(f"FFmpeg falhou ao extrair áudio:\n{resultado.stderr[-300:]}")
    return audio_path


def _segundos_para_srt(segundos: float) -> str:
    """Converte segundos para formato HH:MM:SS,mmm do SRT."""
    h   = int(segundos // 3600)
    m   = int((segundos % 3600) // 60)
    s   = int(segundos % 60)
    ms  = int(round((segundos - int(segundos)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcrever(video_path: str, output_dir: str) -> tuple:
    """
    Transcreve o vídeo e gera legendas SRT.

    Args:
        video_path : caminho do vídeo MP4
        output_dir : pasta de saída

    Returns:
        (texto_completo: str, srt_path: str)
    """
    os.makedirs(output_dir, exist_ok=True)

    # Extrai áudio (mais leve para enviar à API)
    print("  🎵 Extraindo áudio para transcrição...")
    audio_path = _extrair_audio(video_path, output_dir)
    tamanho_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"     Áudio: {audio_path} ({tamanho_mb:.1f} MB)")

    # Transcrição via Groq Whisper
    print("  🎙️  Transcrevendo com Groq Whisper (whisper-large-v3-turbo)...")
    cliente = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    with open(audio_path, "rb") as f:
        transcricao = cliente.audio.transcriptions.create(
            file=("audio_trecho.mp3", f.read()),
            model="whisper-large-v3-turbo",
            response_format="verbose_json",
            language="pt",
        )

    # Extrai segmentos (suporte a dict e objeto SDK)
    if isinstance(transcricao, dict):
        segmentos   = transcricao.get("segments", [])
        texto_total = transcricao.get("text", "")
    else:
        segmentos   = getattr(transcricao, "segments", [])
        texto_total = getattr(transcricao, "text", "")

    print(f"  ✅ {len(segmentos)} segmentos transcritos")
    print(f"     Texto: {texto_total[:100]}...")

    # Gera SRT com blocos de N palavras
    srt_path  = os.path.join(output_dir, "legendas.srt")
    linhas    = []
    idx       = 1

    for seg in segmentos:
        try:
            start = seg.start if hasattr(seg, "start") else seg["start"]
            end   = seg.end   if hasattr(seg, "end")   else seg["end"]
            texto = seg.text  if hasattr(seg, "text")  else seg["text"]
        except (AttributeError, KeyError):
            continue

        texto = texto.strip()
        if not texto:
            continue

        palavras       = texto.split()
        duracao_total  = end - start
        tempo_palavra  = duracao_total / len(palavras) if palavras else 0.1

        for i in range(0, len(palavras), PALAVRAS_BLOCO):
            bloco      = palavras[i: i + PALAVRAS_BLOCO]
            texto_bloco= " ".join(bloco).upper()
            t_inicio   = start + i * tempo_palavra
            t_fim      = start + (i + len(bloco)) * tempo_palavra

            linhas.append(
                f"{idx}\n"
                f"{_segundos_para_srt(t_inicio)} --> {_segundos_para_srt(t_fim)}\n"
                f"{texto_bloco}\n"
            )
            idx += 1

    srt_content = "\n".join(linhas)

    # Fallback mínimo se falhou
    if not srt_content.strip():
        srt_content = "1\n00:00:00,000 --> 00:00:05,000\n \n"

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    print(f"  ✅ Legendas SRT salvas: {srt_path} ({idx-1} blocos)")

    # Remove áudio temporário
    if os.path.exists(audio_path):
        os.remove(audio_path)

    return texto_total, srt_path


if __name__ == "__main__":
    import sys
    video = sys.argv[1] if len(sys.argv) > 1 else "output/trecho_original.mp4"
    texto, srt = transcrever(video, "output")
    print(f"\nTexto:\n{texto[:500]}")
    print(f"\nSRT: {srt}")

