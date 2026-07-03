"""
ytdlp_helper.py
────────────────
Módulo central de configuração do yt-dlp.

Constrói os argumentos base com as técnicas anti-bloqueio mais atuais (2026):
  1. player_client=web,android,tv_downgraded  — múltiplos clientes em fallback
  2. --impersonate chrome  — TLS fingerprint de browser real (via curl-cffi)
  3. --cookies cookies.txt — sessão autenticada do usuário
  4. Deno disponível no PATH — yt-dlp usa automaticamente para JS challenges

Todos os scripts de download importam daqui para manter consistência.
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
    Retorna a lista de argumentos base robusta para o yt-dlp.

    Camadas anti-bloqueio:
      1. player_client múltiplo: web > android > tv_downgraded
      2. TLS impersonation (curl-cffi): mimics real Chrome request
      3. cookies autenticados se disponíveis
      4. Deno no PATH para JS challenges (GitHub Actions instala via setup-deno)

    Args:
        extra: argumentos extras a adicionar ANTES da URL

    Returns:
        lista de args prontos para subprocess.run
    """
    cmd = [
        "yt-dlp",
        # ── Anti-bot: múltiplos clientes em ordem de confiabilidade ──────────
        "--extractor-args", "youtube:player_client=web,android,tv_downgraded",
        # ── TLS fingerprint de browser real (requer curl-cffi instalado) ──────
        "--impersonate", "chrome",
        # ── Não poluir output ────────────────────────────────────────────────
        "--no-warnings",
        "--no-playlist",
    ]

    # ── Cookies autenticados ──────────────────────────────────────────────────
    cookies = _cookies_path()
    if cookies:
        cmd.extend(["--cookies", cookies])
        print(f"    🍪 Usando cookies: {cookies}")
    else:
        print("    ⚠️  Sem cookies.txt — usando sessão anônima")

    # ── Argumentos extras ─────────────────────────────────────────────────────
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
        # Qualidade: 1080p com áudio, fallback para melhor disponível
        "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "--merge-output-format", "mp4",
        "-o", output_path,
    ]

    if extra:
        cmd.extend(extra)

    return cmd
