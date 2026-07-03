"""
baixar_trecho.py
────────────────
Passo 3 do Pipeline Canal Cortes.

Baixa apenas o trecho exato do vídeo (do pico de replay)
usando yt-dlp com --download-sections.

Técnicas anti-bloqueio aplicadas:
  - curl-cffi: TLS fingerprint de Chrome real
  - player_client múltiplo: web > android > tv_downgraded
  - cookies autenticados (via ytdlp_helper)
  - Deno para JS challenges (instalado pelo workflow)
  - 3 tentativas com fallback automático de qualidade
"""

import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ytdlp_helper import args_base_ytdlp

ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")


def baixar_trecho(video_url: str, inicio_s: float, fim_s: float, output_dir: str = OUTPUT_DIR) -> str:
    """
    Baixa o trecho [inicio_s, fim_s] do vídeo com múltiplas camadas anti-bloqueio.

    Args:
        video_url : URL completa do vídeo do YouTube
        inicio_s  : segundo de início do trecho
        fim_s     : segundo de fim do trecho
        output_dir: pasta de saída

    Returns:
        Caminho do arquivo MP4 baixado.
    """
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "tmp"), exist_ok=True)

    trecho_str  = f"*{_formatar_tempo(inicio_s)}-{_formatar_tempo(fim_s)}"
    output_path = os.path.join(output_dir, "trecho_original.mp4")

    print(f"  ⬇️  Baixando trecho {_formatar_tempo(inicio_s)} → {_formatar_tempo(fim_s)}...")
    print(f"     URL: {video_url}")

    # ── Estratégias em ordem de qualidade/confiabilidade ─────────────────────
    tentativas = [
        {
            "desc": "1080p + anti-bot completo (WARP + curl-cffi + cookies)",
            "cmd": args_base_ytdlp([
                "--download-sections", trecho_str,
                "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
                "--merge-output-format", "mp4",
                "-o", output_path,
                "--quiet",
            ]) + [video_url],
        },
        {
            "desc": "Qualidade melhor disponível (sem impersonation)",
            "cmd": [
                "yt-dlp",
                "--download-sections", trecho_str,
                "--extractor-args", "youtube:player_client=web,android,tv_downgraded",
                "-f", "best[height<=1080]/best",
                "--merge-output-format", "mp4",
                "-o", output_path,
                "--no-playlist", "--no-warnings", "--quiet",
                video_url,
            ],
        },
        {
            "desc": "Fallback absoluto (tv_downgraded, qualquer formato)",
            "cmd": [
                "yt-dlp",
                "--download-sections", trecho_str,
                "--extractor-args", "youtube:player_client=tv_downgraded",
                "-f", "best",
                "--merge-output-format", "mp4",
                "-o", output_path,
                "--no-playlist", "--no-warnings", "--quiet",
                video_url,
            ],
        },
    ]

    for t in tentativas:
        print(f"  🔄 {t['desc']}...")
        resultado = subprocess.run(t["cmd"], capture_output=True, text=True, timeout=600)

        if resultado.returncode == 0:
            # Verifica se o arquivo existe (pode ter extensão diferente)
            arquivo = _encontrar_arquivo(output_path)
            if arquivo:
                tamanho_mb = os.path.getsize(arquivo) / (1024 * 1024)
                print(f"  ✅ Trecho baixado: {arquivo} ({tamanho_mb:.1f} MB)")
                return arquivo

        print(f"  ⚠️  Falhou: {resultado.stderr[-150:]}")

    raise RuntimeError(
        f"Todas as tentativas de download falharam para: {video_url}\n"
        f"Último erro: {tentativas[-1]['cmd']}"
    )


def _encontrar_arquivo(output_path: str) -> str | None:
    """Busca o arquivo gerado mesmo se a extensão for diferente do esperado."""
    if os.path.exists(output_path):
        return output_path
    for ext in [".mp4", ".mkv", ".webm", ".m4v"]:
        alt = output_path.rsplit(".", 1)[0] + ext
        if os.path.exists(alt):
            return alt
    return None


def _formatar_tempo(segundos: float) -> str:
    """Converte segundos para formato HH:MM:SS.mmm usado pelo yt-dlp."""
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = segundos % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


if __name__ == "__main__":
    url      = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=example"
    inicio_s = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
    fim_s    = float(sys.argv[3]) if len(sys.argv) > 3 else 660.0
    caminho  = baixar_trecho(url, inicio_s, fim_s)
    print(f"Arquivo: {caminho}")
