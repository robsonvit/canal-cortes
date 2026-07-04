"""
detectar_pico.py
────────────────
Passo 2 do Pipeline Canal Cortes.

Extrai o heatmap do YouTube via yt-dlp e encontra os segmentos
com maior intensidade de replay (os trechos mais assistidos).

O heatmap retornado pelo yt-dlp é uma lista de objetos:
  [{"start_time": 0.0, "end_time": 5.0, "value": 0.3}, ...]
  onde "value" é a intensidade normalizada (0.0 a 1.0).

Estratégia:
  1. Obtém metadados completos via yt-dlp --dump-json
  2. Extrai o campo "heatmap"
  3. Aplica janela deslizante para pontuação de cada posição
  4. Seleciona os N melhores picos com espaçamento mínimo entre eles
  5. Expande ligeiramente o início para capturar o contexto
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

# Espaçamento mínimo entre picos (segundos) — evita picos sobrepostos
ESPACAMENTO_MIN_S = 120   # 2 minutos de distância mínima

# Máximo de picos por vídeo
MAX_PICOS = 6


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


def _pontuar_posicoes(heatmap: list, duracao_total: float, duracao_janela: float) -> list:
    """
    Calcula a intensidade acumulada para cada posição de janela possível.
    Retorna lista de (inicio_s, fim_s, intensidade_media) ordenada por início.
    """
    heatmap_ord = sorted(heatmap, key=lambda x: x["start_time"])
    candidatos = []

    for seg in heatmap_ord:
        inicio_janela = seg["start_time"]
        fim_janela    = inicio_janela + duracao_janela

        # Não usa janelas que ultrapassem o fim do vídeo
        if fim_janela > duracao_total + 5:
            continue

        fim_janela = min(fim_janela, duracao_total)

        intensidade_acumulada = 0.0
        n_segs = 0
        for outro in heatmap_ord:
            if outro["start_time"] < fim_janela and outro["end_time"] > inicio_janela:
                sobreposicao = min(outro["end_time"], fim_janela) - max(outro["start_time"], inicio_janela)
                duracao_seg  = outro["end_time"] - outro["start_time"]
                peso = sobreposicao / duracao_seg if duracao_seg > 0 else 1.0
                intensidade_acumulada += outro["value"] * peso
                n_segs += 1

        intensidade_media = intensidade_acumulada / n_segs if n_segs > 0 else 0.0
        candidatos.append((inicio_janela, fim_janela, intensidade_media))

    return candidatos


def _selecionar_picos_com_espacamento(candidatos: list, n_max: int, espacamento_min: float) -> list:
    """
    Seleciona os N melhores picos garantindo espaçamento mínimo entre eles.
    Algoritmo greedy: ordena por intensidade, aceita se estiver longe de todos já selecionados.

    Returns:
        Lista de (inicio_s, fim_s, intensidade) dos melhores picos, ordenada por intensidade desc.
    """
    # Ordena todos os candidatos por intensidade (maior primeiro)
    ordenados = sorted(candidatos, key=lambda x: x[2], reverse=True)

    selecionados = []
    for inicio, fim, intensidade in ordenados:
        # Verifica se está longe o suficiente de todos os picos já selecionados
        muito_proximo = any(
            abs(inicio - p[0]) < espacamento_min
            for p in selecionados
        )
        if not muito_proximo:
            selecionados.append((inicio, fim, intensidade))
            if len(selecionados) >= n_max:
                break

    # Ordena pelo tempo de início para exibição
    selecionados.sort(key=lambda x: x[2], reverse=True)
    return selecionados


def detectar_picos(video_url: str, n_max: int = MAX_PICOS, espacamento_min: float = ESPACAMENTO_MIN_S) -> list:
    """
    Detecta os N maiores picos de replay no vídeo com espaçamento mínimo.

    Args:
        video_url      : URL do vídeo
        n_max          : número máximo de picos a retornar
        espacamento_min: distância mínima em segundos entre picos

    Returns:
        Lista de dicts ordenada por intensidade (melhor primeiro):
        [{inicio_s, fim_s, duracao_s, intensidade, rank, heatmap_disponivel, titulo_video}]
    """
    metadados = _obter_metadados(video_url)

    titulo        = metadados.get("title", "")
    duracao_total = metadados.get("duration", 0) or 0
    heatmap       = metadados.get("heatmap") or []

    print(f"  🎬 Título : {titulo}")
    print(f"  ⏱️  Duração: {duracao_total/60:.1f} min ({duracao_total}s)")
    print(f"  📊 Heatmap: {len(heatmap)} segmentos disponíveis")

    if not heatmap:
        # ── Fallback sem heatmap: divide o vídeo em partes iguais ─────────────
        print(f"  ⚠️  Heatmap não disponível. Gerando {n_max} trechos por posição...")

        picos = []
        # Divide o vídeo em segmentos distribuídos (excluindo os 10% iniciais e finais)
        inicio_util = duracao_total * 0.10
        fim_util    = duracao_total * 0.90
        espaco      = (fim_util - inicio_util) / n_max

        for i in range(n_max):
            inicio_s = inicio_util + i * espaco
            fim_s    = min(inicio_s + DURACAO_IDEAL_S, duracao_total)
            picos.append({
                "inicio_s":          round(inicio_s, 1),
                "fim_s":             round(fim_s, 1),
                "duracao_s":         round(fim_s - inicio_s, 1),
                "intensidade":       0.0,
                "rank":              i + 1,
                "heatmap_disponivel": False,
                "titulo_video":      titulo,
            })
        return picos

    # ── Usa heatmap real do YouTube ───────────────────────────────────────────
    print(f"  ✅ Heatmap disponível! Calculando múltiplos picos de replay...")

    candidatos = _pontuar_posicoes(heatmap, duracao_total, DURACAO_IDEAL_S)
    melhores   = _selecionar_picos_com_espacamento(candidatos, n_max, espacamento_min)

    resultado = []
    for rank, (inicio_s, fim_s, intensidade) in enumerate(melhores, 1):
        resultado.append({
            "inicio_s":          round(inicio_s, 1),
            "fim_s":             round(fim_s, 1),
            "duracao_s":         round(fim_s - inicio_s, 1),
            "intensidade":       round(intensidade, 4),
            "rank":              rank,
            "heatmap_disponivel": True,
            "titulo_video":      titulo,
        })

    print(f"  🎯 {len(resultado)} picos encontrados:")
    for p in resultado:
        print(f"     Rank {p['rank']}: {p['inicio_s']:.0f}s–{p['fim_s']:.0f}s"
              f" ({p['inicio_s']/60:.1f}–{p['fim_s']/60:.1f} min)"
              f" | intensidade {p['intensidade']:.2%}")

    return resultado


def detectar_pico(video_url: str) -> dict:
    """
    Wrapper de compatibilidade — retorna apenas o MELHOR pico.
    Use detectar_picos() para obter todos os picos disponíveis.
    """
    picos = detectar_picos(video_url, n_max=1)
    return picos[0] if picos else {}


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    picos = detectar_picos(url)
    print(json.dumps(picos, ensure_ascii=False, indent=2))
