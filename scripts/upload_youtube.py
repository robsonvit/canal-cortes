"""
upload_youtube.py
─────────────────
Passo 7 do Pipeline Canal Cortes.

Faz upload do Short finalizado para o YouTube via YouTube Data API v3,
usando credenciais OAuth 2.0 (refresh token).

Baseado no upload_youtube.py do Canal Oração, adaptado para Shorts:
  ✅ Publicação imediata (sem agendamento — Shorts funcionam melhor assim)
  ✅ Título otimizado para Shorts com hashtag #Shorts
  ✅ Descrição creditando o canal de origem
  ✅ Categoria People & Blogs (22)
  ✅ Não é para crianças

Secrets necessários (GitHub → Settings → Secrets → Actions):
  YOUTUBE_CLIENT_ID
  YOUTUBE_CLIENT_SECRET
  YOUTUBE_REFRESH_TOKEN
"""

import os
import re
import json

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


def _obter_credenciais() -> Credentials:
    """Constrói credenciais OAuth a partir dos secrets do ambiente."""
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    creds.refresh(Request())
    return creds


def _sanitizar_nome_arquivo(titulo: str) -> str:
    """Converte título em nome de arquivo seguro."""
    nome = re.sub(r'[\\/*?:"<>|#]', '', titulo)
    nome = re.sub(r'\s+', '_', nome.strip())
    nome = re.sub(r'_{2,}', '_', nome)
    return nome[:80].rstrip('_') + ".mp4"


def _montar_titulo(titulo_original: str, canal_origem: str) -> str:
    """
    Monta o título do Short otimizado para engajamento.
    Máximo 100 caracteres no YouTube.
    """
    # Remove o nome do canal do título original se já estiver lá
    titulo_limpo = titulo_original.replace(canal_origem, "").strip(" |-—")

    # Limita e adiciona contexto
    limite = 85
    if len(titulo_limpo) > limite:
        titulo_limpo = titulo_limpo[:limite].rsplit(" ", 1)[0] + "..."

    return f"{titulo_limpo} #Shorts"


def _montar_descricao(dados: dict) -> str:
    """Monta a descrição do Short com créditos ao canal original."""
    canal    = dados.get("canal", "Podcast")
    titulo   = dados.get("titulo_video", "")
    url      = dados.get("url", "")
    texto    = dados.get("texto_transcricao", "")[:200]

    return f"""🎙️ Corte do podcast: {canal}
📺 Vídeo original: {url}

{texto}...

📌 Siga para mais cortes dos melhores momentos dos podcasts brasileiros!

#Shorts #{canal.replace(' ', '')} #Podcast #Cortes #Brasil
"""


def _montar_tags(dados: dict) -> list:
    """Gera tags otimizadas para o Short."""
    canal = dados.get("canal", "podcast")
    tags_base = [
        "Shorts", "podcast", "cortes de podcast", "melhores momentos",
        canal, canal.lower().replace(" ", ""),
        "podcast brasileiro", "Brasil", "motivação",
    ]

    # Adiciona temas extraídos pela IA se disponíveis
    temas = dados.get("temas", [])
    for tema in temas:
        tp = tema.get("tema_pt", "")
        if tp:
            tags_base.append(tp)

    # Limita a 500 caracteres totais
    tags_validas = []
    total_chars  = 0
    for tag in tags_base:
        tag = tag.strip()
        if tag and len(tag) <= 60:
            if total_chars + len(tag) + 1 <= 480:
                tags_validas.append(tag)
                total_chars += len(tag) + 1

    return tags_validas


def upload_youtube(video_path: str, dados: dict) -> str:
    """
    Faz upload do Short para o YouTube.

    Args:
        video_path : caminho do arquivo MP4 final
        dados      : dict com metadados (titulo_video, canal, url, etc.)

    Returns:
        ID do vídeo criado no YouTube.
    """
    creds   = _obter_credenciais()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    # ── Metadados ────────────────────────────────────────────────────────────
    titulo    = _montar_titulo(
        dados.get("titulo_video", "Momento Incrível"),
        dados.get("canal", ""),
    )[:100]
    descricao = _montar_descricao(dados)[:5000]
    tags      = _montar_tags(dados)

    # ── Renomeia o arquivo com o título ──────────────────────────────────────
    if os.path.exists(video_path):
        diretorio  = os.path.dirname(video_path)
        novo_nome  = _sanitizar_nome_arquivo(titulo)
        novo_path  = os.path.join(diretorio, novo_nome)
        if video_path != novo_path:
            if os.path.exists(novo_path):
                os.remove(novo_path)
            os.rename(video_path, novo_path)
            video_path = novo_path
            print(f"   📁 Arquivo renomeado: {novo_nome}")

    # ── Body da requisição ───────────────────────────────────────────────────
    body = {
        "snippet": {
            "title":                titulo,
            "description":          descricao,
            "tags":                 tags,
            "categoryId":           "22",        # People & Blogs
            "defaultLanguage":      "pt-BR",
            "defaultAudioLanguage": "pt-BR",
        },
        "status": {
            "privacyStatus":           "public",   # Publicação imediata para Shorts
            "selfDeclaredMadeForKids": False,
            "madeForKids":             False,
        },
    }

    # ── Upload ───────────────────────────────────────────────────────────────
    print(f"📤 Iniciando upload do Short para o YouTube...")
    print(f"   Título    : {titulo}")
    print(f"   Tags      : {len(tags)} tags")
    print(f"   Canal     : {dados.get('canal', '-')}")

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,   # 10 MB por chunk
    )

    request  = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"   Upload: {pct}%", end="\r")

    video_id = response.get("id", "")
    print(f"\n✅ Short publicado! ID: {video_id}")
    print(f"   📱 https://www.youtube.com/shorts/{video_id}")
    print(f"   📺 https://www.youtube.com/watch?v={video_id}")

    return video_id


if __name__ == "__main__":
    dados_teste = {
        "titulo_video": "Momento incrível no Podpah",
        "canal": "Podpah",
        "url": "https://www.youtube.com/watch?v=example",
    }
    upload_youtube("output/short_final.mp4", dados_teste)
