"""
upload_youtube.py
─────────────────
Passo 7 do Pipeline Canal Cortes.

Faz upload do Short finalizado para o YouTube via YouTube Data API v3,
usando credenciais OAuth 2.0 (refresh token).

Melhorias de SEO:
  ✅ Título com gancho emocional gerado por Groq AI (baseado na transcrição real)
  ✅ Descrição rica com emojis, resumo do momento, créditos e CTA
  ✅ Até 20 tags temáticas geradas pela IA com base no conteúdo
  ✅ Fallback robusto se a IA falhar
  ✅ Adiciona o Short automaticamente à playlist do canal de origem

Secrets necessários (GitHub → Settings → Secrets → Actions):
  YOUTUBE_CLIENT_ID
  YOUTUBE_CLIENT_SECRET
  YOUTUBE_REFRESH_TOKEN
  GROQ_API_KEY
"""

import os
import re
import json

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


# ─────────────────────────────────────────────────────────────────────────────
# Credenciais OAuth
# ─────────────────────────────────────────────────────────────────────────────
def _obter_credenciais() -> Credentials:
    """Constrói credenciais OAuth a partir dos secrets do ambiente."""
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=[
            "https://www.googleapis.com/auth/youtube",
            "https://www.googleapis.com/auth/youtube.upload",
        ],
    )
    creds.refresh(Request())
    return creds


# ─────────────────────────────────────────────────────────────────────────────
# Utilitários
# ─────────────────────────────────────────────────────────────────────────────
def _sanitizar_nome_arquivo(titulo: str) -> str:
    """Converte título em nome de arquivo seguro."""
    nome = re.sub(r'[\\/*?:"<>|#]', '', titulo)
    nome = re.sub(r'\s+', '_', nome.strip())
    nome = re.sub(r'_{2,}', '_', nome)
    return nome[:80].rstrip('_') + ".mp4"


def _limpar_hashtags_titulo(titulo: str) -> str:
    """Remove hashtags do meio do título para não parecer spam."""
    return re.sub(r'#\w+', '', titulo).strip()


# ─────────────────────────────────────────────────────────────────────────────
# SEO com Groq AI — coração do módulo
# ─────────────────────────────────────────────────────────────────────────────
def _gerar_seo_com_ia(dados: dict) -> dict:
    """
    Usa Groq AI (Llama 3.3 70B) para gerar título, descrição e tags
    otimizados para YouTube Shorts baseados no conteúdo real da transcrição.

    Retorna dict com: titulo, descricao, tags (list)
    """
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        print("  ⚠️  GROQ_API_KEY não configurado — usando SEO básico.")
        return {}

    canal        = dados.get("canal", "Podcast")
    titulo_orig  = dados.get("titulo_video", dados.get("titulo", ""))
    url_orig     = dados.get("url", "")
    transcricao  = dados.get("texto_transcricao", "")[:1500]
    temas        = dados.get("temas", [])
    temas_str    = ", ".join([t.get("tema_pt", "") for t in temas if t.get("tema_pt")])

    prompt = f"""Você é um especialista em SEO para YouTube Shorts e podcasts brasileiros.

Analise este trecho de podcast e crie metadados ALTAMENTE OTIMIZADOS para viralizar no YouTube Shorts.

=== DADOS DO VÍDEO ===
Canal de origem: {canal}
Título do episódio original: {titulo_orig}
URL original: {url_orig}
Temas identificados: {temas_str if temas_str else "N/A"}
Transcrição do trecho:
{transcricao}

=== INSTRUÇÕES PARA TÍTULO ===
- Máximo 90 caracteres (sem contar #Shorts)
- Crie um GANCHO FORTE: use pergunta provocativa, dado surpreendente, afirmação polêmica ou frase de impacto
- Extraia a frase mais marcante ou surpreendente da transcrição
- NÃO mencione o nome do canal no título
- Termine com " #Shorts" (com espaço)
- Exemplos de ganchos bons: "Você está desperdiçando seu talento e nem sabe #Shorts", "Por que 90% das pessoas não ficam ricas #Shorts"

=== INSTRUÇÕES PARA DESCRIÇÃO ===
- 3 parágrafos com emojis
- Parágrafo 1: Resumo do momento mais impactante (2-3 frases, linguagem direta)
- Parágrafo 2: Créditos + link para o vídeo completo
- Parágrafo 3: CTA + 5-8 hashtags temáticas relevantes
- Máximo 800 caracteres total

=== INSTRUÇÕES PARA TAGS ===
- 15 a 20 tags variadas
- Inclua: tags do tema principal, variações do nome do canal, termos de busca que o público usaria
- Misture português e inglês quando fizer sentido
- Inclua "shorts", "podcast brasileiro", "cortes de podcast"
- Tags específicas sobre o assunto discutido (não genéricas!)
- Máximo 500 caracteres somando todas as tags

Retorne APENAS um JSON válido neste formato exato:
{{
  "titulo": "Título com gancho forte aqui #Shorts",
  "descricao": "Parágrafo 1 aqui...\\n\\nParágrafo 2 com créditos...\\n\\nParágrafo 3 CTA e hashtags...",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10", "tag11", "tag12", "tag13", "tag14", "tag15"]
}}

Retorne apenas o JSON, sem explicações adicionais."""

    try:
        from groq import Groq
        cliente = Groq(api_key=groq_key)
        resp = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=800,
        )
        conteudo = resp.choices[0].message.content.strip()

        # Extrai JSON da resposta
        match = re.search(r'\{.*\}', conteudo, re.DOTALL)
        if match:
            seo = json.loads(match.group())
            titulo   = seo.get("titulo", "").strip()[:100]
            descricao = seo.get("descricao", "").strip()[:5000]
            tags      = seo.get("tags", [])

            if titulo and descricao and tags:
                print(f"  🤖 SEO gerado pela IA:")
                print(f"     Título   : {titulo}")
                print(f"     Tags     : {len(tags)} tags geradas")
                print(f"     Descrição: {len(descricao)} chars")
                return {"titulo": titulo, "descricao": descricao, "tags": tags}

    except Exception as e:
        print(f"  ⚠️  Groq AI falhou ao gerar SEO: {e}")

    return {}


