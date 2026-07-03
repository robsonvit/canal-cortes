"""
selecionar_video.py
───────────────────
Passo 1 do Pipeline Canal Cortes.

Monitora os canais configurados em data/canais.json e seleciona
o vídeo mais recente ainda não processado.

Lógica:
  1. Lê lista de canais de data/canais.json
  2. Para cada canal ativo, busca os vídeos mais recentes via yt-dlp
  3. Filtra os já processados (data/videos_processados.json)
  4. Retorna o vídeo mais recente elegível com seus metadados
"""

import os
import json
import subprocess
import random
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ytdlp_helper import args_base_ytdlp

ROOT_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANAIS_FILE    = os.path.join(ROOT_DIR, "data", "canais.json")
TRACKING_FILE  = os.path.join(ROOT_DIR, "data", "videos_processados.json")


# ─────────────────────────────────────────────────────────────────────────────
# Tracking
# ─────────────────────────────────────────────────────────────────────────────
def _carregar_processados() -> dict:
    """Carrega JSON de vídeos já processados."""
    os.makedirs(os.path.join(ROOT_DIR, "data"), exist_ok=True)
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def salvar_processado(video_id: str, dados: dict):
    """Registra um vídeo como processado."""
    processados = _carregar_processados()
    processados[video_id] = {
        "data": datetime.now(timezone.utc).isoformat(),
        "titulo": dados.get("titulo", ""),
        "canal": dados.get("canal", ""),
    }
    with open(TRACKING_FILE, "w", encoding="utf-8") as f:
        json.dump(processados, f, indent=2, ensure_ascii=False)
    print(f"  ✅ Vídeo {video_id} registrado como processado.")


# ─────────────────────────────────────────────────────────────────────────────
# Busca de vídeos recentes via yt-dlp
# ─────────────────────────────────────────────────────────────────────────────
def _buscar_videos_canal(canal: dict, max_videos: int = 5) -> list:
    """
    Usa yt-dlp para listar os vídeos mais recentes de um canal.
    Retorna lista de dicts com {id, titulo, duracao, url}.
    """
    url = canal["url"] + "/videos"
    print(f"  🔍 Buscando vídeos de: {canal['nome']} ({url})")

    cmd = args_base_ytdlp([
        "--flat-playlist",
        "--playlist-end", str(max_videos),
        "--dump-json",
        "--quiet",
    ]) + [url]

    try:
        resultado = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if resultado.returncode != 0:
            print(f"  ⚠️  Erro ao buscar {canal['nome']}: {resultado.stderr[:200]}")
            return []

        videos = []
        for linha in resultado.stdout.strip().split("\n"):
            if not linha.strip():
                continue
            try:
                info = json.loads(linha)
                vid_id   = info.get("id", "")
                titulo   = info.get("title", "Sem título")
                duracao  = info.get("duration", 0)

                # Filtra vídeos muito curtos (menos de 3 minutos) ou estreias futuras (duração 0/None)
                if not duracao or duracao < 180:
                    continue

                if vid_id:
                    videos.append({
                        "id":      vid_id,
                        "titulo":  titulo,
                        "duracao": duracao,
                        "canal":   canal["nome"],
                        "url":     f"https://www.youtube.com/watch?v={vid_id}",
                    })
            except json.JSONDecodeError:
                continue

        print(f"  📋 {len(videos)} vídeos encontrados em {canal['nome']}")
        return videos

    except subprocess.TimeoutExpired:
        print(f"  ⚠️  Timeout ao buscar {canal['nome']}")
        return []
    except Exception as e:
        print(f"  ⚠️  Erro inesperado ao buscar {canal['nome']}: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Seleção principal
# ─────────────────────────────────────────────────────────────────────────────
def selecionar_video() -> dict:
    """
    Percorre todos os canais ativos e retorna o vídeo mais recente
    ainda não processado. Raise RuntimeError se não encontrar nenhum.
    """
    # Carrega configs
    with open(CANAIS_FILE, encoding="utf-8") as f:
        config = json.load(f)

    canais_ativos = [c for c in config["canais"] if c.get("ativo", True)]
    processados   = _carregar_processados()

    print(f"  📡 Monitorando {len(canais_ativos)} canais...")

    todos_candidatos = []

    # Canal específico forçado via env var (útil para testes)
    canal_forcado_url = os.environ.get("CANAL_URL")
    if canal_forcado_url:
        canais_ativos = [{"nome": "Forçado", "url": canal_forcado_url, "ativo": True}]
        print(f"  🎯 Canal forçado via CANAL_URL: {canal_forcado_url}")

    for canal in canais_ativos:
        videos = _buscar_videos_canal(canal, max_videos=5)
        for v in videos:
            if v["id"] not in processados:
                todos_candidatos.append(v)

    if not todos_candidatos:
        raise RuntimeError(
            "❌ Nenhum vídeo elegível encontrado. "
            "Todos os vídeos recentes já foram processados."
        )

    # Embaralha para variar canais entre execuções, pega o primeiro
    random.shuffle(todos_candidatos)
    escolhido = todos_candidatos[0]

    print(f"\n  🎬 Vídeo selecionado:")
    print(f"     Canal : {escolhido['canal']}")
    print(f"     Título: {escolhido['titulo']}")
    print(f"     URL   : {escolhido['url']}")
    duracao_min = (escolhido.get('duracao') or 0) / 60
    print(f"     Duração: {duracao_min:.0f} min")

    return escolhido


if __name__ == "__main__":
    v = selecionar_video()
    print(json.dumps(v, ensure_ascii=False, indent=2))
