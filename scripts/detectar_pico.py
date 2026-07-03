"""
detectar_pico.py
────────────────
Passo 2 do Pipeline Canal Cortes.

Extrai o heatmap do YouTube via yt-dlp e encontra o segmento
com maior intensidade de replay (o trecho mais assistido).

O heatmap retornado pelo yt-dlp é uma lista de objetos:
  [{"start_time": 0.0, "end_time": 5.0, "value": 0.3}, ...]
  onde "value" é a intensidade normalizada (0.0 a 1.0).

Estratégia:
  1. Obtém metadados completos via yt-dlp --dump-json
  2. Extrai o campo "heatmap"
  3. Aplica janela deslizante para encontrar segmento contínuo
     de 45-90 segundos com maior soma de intensidade
  4. Expande ligeiramente o início para capturar o contexto
"""

import subprocess
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ytdlp_helper import args_base_ytdlp

# Duração alvo do trecho a recortar (segundos)
DURACAO_MINIMA_S = 45
DURACAO_MAXIMA_S = 90
DURACAO_IDEAL_S  = 60   # Ponto médio ideal para Shorts


def _obter_metadados(video_url: str) -> dict:
    """
    Obtém metadados completos do vídeo via yt-dlp.
    Usa múltiplas camadas anti-bloqueio (WARP + Deno + curl-cffi + cookies).
    Tenta 3 estratégias em fallback se a primeira falhar.
    """
    print(f"  📡 Obtendo metadados do vídeo...")

    # Estratégias em ordem de confiabilidade
    estrategias = [
        # 1. Configuração completa com impersonation
        args_base_ytdlp(["--dump-json", "--quiet"]) + [video_url],
        # 2. Sem impersonation (fallback caso curl-cffi não esteja instalado)
        ["yt-dlp", "--dump-json", "--quiet", "--no-warnings", "--no-playlist",
         "--extractor-args", "youtube:player_client=web,android,tv_downgraded",
         video_url],
        # 3. Modo tv (menos bloqueado em CIs)
        ["yt-dlp", "--dump-json", "--quiet", "--no-warnings", "--no-playlist",
         "--extractor-args", "youtube:player_client=tv_downgraded",
         video_url],
    ]

    ultimo_erro = ""
    for i, cmd in enumerate(estrategias, 1):
        print(f"  🔄 Tentativa {i}/3...")
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if resultado.returncode == 0 and resultado.stdout.strip():
            print(f"  ✅ Metadados obtidos na tentativa {i}")
            return json.loads(resultado.stdout)
        ultimo_erro = resultado.stderr[:300]
        print(f"  ⚠️  Tentativa {i} falhou: {ultimo_erro[:100]}")

    raise RuntimeError(
        f"Falha ao obter metadados do vídeo (todas as tentativas falharam):\n{ultimo_erro}"
    )


def _janela_deslizante(heatmap: list, duracao_janela: float) -> tuple:
    """
    Aplica janela deslizante no heatmap para encontrar o intervalo
    de 'duracao_janela' segundos com maior intensidade acumulada.

    Retorna: (inicio_s, fim_s, intensidade_media)
    """
    if not heatmap:
        return None, None, 0.0

    # Ordenar por tempo de início
    heatmap_ord = sorted(heatmap, key=lambda x: x["start_time"])

    melhor_inicio    = heatmap_ord[0]["start_time"]
    melhor_fim       = melhor_inicio + duracao_janela
    melhor_intensidade = 0.0

    for i, seg in enumerate(heatmap_ord):
        inicio_janela = seg["start_time"]
        fim_janela    = inicio_janela + duracao_janela

        # Soma a intensidade de todos os segmentos dentro da janela
        intensidade_acumulada = 0.0
        n_segmentos = 0
        for outro in heatmap_ord:
            # Verifica sobreposição
            if outro["start_time"] < fim_janela and outro["end_time"] > inicio_janela:
                # Peso proporcional à sobreposição
                sobreposicao = min(outro["end_time"], fim_janela) - max(outro["start_time"], inicio_janela)
                duracao_seg  = outro["end_time"] - outro["start_time"]
                peso = sobreposicao / duracao_seg if duracao_seg > 0 else 1.0
                intensidade_acumulada += outro["value"] * peso
                n_segmentos += 1

        intensidade_media = intensidade_acumulada / n_segmentos if n_segmentos > 0 else 0.0

        if intensidade_media > melhor_intensidade:
            melhor_intensidade = intensidade_media
            melhor_inicio      = inicio_janela
            melhor_fim         = fim_janela

    return melhor_inicio, melhor_fim, melhor_intensidade