# ─────────────────────────────────────────────────────────────────────────────
# SEO Fallback — usado quando a IA não está disponível
# ─────────────────────────────────────────────────────────────────────────────
def _montar_titulo_fallback(titulo_original: str, canal_origem: str) -> str:
    """Monta o título do Short com gancho básico."""
    titulo_limpo = titulo_original.replace(canal_origem, "").strip(" |-—")
    limite = 85
    if len(titulo_limpo) > limite:
        titulo_limpo = titulo_limpo[:limite].rsplit(" ", 1)[0] + "..."
    return f"{titulo_limpo} #Shorts"


def _montar_descricao_fallback(dados: dict) -> str:
    """Monta a descrição do Short com créditos ao canal original."""
    canal   = dados.get("canal", "Podcast")
    titulo  = dados.get("titulo_video", dados.get("titulo", ""))
    url     = dados.get("url", "")
    texto   = dados.get("texto_transcricao", "")[:300]

    canal_sem_espaco = canal.replace(' ', '')

    return f"""🎙️ Um dos momentos mais impactantes do {canal}!

📺 Assista o episódio completo: {titulo}
🔗 {url}

📌 Siga para mais cortes dos melhores momentos dos podcasts brasileiros!

#{canal_sem_espaco} #Podcast #PodcastBrasileiro #Cortes #CortesdePodcast #Shorts #Brasil #Viral"""


def _montar_tags_fallback(dados: dict) -> list:
    """Gera tags básicas otimizadas para o Short."""
    canal = dados.get("canal", "podcast")
    canal_sem_espaco = canal.lower().replace(" ", "")

    tags_base = [
        "shorts", "podcast", "cortes de podcast", "podcast brasileiro",
        "melhores momentos", "viral", "brasil", "motivação",
        canal, canal_sem_espaco,
        f"cortes {canal.lower()}", f"{canal.lower()} podcast",
        "short", "reels", "entretenimento",
    ]

    # Adiciona temas extraídos pela IA se disponíveis
    temas = dados.get("temas", [])
    for tema in temas:
        tp = tema.get("tema_pt", "")
        if tp and tp not in tags_base:
            tags_base.append(tp)

    # Limita a 500 caracteres totais
    tags_validas = []
    total_chars  = 0
    for tag in tags_base:
        tag = tag.strip()
        if tag and len(tag) <= 60:
            if total_chars + len(tag) + 1 <= 490:
                tags_validas.append(tag)
                total_chars += len(tag) + 1

    return tags_validas


# ─────────────────────────────────────────────────────────────────────────────
# Playlist — adiciona o Short à playlist do canal de origem
# ─────────────────────────────────────────────────────────────────────────────
def _obter_playlist_id_do_canal(canal_nome: str) -> str | None:
    """
    Busca o playlist_id do canal de origem no canais.json.
    Retorna None se não encontrar ou se não estiver configurado.
    """
    root_dir    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    canais_file = os.path.join(root_dir, "data", "canais.json")

    try:
        with open(canais_file, encoding="utf-8") as f:
            config = json.load(f)

        for canal in config.get("canais", []):
            if canal.get("nome", "").lower() == canal_nome.lower():
                playlist_id = canal.get("playlist_id", "")
                if playlist_id and playlist_id != "COLE_O_ID_DA_PLAYLIST_AQUI":
                    return playlist_id
                else:
                    print(f"  ⚠️  Canal '{canal_nome}' sem playlist_id configurado.")
                    print(f"       Crie uma playlist no YouTube Studio e adicione o ID em data/canais.json")
                    return None

        print(f"  ⚠️  Canal '{canal_nome}' não encontrado em canais.json")
        return None

    except Exception as e:
        print(f"  ⚠️  Erro ao ler canais.json: {e}")
        return None


