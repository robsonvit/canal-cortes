"""
baixar_trecho.py
────────────────
Passo 3 do Pipeline Canal Cortes.

Baixa apenas o trecho exato do vídeo (do pico de replay)
usando yt-dlp com --download-sections.

Qualidade: 1080p preferencial, fallback para melhor disponível.
Formato: MP4 com áudio (necessário para transcrição).
"""

import os
import subprocess

ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")


def baixar_trecho(video_url: str, inicio_s: float, fim_s: float, output_dir: str = OUTPUT_DIR) -> str:
    """
    Baixa o trecho [inicio_s, fim_s] do vídeo.

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

    trecho_str = f"*{_formatar_tempo(inicio_s)}-{_formatar_tempo(fim_s)}"
    output_path = os.path.join(output_dir, "trecho_original.mp4")

    print(f"  ⬇️  Baixando trecho {_formatar_tempo(inicio_s)} → {_formatar_tempo(fim_s)}...")
    print(f"     URL: {video_url}")

    cmd = [
        "yt-dlp",
        # Seção específica (evita baixar o vídeo inteiro)
        "--download-sections", trecho_str,

        # Qualidade: 1080p com áudio, fallback para melhor disponível
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",

        # Força mesclar em MP4
        "--merge-output-format", "mp4",

        # Caminho de saída
        "-o", output_path,

        # Sem metadados desnecessários
        "--no-playlist",
        "--no-warnings",

        # Cookies do navegador para evitar bloqueios (se disponível)
        # "--cookies-from-browser", "chrome",  # Descomente se necessário
    ]
    if os.path.exists("cookies.txt"):
        cmd.extend(["--cookies", "cookies.txt"])
    
    cmd.append(video_url)

    resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if resultado.returncode != 0:
        # Tenta fallback com qualidade menor
        print(f"  ⚠️  Falha na qualidade premium. Tentando fallback...")
        cmd_fallback = [
            "yt-dlp",
            "--download-sections", trecho_str,
            "-f", "best",
            "--merge-output-format", "mp4",
            "-o", output_path,
            "--no-playlist",
            "--no-warnings",
        ]
        if os.path.exists("cookies.txt"):
            cmd_fallback.extend(["--cookies", "cookies.txt"])
            
        cmd_fallback.append(video_url)
        resultado2 = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=300)
        if resultado2.returncode != 0:
            raise RuntimeError(
                f"Falha ao baixar o trecho:\n{resultado.stderr[-400:]}\n{resultado2.stderr[-400:]}"
            )

    # Verifica se o arquivo foi criado
    if not os.path.exists(output_path):
        # yt-dlp pode ter adicionado extensão diferente — tenta encontrar
        for ext in [".mp4", ".mkv", ".webm"]:
            alt = output_path.replace(".mp4", ext)
            if os.path.exists(alt):
                output_path = alt
                break
        else:
            raise FileNotFoundError(
                f"Arquivo de saída não encontrado em: {output_path}"
            )

    tamanho_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  ✅ Trecho baixado: {output_path} ({tamanho_mb:.1f} MB)")
    return output_path


def _formatar_tempo(segundos: float) -> str:
    """Converte segundos para formato HH:MM:SS.mmm usado pelo yt-dlp."""
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = segundos % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


if __name__ == "__main__":
    import sys
    url      = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=example"
    inicio_s = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
    fim_s    = float(sys.argv[3]) if len(sys.argv) > 3 else 660.0
    caminho  = baixar_trecho(url, inicio_s, fim_s)
    print(f"Arquivo: {caminho}")
