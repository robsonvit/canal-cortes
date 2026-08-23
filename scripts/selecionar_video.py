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
from ytdlp_helper import args_base_ytdlp_listing

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


def salvar_processado(video_id: str, dados: dict, pico_inicio_s: float = None, total_picos: int = 1):
    """
    Registra um pico de um vídeo como processado.

    - Se o vídeo ainda não existe no tracking, cria entrada.
    - Adiciona pico_inicio_s à lista de picos_usados.
    - Marca picos_esgotados=True quando todos os picos do vídeo tiverem sido usados.
    """
    processados = _carregar_processados()
    agora = datetime.now(timezone.utc).isoformat()

    entrada = processados.get(video_id, {})

    # Compatibilidade com formato antigo (chave 'data' direta)
    if "data" in entrada and "picos_usados" not in entrada:
        # Formato antigo — marca como esgotado
        entrada = {
            "data_primeiro":   entrada["data"],
            "data_ultimo":     agora,
            "titulo":          entrada.get("titulo", dados.get("titulo", "")),
            "canal":           entrada.get("canal",  dados.get("canal",  "")),
            "picos_usados":    [],
            "total_picos":     0,
            "picos_esgotados": True,   # Formato antigo: considera esgotado
        }

    picos_usados = entrada.get("picos_usados", [])

    if pico_inicio_s is not None and pico_inicio_s not in picos_usados:
        picos_usados.append(pico_inicio_s)

    picos_esgotados = len(picos_usados) >= total_picos

    processados[video_id] = {
        "data_primeiro": entrada.get("data_primeiro", agora),
        "data_ultimo":   agora,
        "titulo":        dados.get("titulo", entrada.get("titulo", "")),
        "canal":         dados.get("canal",  entrada.get("canal",  "")),
        "picos_usados":  picos_usados,
        "total_picos":   total_picos,
        "picos_esgotados": picos_esgotados,
    }

    with open(TRACKING_FILE, "w", encoding="utf-8") as f:
        json.dump(processados, f, indent=2, ensure_ascii=False)

    restantes = total_picos - len(picos_usados)
    status = "esgotado" if picos_esgotados else f"{restantes} pico(s) restante(s)"
    print(f"  ✅ Vídeo {video_id}: pico {pico_inicio_s}s registrado ({status})")