def _adicionar_a_playlist(youtube, video_id: str, canal_nome: str):
    """
    Adiciona o Short publicado à playlist do canal de origem.
    Falha silenciosamente para não bloquear o pipeline.
    """
    playlist_id = _obter_playlist_id_do_canal(canal_nome)
    if not playlist_id:
        return

    print(f"\n  📋 Adicionando Short à playlist do canal '{canal_nome}'...")
    print(f"     Playlist ID: {playlist_id}")

    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id,
                    },
                }
            },
        ).execute()
        print(f"  ✅ Short adicionado à playlist com sucesso!")

    except Exception as e:
        print(f"  ⚠️  Falha ao adicionar à playlist: {e}")
        print(f"       O vídeo foi publicado normalmente. Verifique as permissões do OAuth.")


# ─────────────────────────────────────────────────────────────────────────────
# Função principal de upload
# ─────────────────────────────────────────────────────────────────────────────
def upload_youtube(video_path: str, dados: dict) -> str:
    """
    Faz upload do Short para o YouTube com SEO otimizado por IA.

    Args:
        video_path : caminho do arquivo MP4 final
        dados      : dict com metadados (titulo_video, canal, url, texto_transcricao, temas, etc.)

    Returns:
        ID do vídeo criado no YouTube.
    """
    creds   = _obter_credenciais()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    canal = dados.get("canal", "Podcast")

    # ── Gera SEO com IA ──────────────────────────────────────────────────────
    print(f"\n  🤖 Gerando SEO otimizado com Groq AI...")
    seo_ia = _gerar_seo_com_ia(dados)

    if seo_ia:
        titulo    = seo_ia["titulo"][:100]
        descricao = seo_ia["descricao"][:5000]
        tags_raw  = seo_ia["tags"]
    else:
        print(f"  📝 Usando SEO fallback...")
        titulo    = _montar_titulo_fallback(
            dados.get("titulo_video", dados.get("titulo", "Momento Incrível")),
            canal,
        )[:100]
        descricao = _montar_descricao_fallback(dados)[:5000]
        tags_raw  = _montar_tags_fallback(dados)

    # Valida e trunca tags para o limite do YouTube (500 chars totais)
    tags_validas = []
    total_chars  = 0
    for tag in tags_raw:
        tag = str(tag).strip()
        if tag and len(tag) <= 60:
            if total_chars + len(tag) + 1 <= 490:
                tags_validas.append(tag)
                total_chars += len(tag) + 1

    # ── Renomeia o arquivo com o título ──────────────────────────────────────
    if os.path.exists(video_path):
        diretorio = os.path.dirname(video_path)
        novo_nome = _sanitizar_nome_arquivo(titulo)
        novo_path = os.path.join(diretorio, novo_nome)
        if video_path != novo_path:
            if os.path.exists(novo_path):
                os.remove(novo_path)
            os.rename(video_path, novo_path)
            video_path = novo_path
            print(f"  📁 Arquivo renomeado: {novo_nome}")

    # ── Body da requisição ───────────────────────────────────────────────────
    body = {
        "snippet": {
            "title":                titulo,
            "description":          descricao,
            "tags":                 tags_validas,
            "categoryId":           "22",        # People & Blogs
            "defaultLanguage":      "pt-BR",
            "defaultAudioLanguage": "pt-BR",
        },
        "status": {
            "privacyStatus":           "public",
            "selfDeclaredMadeForKids": False,
            "madeForKids":             False,
        },
    }

    # ── Upload ───────────────────────────────────────────────────────────────
    print(f"\n  📤 Iniciando upload do Short para o YouTube...")
    print(f"     Título    : {titulo}")
    print(f"     Tags      : {len(tags_validas)} tags ({total_chars} chars)")
    print(f"     Descrição : {len(descricao)} chars")
    print(f"     Canal     : {canal}")

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
            print(f"  Upload: {pct}%", end="\r")

    video_id = response.get("id", "")
    print(f"\n  ✅ Short publicado! ID: {video_id}")
    print(f"     📱 https://www.youtube.com/shorts/{video_id}")
    print(f"     📺 https://www.youtube.com/watch?v={video_id}")

    # ── Adiciona à playlist do canal ─────────────────────────────────────────
    _adicionar_a_playlist(youtube, video_id, canal)

    return video_id


if __name__ == "__main__":
    dados_teste = {
        "titulo_video": "O segredo que ninguém te conta sobre dinheiro e liberdade financeira",
        "canal": "Podpah",
        "url": "https://www.youtube.com/watch?v=example",
        "texto_transcricao": "A maioria das pessoas trabalha a vida toda e nunca consegue sair do ciclo...",
    }
    upload_youtube("output/short_final.mp4", dados_teste)

