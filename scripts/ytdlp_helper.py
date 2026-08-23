"""
ytdlp_helper.py
────────────────
Módulo central de configuração do yt-dlp.

Constroi dois conjuntos de args separados:
  1. args_base_ytdlp()         — para DOWNLOAD de vídeos (player_client=mweb,android)
  2. args_base_ytdlp_listing() — para LISTAGEM de canais (player_client=web)

A separação é necessária pois:
  - mweb/android bypassa bot-check no download mas não suporta flat-playlist
  - web suporta listagem de canais mas é mais bloqueado para downloads
"""

import os

# Caminho canônico do cookies.txt (raiz do projeto ou diretório de trabalho)
_COOKIES_PATHS = [
    "cookies.txt",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cookies.txt"),
]


def _cookies_path() -> str | None:
    """Retorna o caminho do cookies.txt se existir."""
    for p in _COOKIES_PATHS:
        if os.path.exists(p) and os.path.getsize(p) > 100:
            return p
    return None


def args_base_ytdlp(extra: list = None) -> list:
    """
    Args para DOWNLOAD de vídeos individuais.
    Usa mweb,android que bypassa bot-check em IPs de datacenter.
    NÃO usar para listagem de canais/playlists.
    """
    cmd = [
        "yt-dlp",
        # ── Anti-bot: mweb é menos detectado em IPs de datacenter ──────────────
        "--extractor-args", "youtube:player_client=mweb,android",
        # ── Simular user-agent de mobile para reforçar o mweb ──────────────────
        "--add-headers", "User-Agent:Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        # ── Não poluir output ────────────────────────────────────────────────
        "--no-warnings",
        "--no-playlist",
    ]

    cookies = _cookies_path()
    if cookies:
        cmd.extend(["--cookies", cookies])
        print(f"    🍪 Usando cookies: {cookies}")
    else:
        print("    ⚠️  Sem cookies.txt — usando sessão anônima")

    if extra:
        cmd.extend(extra)

    return cmd


def args_base_ytdlp_listing(extra: list = None) -> list:
    """
    Args para LISTAGEM de canais e playlists.
    Usa player_client=web que suporta flat-playlist corretamente.
    NÃO usar para download de vídeos individuais em servidores (será bloqueado).
    """
    cmd = [
        "yt-dlp",
        # ── web é o único que suporta listagem de canais/playlists ────────────
        "--extractor-args", "youtube:player_client=web",
        "--no-warnings",
    ]

    cookies = _cookies_path()
    if cookies:
        cmd.extend(["--cookies", cookies])
        print(f"    🍪 Usando cookies: {cookies}")
    else:
        print("    ⚠️  Sem cookies.txt — usando sessão anônima")

    if extra:
        cmd.extend(extra)

    return cmd


def args_download_ytdlp(trecho_str: str, output_path: str, extra: list = None) -> list:
    """
    Argumentos completos para download de trecho de vídeo.

    Args:
        trecho_str  : ex '*00:10:00.000-00:11:00.000'
        output_path : caminho do arquivo de saída
        extra       : argumentos extras antes da URL
    """
    cmd = args_base_ytdlp()

    cmd += [
        "--download-sections", trecho_str,
        # Qualidade: 1080p com áudio (forçando H.264/AVC para garantir suporte no OpenCV)
        "-f", "bestvideo[ext=mp4][vcodec^=avc][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]/best",
        "--merge-output-format", "mp4",
        "--recode-video", "mp4",  # Garante re-encode para h264 caso não venha nativo
        "-o", output_path,
    ]

    if extra:
        cmd.extend(extra)

    return cmd

