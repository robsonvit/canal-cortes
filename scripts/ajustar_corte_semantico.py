"""
ajustar_corte_semantico.py
──────────────────────────
Passo 2.5 do Pipeline Canal Cortes.

Após detectar a zona quente via heatmap, refina os pontos de corte
usando a transcrição do trecho como guia semântico.

Problema que resolve:
  O heatmap define os limites do clipe matematicamente — sem saber o
  que está sendo dito. Isso faz o corte cair no meio de uma frase,
  gerando clipes que começam sem contexto ou terminam sem conclusão.

Solução:
  1. Expande o trecho detectado (até 90s antes e depois) para ter contexto
  2. Baixa apenas o ÁUDIO dessa janela expandida (baixo consumo)
  3. Transcreve com Groq Whisper (verbose_json com timestamps de segmentos)
  4. Busca na transcrição:
     - Início ajustado: primeiro segmento que começa após início_heatmap
       (dentro de ±45s) e representa o começo de uma sentença/fala completa
     - Fim ajustado: último segmento que TERMINA antes do fim_heatmap
       (dentro de ±45s) e representa o final de uma sentença/ideia completa
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

# Janela de expansão para busca de contexto (em segundos)
JANELA_EXPANSAO_S = 90.0   # Expande até 90s antes e depois do pico
# Janela máxima de busca do ponto de corte ajustado (em segundos em relação ao pico original)
JANELA_BUSCA_S    = 45.0   # Aceita ajuste de até 45s do ponto original

# Marcadores de fim de sentença
MARCADORES_FIM = re.compile(r'[.!?…]+\s*$')
# Marcadores de início de nova ideia (começo de frase após pontuação)
MARCADORES_INICIO = re.compile(r'^[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÇ"\'"«\-–]')


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
    Baixa apenas o áudio do trecho expandido para uso na transcrição.
    Usa qualidade mínima (bestaudio) para ser rápido.

    Returns:
        (caminho_audio_mp3, offset_s) onde offset_s é o início real do trecho
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

    print(f"  🎙️  [Semântico] Baixando áudio expandido: {_formatar_tempo(inicio_exp)} → {_formatar_tempo(fim_exp)}...")

    # Tenta com anti-bot completo primeiro
    cmds = [
        args_base_ytdlp([
            "--download-sections", trecho_str,
            "-f", "bestaudio/best",
            "-x",                              # Extrai apenas áudio
            "--audio-format", "mp3",
            "--audio-quality", "3",            # Qualidade média — suficiente para ASR
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
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        # yt-dlp com -x pode gerar .mp3 diretamente ou com sufixo diferente
        arquivo_real = _encontrar_audio(audio_path)
        if resultado.returncode == 0 and arquivo_real:
            tamanho_mb = os.path.getsize(arquivo_real) / (1024 * 1024)
            print(f"  ✅ [Semântico] Áudio baixado: {arquivo_real} ({tamanho_mb:.1f} MB)")
            return arquivo_real, inicio_exp
        print(f"  ⚠️  [Semântico] Falhou: {resultado.stderr[-100:]}")

    raise RuntimeError(f"[Semântico] Não foi possível baixar áudio expandido de {video_url}")


def _encontrar_audio(output_path: str) -> str | None:
    """Localiza o arquivo de áudio gerado pelo yt-dlp (ignora extensão)."""
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
    Transcreve o áudio via Groq Whisper (verbose_json).

    Returns:
        Lista de segmentos [{start, end, text}, ...]
        onde start/end são relativos ao início do arquivo de áudio.
    """
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        raise EnvironmentError("GROQ_API_KEY não configurado.")

    cliente = Groq(api_key=groq_key)

    # Whisper aceita arquivos até 25 MB. Para áudios maiores, corta o trecho
    tamanho_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"  🤖 [Semântico] Transcrevendo {tamanho_mb:.1f} MB com Groq Whisper...")

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

    print(f"  ✅ [Semântico] {len(resultado)} segmentos transcritos")
    return resultado


def _eh_inicio_de_frase(texto: str) -> bool:
    """
    Verifica se o texto parece ser o início de uma nova ideia/frase.
    Heurísticas: começa com maiúscula, não é continuação de conjunção, etc.
    """
    if not texto:
        return False
    # Começa com letra maiúscula ou aspas/travessão (diálogo)
    return bool(MARCADORES_INICIO.match(texto))


