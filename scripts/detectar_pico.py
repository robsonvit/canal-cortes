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
DURACAO_MINIMA_S = 40
DURACAO_MAXIMA_S = 180   # Sem limite rígido de 60s, pode ser até 3 minutos
DURACAO_IDEAL_S  = 60    # Duração base de fallback

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


def _encontrar_picos_dinamicos(heatmap: list, duracao_total: float) -> list:
    """
    Encontra o 'morro' completo de cada pico de interesse.
    Expande para a esquerda e para a direita a partir do ponto mais quente,
    enquanto a intensidade for no mínimo 30% do pico.
    Retorna lista de (inicio_s, fim_s, intensidade) ordenados por intensidade.
    """
    if not heatmap:
        return []

    # Encontra picos locais (pontos que são maiores que seus vizinhos)
    heatmap_ord = sorted(heatmap, key=lambda x: x["start_time"])
    
    picos_locais = []
    for i, seg in enumerate(heatmap_ord):
        val = seg["value"]
        if val < 0.1: # Ignora ruído baixo
            continue
        # Verifica se é pico local
        esq = heatmap_ord[i-1]["value"] if i > 0 else 0
        dir = heatmap_ord[i+1]["value"] if i < len(heatmap_ord)-1 else 0
        if val >= esq and val >= dir:
            picos_locais.append((i, seg))
            
    # Para cada pico local, expande
    candidatos = []
    for idx_pico, seg_pico in picos_locais:
        intensidade_pico = seg_pico["value"]
        limiar = intensidade_pico * 0.30  # Caiu 70% = acabou o assunto
        
        idx_esq = idx_pico
        while idx_esq > 0 and heatmap_ord[idx_esq - 1]["value"] >= limiar:
            idx_esq -= 1
            
        idx_dir = idx_pico
        while idx_dir < len(heatmap_ord) - 1 and heatmap_ord[idx_dir + 1]["value"] >= limiar:
            idx_dir += 1
            
        inicio = heatmap_ord[idx_esq]["start_time"]
        fim    = heatmap_ord[idx_dir]["end_time"]
        
        # Garante duração mínima
        dur = fim - inicio
        if dur < DURACAO_MINIMA_S:
            falta = DURACAO_MINIMA_S - dur
            inicio = max(0, inicio - falta/2)
            fim    = min(duracao_total, fim + falta/2)
            
        # Garante duração máxima
        dur = fim - inicio
        if dur > DURACAO_MAXIMA_S:
            centro = (inicio + fim) / 2
            inicio = max(0, centro - DURACAO_MAXIMA_S/2)
            fim    = min(duracao_total, centro + DURACAO_MAXIMA_S/2)
            
        # Calcula intensidade média do trecho final
        soma = 0
        n = 0
        for s in heatmap_ord:
            if s["start_time"] >= inicio and s["end_time"] <= fim:
                soma += s["value"]
                n += 1
                
        media = soma / n if n > 0 else intensidade_pico
        candidatos.append((inicio, fim, media))

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
        raise ValueError("Sem mapa de calor (heatmap). O vídeo não possui dados de retenção do YouTube.")

    # ── Usa heatmap real do YouTube ───────────────────────────────────────────
    print(f"  ✅ Heatmap disponível! Calculando múltiplos picos com duração dinâmica...")

    candidatos = _encontrar_picos_dinamicos(heatmap, duracao_total)
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