def detectar_pico(video_url: str) -> dict:
    """
    Detecta o trecho de maior replay no vídeo.

    Retorna dict com:
      - inicio_s    : segundo de início do trecho
      - fim_s       : segundo de fim do trecho
      - duracao_s   : duração do trecho em segundos
      - intensidade : intensidade média do pico (0.0-1.0)
      - heatmap_disponivel : bool (se o YouTube forneceu o heatmap)
    """
    metadados = _obter_metadados(video_url)

    titulo    = metadados.get("title", "")
    duracao_total = metadados.get("duration", 0) or 0
    heatmap   = metadados.get("heatmap", [])

    print(f"  🎬 Título : {titulo}")
    print(f"  ⏱️  Duração: {duracao_total/60:.1f} min ({duracao_total}s)")
    print(f"  📊 Heatmap: {len(heatmap)} segmentos disponíveis")

    if heatmap:
        # ── Usar heatmap real do YouTube ─────────────────────────────────────
        print(f"  ✅ Heatmap disponível! Calculando pico de replay...")

        # Testa diferentes janelas de duração e pega a melhor
        melhor_resultado = None
        melhor_score     = 0.0

        for duracao_janela in [DURACAO_MINIMA_S, DURACAO_IDEAL_S, DURACAO_MAXIMA_S]:
            inicio, fim, intensidade = _janela_deslizante(heatmap, duracao_janela)
            if intensidade > melhor_score:
                melhor_score     = intensidade
                melhor_resultado = (inicio, fim, intensidade, duracao_janela)

        inicio_s, fim_s, intensidade, dur_janela = melhor_resultado

        # Garante que não ultrapassa a duração do vídeo
        if fim_s > duracao_total:
            fim_s = duracao_total
            inicio_s = max(0, fim_s - dur_janela)

        print(f"  🎯 Pico encontrado:")
        print(f"     Início   : {inicio_s:.1f}s ({inicio_s/60:.1f} min)")
        print(f"     Fim      : {fim_s:.1f}s ({fim_s/60:.1f} min)")
        print(f"     Duração  : {fim_s - inicio_s:.1f}s")
        print(f"     Intensidade: {intensidade:.2%}")

        return {
            "inicio_s":           round(inicio_s, 1),
            "fim_s":              round(fim_s, 1),
            "duracao_s":          round(fim_s - inicio_s, 1),
            "intensidade":        round(intensidade, 4),
            "heatmap_disponivel": True,
            "titulo_video":       titulo,
        }

    else:
        # ── Fallback: sem heatmap, pega o terço médio do vídeo ──────────────
        print(f"  ⚠️  Heatmap não disponível. Usando fallback (terço médio)...")

        # Podcasts tendem a ter momentos bons no terço médio
        inicio_s = duracao_total * 0.35
        fim_s    = inicio_s + DURACAO_IDEAL_S

        if fim_s > duracao_total:
            fim_s    = duracao_total
            inicio_s = max(0, fim_s - DURACAO_IDEAL_S)

        print(f"  📍 Trecho selecionado (fallback):")
        print(f"     Início  : {inicio_s:.1f}s ({inicio_s/60:.1f} min)")
        print(f"     Fim     : {fim_s:.1f}s ({fim_s/60:.1f} min)")
        print(f"     Duração : {fim_s - inicio_s:.1f}s")

        return {
            "inicio_s":           round(inicio_s, 1),
            "fim_s":              round(fim_s, 1),
            "duracao_s":          round(fim_s - inicio_s, 1),
            "intensidade":        0.0,
            "heatmap_disponivel": False,
            "titulo_video":       titulo,
        }


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    resultado = detectar_pico(url)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
