"""
ajustar_corte_semantico.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Passo 2.5 do Pipeline Canal Cortes.

ApÃ³s detectar a zona quente via heatmap, refina os pontos de corte
usando a transcriÃ§Ã£o do trecho como guia semÃ¢ntico.

Problema que resolve:
  O heatmap define os limites do clipe matematicamente â€” sem saber o
  que estÃ¡ sendo dito. Isso faz o corte cair no meio de uma frase,
  gerando clipes que comeÃ§am sem contexto ou terminam sem conclusÃ£o.

SoluÃ§Ã£o:
  1. Expande o trecho detectado (atÃ© 90s antes e depois) para ter contexto
  2. Baixa apenas o ÃUDIO dessa janela expandida (baixo consumo)
  3. Transcreve com Groq Whisper (verbose_json com timestamps de segmentos)
  4. Busca na transcriÃ§Ã£o:
     - InÃ­cio ajustado: primeiro segmento que comeÃ§a apÃ³s inÃ­cio_heatmap
       (dentro de Â±45s) e representa o comeÃ§o de uma sentenÃ§a/fala completa
     - Fim ajustado: Ãºltimo segmento que TERMINA antes do fim_heatmap
       (dentro de Â±45s) e representa o final de uma sentenÃ§a/ideia completa
  5. Retorna (inicio_ajustado, fim_ajustado)
"""

import os
import re
import sys
import subprocess
import tempfile

from groq import Groq

ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")

# Janela de expansÃ£o para busca de contexto (em segundos)
JANELA_EXPANSAO_S = 90.0   # Expande atÃ© 90s antes e depois do pico
# Janela mÃ¡xima de busca do ponto de corte ajustado (em segundos em relaÃ§Ã£o ao pico original)
JANELA_BUSCA_S    = 45.0   # Aceita ajuste de atÃ© 45s do ponto original

# Marcadores de fim de sentenÃ§a
MARCADORES_FIM = re.compile(r'[.!?â€¦]+\s*$')
# Marcadores de inÃ­cio de nova ideia (comeÃ§o de frase apÃ³s pontuaÃ§Ã£o)
MARCADORES_INICIO = re.compile(r'^[A-ZÃÃ‰ÃÃ“ÃšÃ‚ÃŠÃŽÃ”Ã›ÃƒÃ•Ã€Ã‡"\'"Â«\-â€“]')


