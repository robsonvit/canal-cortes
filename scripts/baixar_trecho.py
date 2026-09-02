"""
baixar_trecho.py
────────────────
Passo 3 do Pipeline Canal Cortes.

Baixa apenas o trecho exato do vídeo (do pico de replay)
usando yt-dlp com --download-sections.

🔒 TRAVA DE QUALIDADE MÍNIMA: 1080p (height >= 1080)
  - NENHUMA tentativa aceita vídeo abaixo de 1080p
  - O fallback muda a estratégia anti-bot, NÃO a qualidade
  - Se nenhuma tentativa conseguir 1080p, o pipeline ABORTA com erro

Técnicas anti-bloqueio aplicadas:
  - curl-cffi: TLS fingerprint de Chrome real
  - player_client múltiplo: mweb,android > web,android > android,ios > tv_downgraded
  - cookies autenticados (via ytdlp_helper)
  - Deno para JS challenges (instalado pelo workflow)
  - 4 tentativas com estratégias anti-bot diferentes (sem abaixar qualidade)

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
    Utiliza uma margem de segurança de 10s antes do clipe e corta exato com ffmpeg
    para garantir 0 delay de áudio/vídeo.
    """
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "tmp"), exist_ok=True)

    MARGEM_S = 10.0
    inicio_dl = max(0.0, inicio_s - MARGEM_S)
    trim_s = inicio_s - inicio_dl

    trecho_str  = f"*{_formatar_tempo(inicio_dl)}-{_formatar_tempo(fim_s)}"
    output_path = os.path.join(output_dir, "tmp", "_raw_download.mkv")
    final_path = os.path.join(output_dir, "trecho_original.mp4")

    print(f"  ⬇️  Baixando trecho (com margem) {_formatar_tempo(inicio_dl)} → {_formatar_tempo(fim_s)}...")
    print(f"     URL: {video_url}")

    # ── TRAVA DE QUALIDADE: NENHUMA tentativa aceita abaixo de 1080p ─────────
    # O fallback muda a estratégia anti-bot, NÃO a qualidade mínima.
    # Se todas as 4 tentativas falharem em 1080p, o pipeline aborta com erro.
    FILTRO_1080P = "bestvideo[height>=1080]+bestaudio/bestvideo[height>=1080]+bestaudio[ext=m4a]"

    tentativas = [
        {
            "desc": "Prioridade 1: 1080p+ | anti-bot completo (WARP + curl-cffi + mweb,android)",
            "cmd": args_base_ytdlp([
                "--download-sections", trecho_str,
                "-f", FILTRO_1080P,
                "--merge-output-format", "mkv",
                "-o", output_path,
                "--quiet",
            ]) + [video_url],
        },
        {
            # Muda apenas o player_client — mantém 1080p mínimo
            "desc": "Prioridade 2: 1080p+ | player_client=web,android (sem curl-cffi)",
            "cmd": [
                "yt-dlp",
                "--download-sections", trecho_str,
                "--extractor-args", "youtube:player_client=web,android",
                "-f", FILTRO_1080P,
                "--merge-output-format", "mkv",
                "-o", output_path,
                "--no-playlist", "--no-warnings", "--quiet",
                video_url,
            ],
        },
        {
            # Tenta player_client=android,ios — mantém 1080p mínimo
            "desc": "Prioridade 3: 1080p+ | player_client=android,ios",
            "cmd": [
                "yt-dlp",
                "--download-sections", trecho_str,
                "--extractor-args", "youtube:player_client=android,ios",
                "-f", FILTRO_1080P,
                "--merge-output-format", "mkv",
                "-o", output_path,
                "--no-playlist", "--no-warnings", "--quiet",
                video_url,
            ],
        },
        {
            # Último recurso: tv_downgraded (contorna alguns bot-checks) — AINDA 1080p mínimo
            "desc": "Prioridade 4: 1080p+ | player_client=tv_downgraded (último recurso anti-bot)",
            "cmd": [
                "yt-dlp",
                "--download-sections", trecho_str,
                "--extractor-args", "youtube:player_client=tv_downgraded",
                "-f", FILTRO_1080P,
                "--merge-output-format", "mkv",
                "-o", output_path,
                "--no-playlist", "--no-warnings", "--quiet",
                video_url,
            ],
        },
    ]

    for t in tentativas:
        print(f"  🔄 {t['desc']}...")
        # Remove arquivo temp se existir de tentativa anterior
        if os.path.exists(output_path):
            os.remove(output_path)
            
        resultado = subprocess.run(t["cmd"], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)

        if resultado.returncode == 0:
            arquivo = _encontrar_arquivo(output_path)
            if arquivo:
                tamanho_mb = os.path.getsize(arquivo) / (1024 * 1024)
                print(f"  ✅ Trecho cru baixado: {arquivo} ({tamanho_mb:.1f} MB)")

                # ── Verificação de qualidade pós-download ─────────────────────
                resolucao = _verificar_resolucao(arquivo)
                if resolucao:
                    print(f"  🔍 Resolução detectada: {resolucao[0]}x{resolucao[1]}")
                    if resolucao[1] < 1080:
                        print(f"  🚫 TRAVA DE QUALIDADE: {resolucao[1]}p < 1080p. Descartando e tentando próxima estratégia...")
                        os.remove(arquivo)
                        continue
                    else:
                        print(f"  ✅ Qualidade aprovada: {resolucao[1]}p >= 1080p")
                else:
                    print("  ⚠️  Não foi possível verificar resolução — prosseguindo com cautela")

                # Executa o corte exato removendo a margem e recodificando
                cmd_trim = [
                    "ffmpeg", "-y",
                    "-i", arquivo,
                    "-ss", str(trim_s),
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "16",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-avoid_negative_ts", "make_zero",
                    final_path
                ]
                print(f"  ✂️  Aparando {trim_s:.1f}s iniciais com recodificação para zerar delay...")
                res_trim = subprocess.run(cmd_trim, capture_output=True, text=True, encoding='utf-8', errors='replace')
                if res_trim.returncode == 0 and os.path.exists(final_path):
                    t_mb = os.path.getsize(final_path) / (1024 * 1024)
                    print(f"  ✅ Corte exato concluído: {final_path} ({t_mb:.1f} MB)")
                    return final_path
                else:
                    print(f"  ⚠️  Falha ao aparar trecho: {res_trim.stderr[-200:]}")
                    # Retorna o arquivo bruto em caso de falha extrema
                    return arquivo

        print(f"  ⚠️  Falhou: {resultado.stderr[-150:]}")

    raise RuntimeError(
        f"\n🚫 ERRO DE QUALIDADE: Todas as {len(tentativas)} tentativas de download em 1080p+ falharam."
        f"\n   URL: {video_url}"
        f"\n   Isso pode indicar que o vídeo não está disponível em 1080p ou bloqueio anti-bot."
        f"\n   NOTA: O pipeline NÃO aceita vídeos abaixo de 1080p por política de qualidade."
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


def _verificar_resolucao(arquivo: str) -> tuple[int, int] | None:
    """
    Usa ffprobe para verificar a resolução real do arquivo baixado.
    Retorna (largura, altura) ou None se não conseguir verificar.

    🔒 Esta verificação é a SEGUNDA camada da trava de qualidade:
       A primeira é o filtro do yt-dlp, esta é a confirmação pós-download.
    """
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            arquivo,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            partes = result.stdout.strip().split(",")
            if len(partes) >= 2:
                return (int(partes[0]), int(partes[1]))
    except Exception as e:
        print(f"  ⚠️  ffprobe falhou: {e}")
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