# ─────────────────────────────────────────────────────────────────────────────
# Busca de vídeos recentes via yt-dlp
# ─────────────────────────────────────────────────────────────────────────────
def _buscar_videos_canal(canal: dict, max_videos: int = 20) -> list:
    """
    Usa yt-dlp para listar os vídeos mais recentes de um canal.
    Retorna lista de dicts com {id, titulo, duracao, url, views}.
    """
    url = canal["url"] + "/videos"
    print(f"  🔍 Buscando vídeos de: {canal['nome']} ({url})")

    cmd = args_base_ytdlp_listing([
        "--flat-playlist",
        "--playlist-end", str(max_videos),
        "--dump-json",
        "--quiet",
    ]) + [url]

    try:
        resultado = subprocess.run(
            cmd,
            capture_output=True,
            text=True, encoding='utf-8', errors='replace',
            timeout=60,
        )

        # Fallback caso yt-dlp dê erro (ex: cookies.txt inválido ou problema de sessão)
        if resultado.returncode != 0:
            print(f"  ⚠️  Erro ao buscar {canal['nome']}: {resultado.stderr[:200]}")
            # Se deu erro e tínhamos cookies, tenta rodar de novo sem cookies
            if "--cookies" in cmd:
                print("  🔄 Tentando buscar sem cookies como fallback...")
                cmd_sem_cookies = [arg for arg in cmd if arg != "cookies.txt" and arg != "--cookies"]
                resultado = subprocess.run(
                    cmd_sem_cookies,
                    capture_output=True,
                    text=True, encoding='utf-8', errors='replace',
                    timeout=60,
                )
                if resultado.returncode != 0:
                    print(f"  ⚠️  Erro persistente sem cookies: {resultado.stderr[:200]}")
                    return []
            else:
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
                views    = info.get("view_count", 0) or 0

                # Filtra vídeos muito curtos (menos de 3 minutos) ou estreias futuras (duração 0/None)
                if not duracao or duracao < 180:
                    continue

                if vid_id:
                    videos.append({
                        "id":      vid_id,
                        "titulo":  titulo,
                        "duracao": duracao,
                        "views":   views,
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

    # Identifica canais que já foram processados hoje no horário local
    hoje_local = datetime.now().date()
    canais_processados_hoje = set()
    for vid, info in processados.items():
        if isinstance(info, dict) and "data_ultimo" in info:
            try:
                dt_utc = datetime.fromisoformat(info["data_ultimo"])
                dt_local = dt_utc.astimezone()
                if dt_local.date() == hoje_local:
                    c = info.get("canal")
                    if c:
                        canais_processados_hoje.add(c)
            except Exception:
                pass

    if canais_processados_hoje:
        print(f"  🚫 Canais que já postaram hoje e serão evitados: {', '.join(canais_processados_hoje)}")

    for canal in canais_ativos:
        videos = _buscar_videos_canal(canal, max_videos=20)
        for v in videos:
            entrada = processados.get(v["id"])
            if entrada is None:
                # Vídeo nunca processado — totalmente disponível
                todos_candidatos.append(v)
            elif isinstance(entrada, dict) and not entrada.get("picos_esgotados", True):
                # Vídeo já iniciado mas ainda tem picos disponíveis
                todos_candidatos.append(v)
            # else: formato antigo ou esgotado — ignora

    if not todos_candidatos:
        print("⚠️  Nenhum vídeo recente elegível encontrado. Buscando vídeos populares (com mais visualizações) como fallback...")
        # Altera a busca para trazer os mais populares usando playlist_sort=popular do extractor-args
        # Para isso passamos a flag correspondente na config de busca
        for canal in canais_ativos:
            # Para popular, podemos buscar em uma playlist maior (ex: 40 vídeos) para ter boa variedade
            url_popular = canal["url"] + "/videos"
            print(f"  🔍 Buscando vídeos populares de: {canal['nome']}")
            
            # Vamos construir o comando do yt-dlp usando a flag de popular
            cmd = args_base_ytdlp_listing([
                "--flat-playlist",
                "--playlist-end", "40",
                "--dump-json",
                "--quiet",
                "--extractor-args", "youtube:playlist_sort=popular",
                "--compat-options", "no-youtube-channel-redirect",
            ]) + [url_popular]
            
            try:
                resultado = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True, encoding='utf-8', errors='replace',
                    timeout=60,
                )
                
                # Fallback sem cookies caso falhe
                if resultado.returncode != 0 and "--cookies" in cmd:
                    cmd_sem_cookies = [arg for arg in cmd if arg != "cookies.txt" and arg != "--cookies"]
                    resultado = subprocess.run(
                        cmd_sem_cookies,
                        capture_output=True,
                        text=True, encoding='utf-8', errors='replace',
                        timeout=60,
                    )
                
                if resultado.returncode == 0:
                    videos_populares = []
                    for linha in resultado.stdout.strip().split("\n"):
                        if not linha.strip():
                            continue
                        try:
                            info = json.loads(linha)
                            vid_id   = info.get("id", "")
                            titulo   = info.get("title", "Sem título")
                            duracao  = info.get("duration", 0)
                            views    = info.get("view_count", 0) or 0
                            
                            if not duracao or duracao < 180:
                                continue
                                
                            if vid_id:
                                videos_populares.append({
                                    "id":      vid_id,
                                    "titulo":  titulo,
                                    "duracao": duracao,
                                    "views":   views,
                                    "canal":   canal["nome"],
                                    "url":     f"https://www.youtube.com/watch?v={vid_id}",
                                })
                        except json.JSONDecodeError:
                            continue
                    
                    # Filtra candidatos populares
                    for v in videos_populares:
                        entrada = processados.get(v["id"])
                        if entrada is None:
                            todos_candidatos.append(v)
                        elif isinstance(entrada, dict) and not entrada.get("picos_esgotados", True):
                            todos_candidatos.append(v)
            except Exception as e:
                print(f"  ⚠️  Erro ao buscar populares de {canal['nome']}: {e}")
                
        if not todos_candidatos:
            print("❌ ERRO: Mesmo buscando vídeos populares, nenhum candidato elegível com picos disponíveis foi encontrado.")
            sys.exit(0)
        else:
            # Como são populares, vamos ordenar pelo view_count decrescente (o de mais views primeiro)
            todos_candidatos.sort(key=lambda x: x.get("views", 0), reverse=True)
            print(f"  🔥 Encontrados {len(todos_candidatos)} vídeos populares elegíveis como fallback. Ordenados por visualizações.")

    # Filtra candidatos para evitar canais que já postaram hoje
    candidatos_filtrados = [v for v in todos_candidatos if v["canal"] not in canais_processados_hoje]
    if candidatos_filtrados:
        print(f"  🎯 Filtro ativo: Removidos {len(todos_candidatos) - len(candidatos_filtrados)} vídeos de canais que já postaram hoje.")
        todos_candidatos = candidatos_filtrados
    else:
        print("  ⚠️ Todos os canais ativos já postaram hoje. Usando fallback de repetição para evitar travamento da automação.")

    # Lógica de intercalação (alternar canais e vídeos)
    ultimo_uso_canal = {}
    ultimo_uso_video = {}

    for vid, info in processados.items():
        if isinstance(info, dict) and "data_ultimo" in info:
            dt = datetime.fromisoformat(info["data_ultimo"])
            c = info.get("canal", "")
            if c not in ultimo_uso_canal or dt > ultimo_uso_canal[c]:
                ultimo_uso_canal[c] = dt
            if vid not in ultimo_uso_video or dt > ultimo_uso_video[vid]:
                ultimo_uso_video[vid] = dt

    # Data mínima para canais/vídeos nunca usados
    min_date = datetime.min.replace(tzinfo=timezone.utc)

    def chave_ordenacao(v):
        t_canal = ultimo_uso_canal.get(v["canal"], min_date)
        t_video = ultimo_uso_video.get(v["id"], min_date)
        return (t_canal, t_video)

    # Embaralha para variar empates aleatoriamente
    random.shuffle(todos_candidatos)
    
    # Ordena priorizando canais menos recentes e, em seguida, vídeos menos recentes
    todos_candidatos.sort(key=chave_ordenacao)
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