def _formatar_tempo(segundos: float) -> str:
    """Converte segundos para formato HH:MM:SS.mmm usado pelo yt-dlp."""
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = segundos % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def _baixar_audio_expandido(
    video_url: str,
    inicio_s: float,
    fim_s: float,
    output_dir: str,
) -> tuple[str, float]:
    """
    Baixa apenas o Ã¡udio do trecho expandido para uso na transcriÃ§Ã£o.
    Usa qualidade mÃ­nima (bestaudio) para ser rÃ¡pido.

    Returns:
        (caminho_audio_mp3, offset_s) onde offset_s Ã© o inÃ­cio real do trecho
        baixado (para converter os timestamps do Whisper de volta ao tempo global)
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ytdlp_helper import args_base_ytdlp

    inicio_exp = max(0.0, inicio_s - JANELA_EXPANSAO_S)
    fim_exp    = fim_s + JANELA_EXPANSAO_S
    trecho_str = f"*{_formatar_tempo(inicio_exp)}-{_formatar_tempo(fim_exp)}"

    audio_dir  = os.path.join(output_dir, "tmp")
    os.makedirs(audio_dir, exist_ok=True)
    audio_path = os.path.join(audio_dir, "_semantico_audio.mp3")

    print(f"  ðŸŽ™ï¸  [SemÃ¢ntico] Baixando Ã¡udio expandido: {_formatar_tempo(inicio_exp)} â†’ {_formatar_tempo(fim_exp)}...")

    # Tenta com anti-bot completo primeiro
    cmds = [
        args_base_ytdlp([
            "--download-sections", trecho_str,
            "-f", "bestaudio/best",
            "-x",                              # Extrai apenas Ã¡udio
            "--audio-format", "mp3",
            "--audio-quality", "3",            # Qualidade mÃ©dia â€” suficiente para ASR
            "-o", audio_path,
            "--quiet",
        ]) + [video_url],
        [
            "yt-dlp",
            "--download-sections", trecho_str,
            "--extractor-args", "youtube:player_client=web,android,tv_downgraded",
            "-f", "bestaudio/best",
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "3",
            "-o", audio_path,
            "--no-playlist", "--no-warnings", "--quiet",
            video_url,
        ],
    ]

    for cmd in cmds:
        resultado = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
        # yt-dlp com -x pode gerar .mp3 diretamente ou com sufixo diferente
        arquivo_real = _encontrar_audio(audio_path)
        if resultado.returncode == 0 and arquivo_real:
            tamanho_mb = os.path.getsize(arquivo_real) / (1024 * 1024)
            print(f"  âœ… [SemÃ¢ntico] Ãudio baixado: {arquivo_real} ({tamanho_mb:.1f} MB)")
            return arquivo_real, inicio_exp
        print(f"  âš ï¸  [SemÃ¢ntico] Falhou: {resultado.stderr[-100:]}")

    raise RuntimeError(f"[SemÃ¢ntico] NÃ£o foi possÃ­vel baixar Ã¡udio expandido de {video_url}")


def _encontrar_audio(output_path: str) -> str | None:
    """Localiza o arquivo de Ã¡udio gerado pelo yt-dlp (ignora extensÃ£o)."""
    base = output_path.rsplit(".", 1)[0]
    for ext in [".mp3", ".m4a", ".opus", ".webm", ".ogg"]:
        cand = base + ext
        if os.path.exists(cand):
            return cand
    if os.path.exists(output_path):
        return output_path
    return None


def _transcrever_audio(audio_path: str) -> list:
    """
    Transcreve o Ã¡udio via Groq Whisper (verbose_json).

    Returns:
        Lista de segmentos [{start, end, text}, ...]
        onde start/end sÃ£o relativos ao inÃ­cio do arquivo de Ã¡udio.
    """
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        raise EnvironmentError("GROQ_API_KEY nÃ£o configurado.")

    cliente = Groq(api_key=groq_key)

    # Whisper aceita arquivos atÃ© 25 MB. Para Ã¡udios maiores, corta o trecho
    tamanho_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"  ðŸ¤– [SemÃ¢ntico] Transcrevendo {tamanho_mb:.1f} MB com Groq Whisper...")

    with open(audio_path, "rb") as f:
        transcricao = cliente.audio.transcriptions.create(
            file=(os.path.basename(audio_path), f.read()),
            model="whisper-large-v3-turbo",
            response_format="verbose_json",
            language="pt",
        )

    if isinstance(transcricao, dict):
        segmentos = transcricao.get("segments", [])
    else:
        segmentos = getattr(transcricao, "segments", [])

    # Normaliza para dicts
    resultado = []
    for seg in segmentos:
        start = seg.start if hasattr(seg, "start") else seg["start"]
        end   = seg.end   if hasattr(seg, "end")   else seg["end"]
        text  = seg.text  if hasattr(seg, "text")  else seg["text"]
        resultado.append({"start": float(start), "end": float(end), "text": text.strip()})

    print(f"  âœ… [SemÃ¢ntico] {len(resultado)} segmentos transcritos")
    return resultado


def _eh_inicio_de_frase(texto: str) -> bool:
    """
    Verifica se o texto parece ser o inÃ­cio de uma nova ideia/frase.
    HeurÃ­sticas: comeÃ§a com maiÃºscula, nÃ£o Ã© continuaÃ§Ã£o de conjunÃ§Ã£o, etc.
    """
    if not texto:
        return False
    # ComeÃ§a com letra maiÃºscula ou aspas/travessÃ£o (diÃ¡logo)
    return bool(MARCADORES_INICIO.match(texto))


def _eh_fim_de_frase(texto: str) -> bool:
    """
    Verifica se o texto termina uma sentenÃ§a/ideia completa.
    HeurÃ­sticas: termina com '.', '!', '?', '...', etc.
    """
    if not texto:
        return False
    return bool(MARCADORES_FIM.search(texto))


def ajustar_corte_semantico(
    video_url: str,
    inicio_s: float,
    fim_s: float,
    output_dir: str = OUTPUT_DIR,
) -> tuple[float, float]:
    """
    Refina os pontos de corte de um clipe usando transcriÃ§Ã£o como guia semÃ¢ntico.

    Fluxo:
      1. Baixa Ã¡udio expandido (Â±90s alÃ©m do pico)
      2. Transcreve com Groq Whisper
      3. Encontra inÃ­cio de frase mais prÃ³ximo do inicio_s (Â±45s)
      4. Encontra fim de frase mais prÃ³ximo do fim_s (Â±45s)
      5. Retorna tempos ajustados

    Args:
        video_url : URL do vÃ­deo original
        inicio_s  : ponto de inÃ­cio do heatmap (segundos absolutos no vÃ­deo)
        fim_s     : ponto de fim do heatmap (segundos absolutos no vÃ­deo)
        output_dir: pasta de trabalho

    Returns:
        (inicio_ajustado_s, fim_ajustado_s)
        Se o ajuste falhar, retorna os valores originais.
    """
    print(f"\n  ðŸ” [Ajuste SemÃ¢ntico] Refinando corte {inicio_s:.0f}s â†’ {fim_s:.0f}s...")

    try:
        # 1. Baixa Ã¡udio expandido
        audio_path, offset_s = _baixar_audio_expandido(video_url, inicio_s, fim_s, output_dir)

        # 2. Transcreve
        segmentos = _transcrever_audio(audio_path)

        # Remove arquivo de Ã¡udio temporÃ¡rio
        if os.path.exists(audio_path):
            os.remove(audio_path)

        if not segmentos:
            print("  âš ï¸  [SemÃ¢ntico] Sem segmentos na transcriÃ§Ã£o. Usando tempos originais.")
            return inicio_s, fim_s

        # Converte timestamps relativos (ao inÃ­cio do arquivo de Ã¡udio) para absolutos
        # Whisper retorna tempos relativos ao inÃ­cio do arquivo que enviamos.
        # O arquivo comeÃ§a em offset_s do vÃ­deo original.
        segs_abs = [
            {
                "start": s["start"] + offset_s,
                "end":   s["end"]   + offset_s,
                "text":  s["text"],
            }
            for s in segmentos
        ]

        # â”€â”€â”€ Ajuste do INÃCIO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Busca o segmento cujo inÃ­cio Ã© mais prÃ³ximo do inicio_s
        # PreferÃªncia: comeÃ§a uma frase nova (maiÃºscula) e estÃ¡ dentro da janela
        candidatos_inicio = [
            s for s in segs_abs
            if abs(s["start"] - inicio_s) <= JANELA_BUSCA_S
        ]

        inicio_ajustado = inicio_s  # Default: mantÃ©m original
        if candidatos_inicio:
            # Prefere o segmento que Ã© inÃ­cio de frase e estÃ¡ mais perto do pico
            frases_novas = [s for s in candidatos_inicio if _eh_inicio_de_frase(s["text"])]
            pool = frases_novas if frases_novas else candidatos_inicio
            # Escolhe o mais prÃ³ximo do ponto original (minimiza diferenÃ§a)
            melhor = min(pool, key=lambda s: abs(s["start"] - inicio_s))
            inicio_ajustado = melhor["start"]
            print(f"  âœ… [SemÃ¢ntico] InÃ­cio ajustado: {inicio_s:.1f}s â†’ {inicio_ajustado:.1f}s")
            print(f"     Frase: \"{melhor['text'][:80]}\"")
        else:
            print(f"  â„¹ï¸  [SemÃ¢ntico] Nenhum segmento prÃ³ximo do inÃ­cio. Mantendo {inicio_s:.1f}s")

        # â”€â”€â”€ Ajuste do FIM â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Busca segmentos cujo FIM Ã© mais prÃ³ximo de fim_s
        # PreferÃªncia: termina uma frase completa (pontuaÃ§Ã£o) e estÃ¡ dentro da janela
        candidatos_fim = [
            s for s in segs_abs
            if abs(s["end"] - fim_s) <= JANELA_BUSCA_S
        ]

        fim_ajustado = fim_s  # Default: mantÃ©m original
        if candidatos_fim:
            frases_completas = [s for s in candidatos_fim if _eh_fim_de_frase(s["text"])]
            pool = frases_completas if frases_completas else candidatos_fim
            # Escolhe o mais prÃ³ximo do ponto de fim original
            melhor = min(pool, key=lambda s: abs(s["end"] - fim_s))
            fim_ajustado = melhor["end"]
            print(f"  âœ… [SemÃ¢ntico] Fim ajustado: {fim_s:.1f}s â†’ {fim_ajustado:.1f}s")
            print(f"     Frase: \"...{melhor['text'][-80:]}\"")
        else:
            print(f"  â„¹ï¸  [SemÃ¢ntico] Nenhum segmento prÃ³ximo do fim. Mantendo {fim_s:.1f}s")

        # Garante que o inÃ­cio Ã© sempre menor que o fim
        if inicio_ajustado >= fim_ajustado:
            print("  âš ï¸  [SemÃ¢ntico] Ajuste invÃ¡lido (inÃ­cio >= fim). Usando originais.")
            return inicio_s, fim_s

        duracao = fim_ajustado - inicio_ajustado
        print(f"  ðŸ“ [SemÃ¢ntico] DuraÃ§Ã£o final: {duracao:.1f}s ({duracao/60:.1f} min)")

        return inicio_ajustado, fim_ajustado

    except Exception as e:
        print(f"  âš ï¸  [SemÃ¢ntico] Falha no ajuste semÃ¢ntico: {e}. Usando tempos originais.")
        return inicio_s, fim_s


if __name__ == "__main__":
    # Teste rÃ¡pido
    url      = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=example"
    inicio_s = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
    fim_s    = float(sys.argv[3]) if len(sys.argv) > 3 else 700.0
    i, f = ajustar_corte_semantico(url, inicio_s, fim_s)
    print(f"\nResultado: {i:.1f}s â†’ {f:.1f}s  (duraÃ§Ã£o: {f - i:.1f}s)")

