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

Fix A/V sync:
  Após o download, normaliza os PTS via FFmpeg para evitar o delay
  de áudio/vídeo nos primeiros segundos do clipe.
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
        Caminho do arquivo MP4 baixado e com timestamps normalizados.
    """
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "tmp"), exist_ok=True)

    trecho_str  = f"*{_formatar_tempo(inicio_s)}-{_formatar_tempo(fim_s)}"
    output_path = os.path.join(output_dir, "trecho_original.mp4")

    print(f"  ⬇️  Baixando trecho {_formatar_tempo(inicio_s)} → {_formatar_tempo(fim_s)}...")
    print(f"     URL: {video_url}")

    # ── Estratégias em ordem de qualidade/confiabilidade ─────────────────────
    # NOTA: Removido --downloader-args "ffmpeg:-async 1" de todas as tentativas.
    # O -async 1 causava audio stretching. A sincronização é feita pelo passo
    # _sincronizar_timestamps() após o download, que é mais robusto.
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
                # ── Normaliza timestamps para evitar delay A/V no início ──────
                arquivo = _sincronizar_timestamps(arquivo, output_dir)
                return arquivo

        print(f"  ⚠️  Falhou: {resultado.stderr[-150:]}")

    raise RuntimeError(
        f"Todas as tentativas de download falharam para: {video_url}\n"
        f"Último erro: {tentativas[-1]['cmd']}"
    )


def _sincronizar_timestamps(input_path: str, output_dir: str) -> str:
    """
    Normaliza os PTS (presentation timestamps) do arquivo baixado.

    Problema: ao usar --download-sections, o yt-dlp corta o vídeo a partir
    do keyframe anterior ao ponto solicitado, mas o áudio começa no ponto
    exato. Isso gera um offset de A/V nos primeiros segundos do clipe —
    as pessoas aparecem mexendo a boca antes do som chegar.

    Solução: '-avoid_negative_ts make_zero' + '-fflags +genpts' zeram os
    timestamps negativos e regeneram os PTS, alinhando vídeo e áudio ao
    mesmo ponto de início sem re-encode (cópia direta de streams).
    Resultado: rápido e sem perda de qualidade.

    Args:
        input_path : caminho do arquivo baixado
        output_dir : pasta de saída (tmp/)

    Returns:
        Caminho do arquivo sincronizado (mesmo input_path, substituído).
    """
    tmp_path = os.path.join(output_dir, "tmp", "_sync_tmp.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        "-fflags", "+genpts",
        tmp_path,
    ]
    print("  🔧 Normalizando timestamps A/V (avoid_negative_ts + genpts)...")
    resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if resultado.returncode == 0 and os.path.exists(tmp_path):
        # Substitui o original pelo arquivo sincronizado
        os.replace(tmp_path, input_path)
        tamanho_mb = os.path.getsize(input_path) / (1024 * 1024)
        print(f"  ✅ A/V sync corrigido: {input_path} ({tamanho_mb:.1f} MB)")
    else:
        # Se falhar, mantém o original sem crash (etapa opcional de qualidade)
        print(f"  ⚠️  Normalização de timestamps falhou (mantendo original): {resultado.stderr[-150:]}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return input_path


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