def _eh_fim_de_frase(texto: str) -> bool:
    """
    Verifica se o texto termina uma sentença/ideia completa.
    Heurísticas: termina com '.', '!', '?', '...', etc.
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
    Refina os pontos de corte de um clipe usando transcrição como guia semântico.

    Fluxo:
      1. Baixa áudio expandido (±90s além do pico)
      2. Transcreve com Groq Whisper
      3. Encontra início de frase mais próximo do inicio_s (±45s)
      4. Encontra fim de frase mais próximo do fim_s (±45s)
      5. Retorna tempos ajustados

    Args:
        video_url : URL do vídeo original
        inicio_s  : ponto de início do heatmap (segundos absolutos no vídeo)
        fim_s     : ponto de fim do heatmap (segundos absolutos no vídeo)
        output_dir: pasta de trabalho

    Returns:
        (inicio_ajustado_s, fim_ajustado_s)
        Se o ajuste falhar, retorna os valores originais.
    """
    print(f"\n  🔍 [Ajuste Semântico] Refinando corte {inicio_s:.0f}s → {fim_s:.0f}s...")

    try:
        # 1. Baixa áudio expandido
        audio_path, offset_s = _baixar_audio_expandido(video_url, inicio_s, fim_s, output_dir)

        # 2. Transcreve
        segmentos = _transcrever_audio(audio_path)

        # Remove arquivo de áudio temporário
        if os.path.exists(audio_path):
            os.remove(audio_path)

        if not segmentos:
            print("  ⚠️  [Semântico] Sem segmentos na transcrição. Usando tempos originais.")
            return inicio_s, fim_s

        # Converte timestamps relativos (ao início do arquivo de áudio) para absolutos
        # Whisper retorna tempos relativos ao início do arquivo que enviamos.
        # O arquivo começa em offset_s do vídeo original.
        segs_abs = [
            {
                "start": s["start"] + offset_s,
                "end":   s["end"]   + offset_s,
                "text":  s["text"],
            }
            for s in segmentos
        ]

        # ─── Ajuste do INÍCIO ──────────────────────────────────────────────────
        # Busca o segmento cujo início é mais próximo do inicio_s
        # Preferência: começa uma frase nova (maiúscula) e está dentro da janela
        candidatos_inicio = [
            s for s in segs_abs
            if abs(s["start"] - inicio_s) <= JANELA_BUSCA_S
        ]

        inicio_ajustado = inicio_s  # Default: mantém original
        if candidatos_inicio:
            # Prefere o segmento que é início de frase e está mais perto do pico
            frases_novas = [s for s in candidatos_inicio if _eh_inicio_de_frase(s["text"])]
            pool = frases_novas if frases_novas else candidatos_inicio
            # Escolhe o mais próximo do ponto original (minimiza diferença)
            melhor = min(pool, key=lambda s: abs(s["start"] - inicio_s))
            inicio_ajustado = melhor["start"]
            print(f"  ✅ [Semântico] Início ajustado: {inicio_s:.1f}s → {inicio_ajustado:.1f}s")
            print(f"     Frase: \"{melhor['text'][:80]}\"")
        else:
            print(f"  ℹ️  [Semântico] Nenhum segmento próximo do início. Mantendo {inicio_s:.1f}s")

        # ─── Ajuste do FIM ────────────────────────────────────────────────────
        # Busca segmentos cujo FIM é mais próximo de fim_s
        # Preferência: termina uma frase completa (pontuação) e está dentro da janela
        candidatos_fim = [
            s for s in segs_abs
            if abs(s["end"] - fim_s) <= JANELA_BUSCA_S
        ]

        fim_ajustado = fim_s  # Default: mantém original
        if candidatos_fim:
            frases_completas = [s for s in candidatos_fim if _eh_fim_de_frase(s["text"])]
            pool = frases_completas if frases_completas else candidatos_fim
            # Escolhe o mais próximo do ponto de fim original
            melhor = min(pool, key=lambda s: abs(s["end"] - fim_s))
            fim_ajustado = melhor["end"]
            print(f"  ✅ [Semântico] Fim ajustado: {fim_s:.1f}s → {fim_ajustado:.1f}s")
            print(f"     Frase: \"...{melhor['text'][-80:]}\"")
        else:
            print(f"  ℹ️  [Semântico] Nenhum segmento próximo do fim. Mantendo {fim_s:.1f}s")

        # Garante que o início é sempre menor que o fim
        if inicio_ajustado >= fim_ajustado:
            print("  ⚠️  [Semântico] Ajuste inválido (início >= fim). Usando originais.")
            return inicio_s, fim_s

        duracao = fim_ajustado - inicio_ajustado
        print(f"  📐 [Semântico] Duração final: {duracao:.1f}s ({duracao/60:.1f} min)")

        return inicio_ajustado, fim_ajustado

    except Exception as e:
        print(f"  ⚠️  [Semântico] Falha no ajuste semântico: {e}. Usando tempos originais.")
        return inicio_s, fim_s


if __name__ == "__main__":
    # Teste rápido
    url      = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=example"
    inicio_s = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
    fim_s    = float(sys.argv[3]) if len(sys.argv) > 3 else 700.0
    i, f = ajustar_corte_semantico(url, inicio_s, fim_s)
    print(f"\nResultado: {i:.1f}s → {f:.1f}s  (duração: {f - i:.1f}s)")
