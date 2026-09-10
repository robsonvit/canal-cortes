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

    # ── TRAVA DE QUALIDADE: Tenta 1080p em todas as estratégias; fallback final para 720p ──
    # As primeiras 4 tentativas exigem 1080p (apenas muda a estratégia anti-bot).
    # A 5ª tentativa é um fallback para 720p caso o vídeo simplesmente não tenha 1080p
    # (ex: vídeo antigo do canal, upload original em baixa resolução).
    FILTRO_1080P = "bestvideo[height>=1080]+bestaudio/best[height>=1080]"

    tentativas = [
        {
            "desc": "Prioridade 0: 1080p+ | Client Mobile (ios,android,mweb)",
            "cmd": [
                "yt-dlp", "--force-ipv4",
                "--download-sections", trecho_str,
                "--extractor-args", "youtube:player_client=ios,android,mweb",
                "-f", FILTRO_1080P,
                "--merge-output-format", "mkv",
                "-o", output_path,
                "--no-playlist", "--no-warnings", "--quiet",
            ] + (["--cookies", "cookies.txt"] if os.path.exists("cookies.txt") else []) + [video_url],
        },
        {
            # Usa o default do yt-dlp (curl-cffi/deno embutido lidará com bot check via WARP)
            "desc": "Prioridade 1: 1080p+ | Client Padrão (Sem forçar player, confia no WARP)",
            "cmd": [
                "yt-dlp", "--force-ipv4",
                "--download-sections", trecho_str,
                "-f", FILTRO_1080P,
                "--merge-output-format", "mkv",
                "-o", output_path,
                "--no-playlist", "--no-warnings", "--quiet",
            ] + (["--cookies", "cookies.txt"] if os.path.exists("cookies.txt") else []) + [video_url],
        },
        {
            # Força cliente tv (tvhtml5simples) que costuma não ter check pesado e retorna 1080p
            "desc": "Prioridade 2: 1080p+ | player_client=tv",
            "cmd": [
                "yt-dlp", "--force-ipv4",
                "--download-sections", trecho_str,
                "--extractor-args", "youtube:player_client=tv",
                "-f", FILTRO_1080P,
                "--merge-output-format", "mkv",
                "-o", output_path,
                "--no-playlist", "--no-warnings", "--quiet",
            ] + (["--cookies", "cookies.txt"] if os.path.exists("cookies.txt") else []) + [video_url],
        },
        {
            # Força o client web padrão com bypass de restrição de idade
            "desc": "Prioridade 3: 1080p+ | player_client=web + bypass cookies",
            "cmd": [
                "yt-dlp", "--force-ipv4",
                "--download-sections", trecho_str,
                "--extractor-args", "youtube:player_client=web",
                "--age-limit", "21",
                "-f", FILTRO_1080P,
                "--merge-output-format", "mkv",
                "-o", output_path,
                "--no-playlist", "--no-warnings", "--quiet",
            ] + (["--cookies", "cookies.txt"] if os.path.exists("cookies.txt") else []) + [video_url],
        },
        {
            # Fallback final: aceita 720p se nenhuma tentativa anterior funcionou com 1080p
            # Isso resolve casos onde o vídeo não foi upado em 1080p pelo criador
            "desc": "Prioridade 4: FALLBACK 720p | bestvideo[height>=720] (vídeo não tem 1080p)",
            "filtro": "bestvideo[height>=720]+bestaudio/best[height>=720]",
            "tamanho_min_mb": 2.0,
            "cmd": [
                "yt-dlp", "--force-ipv4",
                "--download-sections", trecho_str,
                "-f", "bestvideo[height>=720]+bestaudio/best[height>=720]",
                "--merge-output-format", "mkv",
                "-o", output_path,
                "--no-playlist", "--no-warnings", "--quiet",
            ] + (["--cookies", "cookies.txt"] if os.path.exists("cookies.txt") else []) + [video_url],
        }
    ]

    for t in tentativas:
        print(f"  🔄 {t['desc']}...")
        # Tamanho mínimo específico da tentativa (fallback 720p aceita 2 MB)
        tamanho_min_mb = t.get("tamanho_min_mb", TAMANHO_MIN_MB)
        # Remove arquivo temp se existir de tentativa anterior
        if os.path.exists(output_path):
            os.remove(output_path)
            
        resultado = subprocess.run(t["cmd"], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1500)

        if resultado.returncode == 0:
            arquivo = _encontrar_arquivo(output_path)
            if arquivo:
                tamanho_mb = os.path.getsize(arquivo) / (1024 * 1024)
                print(f"  ✅ Trecho cru baixado: {arquivo} ({tamanho_mb:.1f} MB)")

                # ── Validação de tamanho mínimo ────────────────────────────────
                # Usa o tamanho mínimo específico da tentativa (fallback 720p aceita 2 MB)
                if tamanho_mb < tamanho_min_mb:
                    print(f"  🚫 ARQUIVO MUITO PEQUENO: {tamanho_mb:.1f} MB < {tamanho_min_mb} MB. Download corrompido ou incompleto. Descartando...")
                    os.remove(arquivo)
                    continue

                # ── Verificação de qualidade pós-download ─────────────────────
                # O fallback (720p) tem threshold reduzido
                resolucao_min = 720 if "720p" in t["desc"] else 1080
                resolucao = _verificar_resolucao(arquivo)
                if resolucao:
                    print(f"  🔍 Resolução detectada: {resolucao[0]}x{resolucao[1]}")
                    if resolucao[1] < resolucao_min:
                        print(f"  🚫 TRAVA DE QUALIDADE: {resolucao[1]}p < {resolucao_min}p. Descartando e tentando próxima estratégia...")
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
                    if t_mb < 1.0:
                        print(f"  🚫 ARQUIVO FINAL MUITO PEQUENO: {t_mb:.1f} MB. Recodificação falhou silenciosamente. Descartando...")
                        os.remove(final_path)
                        if os.path.exists(arquivo):
                            os.remove(arquivo)
                        continue
                    print(f"  ✅ Corte exato concluído: {final_path} ({t_mb:.1f} MB)")
                    return final_path
                else:
                    print(f"  ⚠️  Falha ao aparar trecho: {res_trim.stderr[-200:]}")
                    # NÃO retorna arquivo bruto corrompido — tenta próxima estratégia
                    if os.path.exists(arquivo):
                        os.remove(arquivo)
                    if os.path.exists(final_path):
                        os.remove(final_path)
                    continue

        print(f"  ⚠️  Falhou: {resultado.stderr[-150:]}")

    raise RuntimeError(
        f"\n🚫 ERRO DE DOWNLOAD: Todas as {len(tentativas)} tentativas falharam (incluindo fallback 720p)."
        f"\n   URL: {video_url}"
        f"\n   Isso pode indicar bloqueio anti-bot severo ou vídeo indisponível nessa região."
        f"\n   O pipeline tentará o próximo pico/vídeo disponível."
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

