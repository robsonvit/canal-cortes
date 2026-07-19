"""
upload_youtube.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Passo 7 do Pipeline Canal Cortes.

Faz upload do Short finalizado para o YouTube via YouTube Data API v3,
usando credenciais OAuth 2.0 (refresh token).

Melhorias de SEO:
  âœ… TÃ­tulo com gancho emocional gerado por Groq AI (baseado na transcriÃ§Ã£o real)
  âœ… DescriÃ§Ã£o rica com emojis, resumo do momento, crÃ©ditos e CTA
  âœ… AtÃ© 20 tags temÃ¡ticas geradas pela IA com base no conteÃºdo
  âœ… Fallback robusto se a IA falhar
  âœ… Adiciona o Short automaticamente Ã  playlist do canal de origem

Secrets necessÃ¡rios (GitHub â†’ Settings â†’ Secrets â†’ Actions):
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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Credenciais OAuth
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _obter_credenciais() -> Credentials:
    """ConstrÃ³i credenciais OAuth a partir dos secrets do ambiente."""
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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# UtilitÃ¡rios
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _sanitizar_nome_arquivo(titulo: str) -> str:
    """Converte tÃ­tulo em nome de arquivo seguro."""
    nome = re.sub(r'[\\/*?:"<>|#]', '', titulo)
    nome = re.sub(r'\s+', '_', nome.strip())
    nome = re.sub(r'_{2,}', '_', nome)
    return nome[:80].rstrip('_') + ".mp4"


def _limpar_hashtags_titulo(titulo: str) -> str:
    """Remove hashtags do meio do tÃ­tulo para nÃ£o parecer spam."""
    return re.sub(r'#\w+', '', titulo).strip()


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# SEO com Groq AI â€” coraÃ§Ã£o do mÃ³dulo
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _gerar_seo_com_ia(dados: dict) -> dict:
    """
    Usa Groq AI (Llama 3.3 70B) para gerar tÃ­tulo, descriÃ§Ã£o e tags
    otimizados para YouTube Shorts baseados no conteÃºdo real da transcriÃ§Ã£o.

    Retorna dict com: titulo, descricao, tags (list)
    """
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        print("  âš ï¸  GROQ_API_KEY nÃ£o configurado â€” usando SEO bÃ¡sico.")
        return {}

    canal        = dados.get("canal", "Podcast")
    titulo_orig  = dados.get("titulo_video", dados.get("titulo", ""))
    url_orig     = dados.get("url", "")
    transcricao  = dados.get("texto_transcricao", "")[:1500]
    temas        = dados.get("temas", [])
    temas_str    = ", ".join([t.get("tema_pt", "") for t in temas if t.get("tema_pt")])

    prompt = f"""VocÃª Ã© um especialista em SEO para YouTube Shorts e podcasts brasileiros.

Analise este trecho de podcast e crie metadados ALTAMENTE OTIMIZADOS para viralizar no YouTube Shorts.

=== DADOS DO VÃDEO ===
Canal de origem: {canal}
TÃ­tulo do episÃ³dio original: {titulo_orig}
URL original: {url_orig}
Temas identificados: {temas_str if temas_str else "N/A"}
TranscriÃ§Ã£o do trecho:
{transcricao}

