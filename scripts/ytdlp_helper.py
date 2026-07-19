"""
ytdlp_helper.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
MÃ³dulo central de configuraÃ§Ã£o do yt-dlp.

ConstrÃ³i os argumentos base com as tÃ©cnicas anti-bloqueio mais atuais (2026):
  1. player_client=web,android,tv_downgraded  â€” mÃºltiplos clientes em fallback
  2. --impersonate chrome  â€” TLS fingerprint de browser real (via curl-cffi)
  3. --cookies cookies.txt â€” sessÃ£o autenticada do usuÃ¡rio
  4. Deno disponÃ­vel no PATH â€” yt-dlp usa automaticamente para JS challenges

Todos os scripts de download importam daqui para manter consistÃªncia.
"""

import os

# Caminho canÃ´nico do cookies.txt (raiz do projeto ou diretÃ³rio de trabalho)
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
      1. player_client mÃºltiplo: web > android > tv_downgraded
      2. TLS impersonation (curl-cffi): mimics real Chrome request
      3. cookies autenticados se disponÃ­veis
      4. Deno no PATH para JS challenges (GitHub Actions instala via setup-deno)

    Args:
        extra: argumentos extras a adicionar ANTES da URL

    Returns:
        lista de args prontos para subprocess.run
    """
    cmd = [
        "yt-dlp",
        # â”€â”€ Anti-bot: mÃºltiplos clientes em ordem de confiabilidade â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        "--extractor-args", "youtube:player_client=web,android,tv_downgraded",
        # â”€â”€ TLS fingerprint de browser real (requer curl-cffi instalado) â”€â”€â”€â”€â”€â”€
        "--impersonate", "chrome",
        # â”€â”€ NÃ£o poluir output â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        "--no-warnings",
        "--no-playlist",
    ]

    # â”€â”€ Cookies autenticados â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    cookies = _cookies_path()
    if cookies:
        cmd.extend(["--cookies", cookies])
        print(f"    ðŸª Usando cookies: {cookies}")
    else:
        print("    âš ï¸  Sem cookies.txt â€” usando sessÃ£o anÃ´nima")

    # â”€â”€ Argumentos extras â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if extra:
        cmd.extend(extra)

    return cmd


def args_download_ytdlp(trecho_str: str, output_path: str, extra: list = None) -> list:
    """
    Argumentos completos para download de trecho de vÃ­deo.

    Args:
        trecho_str  : ex '*00:10:00.000-00:11:00.000'
        output_path : caminho do arquivo de saÃ­da
        extra       : argumentos extras antes da URL
    """
    cmd = args_base_ytdlp()

    cmd += [
        "--download-sections", trecho_str,
        # Qualidade: 1080p com Ã¡udio (forÃ§ando H.264/AVC para garantir suporte no OpenCV)
        "-f", "bestvideo[ext=mp4][vcodec^=avc][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]/best",
        "--merge-output-format", "mp4",
        "--recode-video", "mp4",  # Garante re-encode para h264 caso nÃ£o venha nativo
        "-o", output_path,
    ]

    if extra:
        cmd.extend(extra)

    return cmd