=== INSTRUÃ‡Ã•ES PARA TÃTULO ===
- MÃ¡ximo 90 caracteres (sem contar #Shorts)
- Crie um GANCHO FORTE: use pergunta provocativa, dado surpreendente, afirmaÃ§Ã£o polÃªmica ou frase de impacto
- Extraia a frase mais marcante ou surpreendente da transcriÃ§Ã£o
- NÃƒO mencione o nome do canal no tÃ­tulo
- Termine com " #Shorts" (com espaÃ§o)
- Exemplos de ganchos bons: "VocÃª estÃ¡ desperdiÃ§ando seu talento e nem sabe #Shorts", "Por que 90% das pessoas nÃ£o ficam ricas #Shorts"

=== INSTRUÃ‡Ã•ES PARA DESCRIÃ‡ÃƒO ===
- 3 parÃ¡grafos com emojis
- ParÃ¡grafo 1: Resumo do momento mais impactante (2-3 frases, linguagem direta)
- ParÃ¡grafo 2: CrÃ©ditos + link para o vÃ­deo completo
- ParÃ¡grafo 3: CTA + 5-8 hashtags temÃ¡ticas relevantes
- MÃ¡ximo 800 caracteres total

=== INSTRUÃ‡Ã•ES PARA TAGS ===
- 15 a 20 tags variadas
- Inclua: tags do tema principal, variaÃ§Ãµes do nome do canal, termos de busca que o pÃºblico usaria
- Misture portuguÃªs e inglÃªs quando fizer sentido
- Inclua "shorts", "podcast brasileiro", "cortes de podcast"
- Tags especÃ­ficas sobre o assunto discutido (nÃ£o genÃ©ricas!)
- MÃ¡ximo 500 caracteres somando todas as tags

Retorne APENAS um JSON vÃ¡lido neste formato exato:
{{
  "titulo": "TÃ­tulo com gancho forte aqui #Shorts",
  "descricao": "ParÃ¡grafo 1 aqui...\\n\\nParÃ¡grafo 2 com crÃ©ditos...\\n\\nParÃ¡grafo 3 CTA e hashtags...",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10", "tag11", "tag12", "tag13", "tag14", "tag15"]
}}

Retorne apenas o JSON, sem explicaÃ§Ãµes adicionais."""

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
                print(f"  ðŸ¤– SEO gerado pela IA:")
                print(f"     TÃ­tulo   : {titulo}")
                print(f"     Tags     : {len(tags)} tags geradas")
                print(f"     DescriÃ§Ã£o: {len(descricao)} chars")
                return {"titulo": titulo, "descricao": descricao, "tags": tags}

    except Exception as e:
        print(f"  âš ï¸  Groq AI falhou ao gerar SEO: {e}")

    return {}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# SEO Fallback â€” usado quando a IA nÃ£o estÃ¡ disponÃ­vel
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _montar_titulo_fallback(titulo_original: str, canal_origem: str) -> str:
    """Monta o tÃ­tulo do Short com gancho bÃ¡sico."""
    titulo_limpo = titulo_original.replace(canal_origem, "").strip(" |-â€”")
    limite = 85
    if len(titulo_limpo) > limite:
        titulo_limpo = titulo_limpo[:limite].rsplit(" ", 1)[0] + "..."
    return f"{titulo_limpo} #Shorts"


def _montar_descricao_fallback(dados: dict) -> str:
    """Monta a descriÃ§Ã£o do Short com crÃ©ditos ao canal original."""
    canal   = dados.get("canal", "Podcast")
    titulo  = dados.get("titulo_video", dados.get("titulo", ""))
    url     = dados.get("url", "")
    texto   = dados.get("texto_transcricao", "")[:300]

    canal_sem_espaco = canal.replace(' ', '')

    return f"""ðŸŽ™ï¸ Um dos momentos mais impactantes do {canal}!

ðŸ“º Assista o episÃ³dio completo: {titulo}
ðŸ”— {url}

ðŸ“Œ Siga para mais cortes dos melhores momentos dos podcasts brasileiros!

#{canal_sem_espaco} #Podcast #PodcastBrasileiro #Cortes #CortesdePodcast #Shorts #Brasil #Viral"""


def _montar_tags_fallback(dados: dict) -> list:
    """Gera tags bÃ¡sicas otimizadas para o Short."""
    canal = dados.get("canal", "podcast")
    canal_sem_espaco = canal.lower().replace(" ", "")

    tags_base = [
        "shorts", "podcast", "cortes de podcast", "podcast brasileiro",
        "melhores momentos", "viral", "brasil", "motivaÃ§Ã£o",
        canal, canal_sem_espaco,
        f"cortes {canal.lower()}", f"{canal.lower()} podcast",
        "short", "reels", "entretenimento",
    ]

    # Adiciona temas extraÃ­dos pela IA se disponÃ­veis
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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Playlist â€” adiciona o Short Ã  playlist do canal de origem
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _obter_playlist_id_do_canal(canal_nome: str) -> str | None:
    """
    Busca o playlist_id do canal de origem no canais.json.
    Retorna None se nÃ£o encontrar ou se nÃ£o estiver configurado.
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
                    print(f"  âš ï¸  Canal '{canal_nome}' sem playlist_id configurado.")
                    print(f"       Crie uma playlist no YouTube Studio e adicione o ID em data/canais.json")
                    return None

        print(f"  âš ï¸  Canal '{canal_nome}' nÃ£o encontrado em canais.json")
        return None

    except Exception as e:
        print(f"  âš ï¸  Erro ao ler canais.json: {e}")
        return None


def _adicionar_a_playlist(youtube, video_id: str, canal_nome: str):
    """
    Adiciona o Short publicado Ã  playlist do canal de origem.
    Falha silenciosamente para nÃ£o bloquear o pipeline.
    """
    playlist_id = _obter_playlist_id_do_canal(canal_nome)
    if not playlist_id:
        return

    print(f"\n  ðŸ“‹ Adicionando Short Ã  playlist do canal '{canal_nome}'...")
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
        print(f"  âœ… Short adicionado Ã  playlist com sucesso!")

    except Exception as e:
        print(f"  âš ï¸  Falha ao adicionar Ã  playlist: {e}")
        print(f"       O vÃ­deo foi publicado normalmente. Verifique as permissÃµes do OAuth.")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# FunÃ§Ã£o principal de upload
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def upload_youtube(video_path: str, dados: dict) -> str:
    """
    Faz upload do Short para o YouTube com SEO otimizado por IA.

    Args:
        video_path : caminho do arquivo MP4 final
        dados      : dict com metadados (titulo_video, canal, url, texto_transcricao, temas, etc.)

    Returns:
        ID do vÃ­deo criado no YouTube.
    """
    creds   = _obter_credenciais()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    canal = dados.get("canal", "Podcast")

    # â”€â”€ Gera SEO com IA â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print(f"\n  ðŸ¤– Gerando SEO otimizado com Groq AI...")
    seo_ia = _gerar_seo_com_ia(dados)

    if seo_ia:
        titulo    = seo_ia["titulo"][:100]
        descricao = seo_ia["descricao"][:5000]
        tags_raw  = seo_ia["tags"]
    else:
        print(f"  ðŸ“ Usando SEO fallback...")
        titulo    = _montar_titulo_fallback(
            dados.get("titulo_video", dados.get("titulo", "Momento IncrÃ­vel")),
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

    # â”€â”€ Renomeia o arquivo com o tÃ­tulo â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if os.path.exists(video_path):
        diretorio = os.path.dirname(video_path)
        novo_nome = _sanitizar_nome_arquivo(titulo)
        novo_path = os.path.join(diretorio, novo_nome)
        if video_path != novo_path:
            if os.path.exists(novo_path):
                os.remove(novo_path)
            os.rename(video_path, novo_path)
            video_path = novo_path
            print(f"  ðŸ“ Arquivo renomeado: {novo_nome}")

    # â”€â”€ Body da requisiÃ§Ã£o â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Upload â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print(f"\n  ðŸ“¤ Iniciando upload do Short para o YouTube...")
    print(f"     TÃ­tulo    : {titulo}")
    print(f"     Tags      : {len(tags_validas)} tags ({total_chars} chars)")
    print(f"     DescriÃ§Ã£o : {len(descricao)} chars")
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
    print(f"\n  âœ… Short publicado! ID: {video_id}")
    print(f"     ðŸ“± https://www.youtube.com/shorts/{video_id}")
    print(f"     ðŸ“º https://www.youtube.com/watch?v={video_id}")

    # â”€â”€ Adiciona Ã  playlist do canal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _adicionar_a_playlist(youtube, video_id, canal)

    return video_id


if __name__ == "__main__":
    dados_teste = {
        "titulo_video": "O segredo que ninguÃ©m te conta sobre dinheiro e liberdade financeira",
        "canal": "Podpah",
        "url": "https://www.youtube.com/watch?v=example",
        "texto_transcricao": "A maioria das pessoas trabalha a vida toda e nunca consegue sair do ciclo...",
    }
    upload_youtube("output/short_final.mp4", dados_teste)

