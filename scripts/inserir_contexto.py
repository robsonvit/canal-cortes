"""
inserir_contexto.py
───────────────────
Passo 6 do Pipeline Canal Cortes.

Enriquece o Short com:
  1. Inserções visuais 1:1 (imagens contextuais de alta qualidade)
     sobrepostas no centro do vídeo por ~2.5 segundos
  2. Cascata de 4 estratégias de busca de imagens:
     - Estratégia 0: Pinterest (pinscrape) → CDN pinimg.com HD (MELHOR CURADORIA)
     - Estratégia 1: DuckDuckGo (via ddgs) → CDN do Bing em &w=800 (HD)
     - Estratégia 2: API Wikipedia PT (fallback) → pithumbsize=1000
     - Estratégia 3: Pexels API (fallback final)
     - Abortagem de segurança se nenhuma imagem for encontrada

Fluxo:
  a. Envia o SRT para Groq AI → extrai 2-3 temas visuais com termos HIPER-ESPECÍFICOS
  b. Busca imagens no Pinterest via pinscrape (Estratégia 0) — melhor curadoria editorial
  c. Fallback DuckDuckGo → Bing CDN HD se Pinterest falhar (Estratégia 1)
  d. Fallback Wikipedia PT se DDG falhar (Estratégia 2)
  e. Fallback Pexels API se tudo falhar (Estratégia 3)
  f. Aborta overlay se nenhuma estratégia encontrar imagem (evita vídeos quebrados)
  g. Cria um plano de timing (quando mostrar cada inserção)
  h. Aplica os overlays via FFmpeg filter_complex (crop automático 1:1)
"""

import os
import json
import re
import random
import subprocess
import requests
import time
import urllib.parse

from openai import OpenAI

ROOT_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR    = os.path.join(ROOT_DIR, "output")

# Tamanho do overlay 1:1 (quadrado) em pixels na tela 9:16
OVERLAY_SIZE  = 800   # Aumentado para 800px para ficar em destaque no centro
OVERLAY_DUR   = 2.45  # Duração de cada inserção em segundos (reduzido em 30%)
# Posição do overlay: centro exato do vídeo
OVERLAY_X     = f"{(1080 - OVERLAY_SIZE) // 2}"
OVERLAY_Y     = f"{(1920 - OVERLAY_SIZE) // 2}"

# User-Agent realista para evitar bloqueios
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


# ─────────────────────────────────────────────────────────────────────────────
# Análise de temas via Groq AI — prompt hiper-específico
# ─────────────────────────────────────────────────────────────────────────────
def _extrair_temas(texto: str, output_dir: str = OUTPUT_DIR) -> list:
    """
    Envia o conteúdo do SRT (ou a transcrição) para Groq AI e extrai temas visuais chave.
    Retorna lista de dicts: [{tema_pt, termo_busca_a, sujeito_wikipedia, segundo}]

    O campo 'termo_busca_a' é projetado para achar a foto EXATA no Bing Imagens.
    O campo 'sujeito_wikipedia' é o termo limpo, apenas a entidade/sujeito (ex: 'Michael Phelps', 'Watergate').
    """
    srt_path = os.path.join(output_dir, "legendas.srt")
    try:
        with open(srt_path, "r", encoding="utf-8") as f:
            texto_para_ia = f.read()[:2500]  # Passa o SRT com os timestamps para a IA
    except Exception:
        texto_para_ia = texto[:800]

    cliente = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ.get("OPENROUTER_API_KEY"))

    prompt = f"""Analise esta transcrição de um podcast em português brasileiro e extraia 3 momentos visuais marcantes.

Para cada momento, retorne:
- "tema_pt": o tema em português (ex: "Zidane")
- "termo_busca_a": TERMO MUITO ESPECÍFICO para achar a foto EXATA no Bing Imagens.
  REGRAS OBRIGATÓRIAS para termo_busca_a:
  * Inclua nome completo de pessoas famosas + contexto (ex: "Zinedine Zidane rosto HD", "Neymar Jr Barcelona camisa 11")
  * Para eventos: inclua ano e nome completo (ex: "Copa do Mundo 2006 final Berlim", "Libertadores 2023 troféu")
  * Para objetos/lugares: seja ultra-específico (ex: "Ferrari F40 vermelha lateral", "Cristo Redentor Rio de Janeiro aéreo")
  * NUNCA use termos genéricos como "futebol", "dinheiro", "sucesso" — seja SEMPRE específico
  * Prefira nomes próprios, marcas, anos, locais ou modelos exatos
- "sujeito_wikipedia": APENAS o nome limpo da entidade principal/sujeito para busca na Wikipedia (ex: "Zinedine Zidane", "Taça Libertadores da América", "Pelé", "Ferrari F40")
- "segundo": o segundo aproximado em que esse tema aparece na transcrição

Retorne APENAS um JSON válido neste formato exato:
[
  {{"tema_pt": "Zidane cabeçada final 2006", "termo_busca_a": "Zinedine Zidane headbutt Materazzi 2006 World Cup final", "sujeito_wikipedia": "Zinedine Zidane", "segundo": 5}},
  {{"tema_pt": "Taça Libertadores da América", "termo_busca_a": "Taça Libertadores da América troféu HD dourado", "sujeito_wikipedia": "Copa Libertadores da América", "segundo": 20}},
  {{"tema_pt": "Pelé Santos FC", "termo_busca_a": "Pelé Santos FC camisa 10 foto histórica HD", "sujeito_wikipedia": "Pelé", "segundo": 40}}
]

Transcrição com tempos (SRT):
{texto_para_ia}

Retorne apenas o JSON, sem explicações."""

    try:
        resp = cliente.chat.completions.create(
            model="google/gemini-2.0-flash-exp:free",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=400,
        )
        conteudo = resp.choices[0].message.content.strip()

        # Extrai o JSON da resposta
        match = re.search(r"\[.*?\]", conteudo, re.DOTALL)
        if match:
            temas = json.loads(match.group())
            print(f"  🧠 Temas extraídos pela IA: {[t['tema_pt'] for t in temas]}")
            print(f"  🔍 Termos de busca (Bing): {[t.get('termo_busca_a', '?') for t in temas]}")
            print(f"  📖 Entidades Wikipedia: {[t.get('sujeito_wikipedia', '?') for t in temas]}")
            return temas
    except Exception as e:
        print(f"  ⚠️  Erro ao extrair temas: {e}")

    # Fallback mínimo
    return [
        {"tema_pt": "podcast conversa", "termo_busca_a": "podcast microphone studio HD professional", "sujeito_wikipedia": "Microfone", "segundo": 5},
        {"tema_pt": "sucesso profissional", "termo_busca_a": "businessman success achievement trophy winner", "sujeito_wikipedia": "Troféu", "segundo": 25},
    ]


# ─────────────────────────────────────────────────────────────────────────────
# ESTRATÉGIA 0: Pinterest via pinscrape → CDN pinimg.com em alta resolução
# ─────────────────────────────────────────────────────────────────────────────
def _buscar_imagem_pinterest(termo: str) -> str | None:
    """
    Busca imagem no Pinterest usando a biblioteca pinscrape.
    Retorna a URL de melhor resolução encontrada no CDN pinimg.com,
    ou None se falhar (sem travar o pipeline).

    O Pinterest tem curadoria editorial muito superior para celebridades,
    eventos esportivos e cultura pop — temas típicos dos podcasts de corte.
    """
    try:
        from pinscrape import Pinterest  # type: ignore
    except ImportError:
        print("  ⚠️  [Pinterest] pinscrape não instalado. Pulando Estratégia 0.")
        print("      Instale com: pip install pinscrape")
        return None

    print(f"  📌 [Pinterest] Buscando: '{termo}'")
    try:
        # Instancia com ou sem sleep_time dependendo da versão da lib
        try:
            p = Pinterest(proxies={}, sleep_time=1)
        except TypeError:
            p = Pinterest(proxies={})

        # API REAL do pinscrape: search(query, page_size=26)
        urls = p.search(termo, page_size=26)

        if not urls:
            print(f"  ⚠️  [Pinterest] Nenhuma imagem encontrada para '{termo}'")
            return None

        # Prefere imagens do CDN oficial do Pinterest (pinimg.com)
        # e filtra para originals/ (maior resolução)
        urls_lista = list(urls) if not isinstance(urls, list) else urls

        # Prioridade 1: originals do pinimg.com (resolução máxima)
        urls_orig = [
            u for u in urls_lista
            if isinstance(u, str) and "pinimg.com" in u and "/originals/" in u
        ]
        # Prioridade 2: qualquer URL do pinimg.com
        urls_pinimg = [
            u for u in urls_lista
            if isinstance(u, str) and "pinimg.com" in u and u not in urls_orig
        ]
        # Prioridade 3: qualquer URL válida retornada
        urls_outras = [
            u for u in urls_lista
            if isinstance(u, str) and u not in urls_orig and u not in urls_pinimg
        ]

        candidatas = urls_orig[:5] + urls_pinimg[:5] + urls_outras[:5]

        for url in candidatas:
            if _testar_url(url):
                print(f"  ✅ [Pinterest] Imagem encontrada: {url[:80]}...")
                return url

        print(f"  ⚠️  [Pinterest] Nenhuma URL válida para '{termo}'")
        return None

    except Exception as e:
        print(f"  ⚠️  [Pinterest] Erro na busca: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# ESTRATÉGIA 1: DuckDuckGo Images → Bing CDN em alta resolução (&w=800)
# ─────────────────────────────────────────────────────────────────────────────
def _buscar_imagem_ddgs(termo: str) -> str | None:
    """
    Busca imagem via DuckDuckGo Images (biblioteca duckduckgo-search).
    Se encontrar imagem hospedada no CDN do Bing, manipula a URL para
    forçar download em alta resolução com &w=800.

    Retorna URL da imagem ou None se falhar.
    """
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        print("  ⚠️  [DDG] duckduckgo-search não instalado. Pulando Estratégia 1.")
        return None

    print(f"  🦆 [DDG] Buscando: '{termo}'")
    try:
        with DDGS() as ddgs:
            resultados = list(ddgs.images(
                keywords=termo,
                region="br-pt",
                safesearch="off",
                size=None,
                type_image=None,
                layout=None,
                license_image=None,
                max_results=10,
            ))

        if not resultados:
            print(f"  ⚠️  [DDG] Nenhum resultado para '{termo}'")
            return None

        # Prioriza imagens do CDN do Bing (th.bing.com ou tse1.mm.bing.net)
        # pois permitem manipulação de resolução via parâmetros de URL
        urls_bing = [
            r["image"] for r in resultados
            if r.get("image") and (
                "th.bing.com" in r["image"] or
                "tse1.mm.bing.net" in r["image"] or
                "tse2.mm.bing.net" in r["image"] or
                "bing.net" in r["image"]
            )
        ]

        urls_outras = [
            r["image"] for r in resultados
            if r.get("image") and r["image"] not in urls_bing
        ]

        # Tenta Bing CDN primeiro (permite forçar alta resolução)
        for url_original in urls_bing[:5]:
            url_hd = _forcar_resolucao_bing(url_original, largura=800)
            if _testar_url(url_hd):
                print(f"  ✅ [DDG→Bing] Imagem HD encontrada: {url_hd[:80]}...")
                return url_hd

        # Tenta outras URLs
        for url in urls_outras[:5]:
            if _testar_url(url):
                print(f"  ✅ [DDG→Outra] Imagem encontrada: {url[:80]}...")
                return url

        print(f"  ⚠️  [DDG] Nenhuma URL válida para '{termo}'")
        return None

    except Exception as e:
        print(f"  ⚠️  [DDG] Erro na busca: {e}")
        return None


def _forcar_resolucao_bing(url: str, largura: int = 800) -> str:
    """
    Manipula URL do CDN do Bing para forçar download em alta resolução.
    Adiciona/substitui os parâmetros w= e h= pela largura desejada.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

        # Remove parâmetros de tamanho existentes e substitui
        params.pop("w", None)
        params.pop("h", None)
        params.pop("rs", None)  # Remove resize/quality params antigos
        params["w"] = [str(largura)]

        nova_query = urllib.parse.urlencode(params, doseq=True)
        url_hd = parsed._replace(query=nova_query).geturl()
        return url_hd
    except Exception:
        return url  # Retorna URL original se a manipulação falhar


def _testar_url(url: str, timeout: int = 8) -> bool:
    """Testa se a URL retorna uma imagem válida (HEAD request)."""
    try:
        resp = requests.head(
            url,
            timeout=timeout,
            headers={"User-Agent": _UA},
            allow_redirects=True,
        )
        content_type = resp.headers.get("content-type", "")
        return (
            resp.status_code == 200 and
            ("image" in content_type or content_type == "")
        )
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# ESTRATÉGIA 2: API Oficial da Wikipedia PT (Fallback)
# ─────────────────────────────────────────────────────────────────────────────
# ESTRATÉGIA 2: API Oficial da Wikipedia PT (Fallback)
# ─────────────────────────────────────────────────────────────────────────────
def _buscar_imagem_wikipedia(termo: str, sujeito: str = "") -> str | None:
    """
    Consulta a API oficial da Wikipédia em português para o sujeito ou termo dado.
    Retorna a URL da imagem principal da página em alta qualidade (pithumbsize=1000).
    """
    # Se o Groq identificou uma entidade limpa para wikipedia, prioriza ela
    termo_busca = sujeito.strip() if sujeito else _limpar_termo_para_wiki(termo)
    if not termo_busca:
        return None

    print(f"  📖 [Wiki] Buscando artigo para: '{termo_busca}'")
    
    # User-Agent específico exigido pela política da Wikipedia para evitar erro 429
    wiki_ua = "CanalCortesBot/1.0 (robsonvit@github.com)"

    try:
        # Passo 1: Busca o artigo mais relevante na Wikipedia PT
        url_search = "https://pt.wikipedia.org/w/api.php"
        params_search = {
            "action": "query",
            "list": "search",
            "srsearch": termo_busca,
            "srlimit": 3,
            "format": "json",
            "utf8": 1,
        }
        resp_search = requests.get(
            url_search,
            params=params_search,
            timeout=10,
            headers={"User-Agent": wiki_ua},
        )
        resp_search.raise_for_status()
        resultados = resp_search.json().get("query", {}).get("search", [])

        if not resultados:
            print(f"  ⚠️  [Wiki] Sem artigos para '{termo_busca}'")
            return None

        # Passo 2: Para cada artigo encontrado, busca a imagem principal
        for artigo in resultados[:3]:
            titulo_pagina = artigo["title"]
            print(f"  📖 [Wiki] Artigo encontrado: '{titulo_pagina}'")

            params_img = {
                "action": "query",
                "titles": titulo_pagina,
                "prop": "pageimages",
                "pithumbsize": 1000,      # Alta qualidade
                "piprop": "thumbnail",
                "format": "json",
                "utf8": 1,
            }
            resp_img = requests.get(
                url_search,
                params=params_img,
                timeout=10,
                headers={"User-Agent": wiki_ua},
            )
            resp_img.raise_for_status()

            pages = resp_img.json().get("query", {}).get("pages", {})
            for page_data in pages.values():
                thumbnail = page_data.get("thumbnail", {})
                url_img = thumbnail.get("source", "")
                if url_img and _testar_url(url_img, headers={"User-Agent": wiki_ua}):
                    print(f"  ✅ [Wiki] Imagem encontrada: {url_img[:80]}...")
                    return url_img

        print(f"  ⚠️  [Wiki] Nenhuma imagem com thumbnail nos artigos para '{termo_busca}'")
        return None

    except Exception as e:
        print(f"  ⚠️  [Wiki] Erro na API: {e}")
        return None


def _limpar_termo_para_wiki(termo: str) -> str:
    """
    Remove palavras de ruído para melhorar a busca na Wikipédia.
    """
    palavras_ruido = [
        "hd", "hd foto", "foto", "rosto", "imagem", "picture", "image",
        "high resolution", "alta resolução", "alta qualidade", "professional",
        "studio", "winner", "trophy", "achievement", "logotipo oficial", "logo"
    ]
    termo_lower = termo.lower()
    for ruido in palavras_ruido:
        termo_lower = termo_lower.replace(ruido, "")
    return " ".join(termo_lower.split()).strip() or termo


# ─────────────────────────────────────────────────────────────────────────────
# ESTRATÉGIA 3: API do Pexels (Fallback do Fallback)
# ─────────────────────────────────────────────────────────────────────────────
def _buscar_imagem_pexels(termo: str) -> str | None:
    """
    Busca uma imagem no Pexels para o termo como fallback final de segurança.
    """
    pexels_key = os.environ.get("PEXELS_API_KEY", "")
    if not pexels_key:
        return None

    # Limpa um pouco do ruído de 'HD' ou 'logotipo' do termo para o Pexels
    termo_pexels = _limpar_termo_para_wiki(termo)
    print(f"  📷 [Pexels] Buscando: '{termo_pexels}'")
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": pexels_key},
            params={"query": termo_pexels, "per_page": 5, "size": "medium"},
            timeout=15,
        )
        resp.raise_for_status()
        fotos = resp.json().get("photos", [])
        if fotos:
            foto = random.choice(fotos)
            url_img = foto["src"].get("medium") or foto["src"]["original"]
            print(f"  ✅ [Pexels] Imagem encontrada: {url_img[:80]}...")
            return url_img
    except Exception as e:
        print(f"  ⚠️  [Pexels] Falha na API: {e}")
    return None


def _testar_url(url: str, timeout: int = 8, headers: dict = None) -> bool:
    """Testa se a URL retorna status válido."""
    if headers is None:
        headers = {"User-Agent": _UA}
    try:
        resp = requests.head(
            url,
            timeout=timeout,
            headers=headers,
            allow_redirects=True,
        )
        return resp.status_code in [200, 301, 302]
    except Exception:
        # Se falhar no HEAD por bloqueio de método, tentamos GET rápido
        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers=headers,
                stream=True,
            )
            return resp.status_code in [200, 301, 302]
        except Exception:
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Motor de busca principal: executa as estratégias em cascata
# ─────────────────────────────────────────────────────────────────────────────
def _buscar_melhor_imagem(termo: str, tema_pt: str, sujeito_wiki: str = "") -> str | None:
    """
    Executa as estratégias de busca em ordem de qualidade:
      0. Pinterest (pinscrape) → CDN pinimg.com HD [MELHOR CURADORIA EDITORIAL]
      1. DuckDuckGo → Bing CDN HD (&w=800)
      2. Wikipedia PT API (pithumbsize=1000)
      3. Pexels API (Fallback Final)

    Se NENHUMA estratégia encontrar imagem, retorna None.
    """
    print(f"\n  🔎 Buscando imagem para: '{tema_pt}'")
    print(f"     Termo Pinterest/Bing: '{termo}'")
    if sujeito_wiki:
        print(f"     Sujeito Wikipédia: '{sujeito_wiki}'")

    # ── Estratégia 0: Pinterest (melhor curadoria para cultura pop/esportes) ──
    url = _buscar_imagem_pinterest(termo)
    if url:
        return url

    # ── Estratégia 1: DuckDuckGo / Bing CDN ──────────────────────────────────
    print(f"  🔄 [Pinterest] Falhou. Tentando DuckDuckGo/Bing...")
    url = _buscar_imagem_ddgs(termo)
    if url:
        return url

    # ── Estratégia 2: Wikipedia PT ───────────────────────────────────────────
    print(f"  🔄 [DDG] Falhou ou deu Block. Tentando Wikipedia PT...")
    url = _buscar_imagem_wikipedia(termo, sujeito_wiki)
    if url:
        return url

    # ── Estratégia 3: Pexels API (Fallback Final) ────────────────────────────
    print(f"  🔄 [Wiki] Falhou. Tentando Pexels API...")
    url = _buscar_imagem_pexels(termo)
    if url:
        return url

    # ── Abortagem de Segurança ───────────────────────────────────────────────
    print(f"  ❌ [ABORT] Nenhuma estratégia encontrou imagem para '{tema_pt}'.")
    print(f"     Overlay ignorado (evitando vídeo com imagem quebrada).")
    return None


def _baixar_imagem(url: str, destino: str) -> bool:
    """Baixa imagem para disco. Retorna True se sucesso."""
    # Define User-Agent baseado no domínio para evitar erro 429
    ua = _UA
    if "wikipedia.org" in url or "wikimedia.org" in url:
        ua = "CanalCortesBot/1.0 (robsonvit@github.com)"
        
    try:
        resp = requests.get(
            url,
            timeout=25,
            headers={"User-Agent": ua},
            allow_redirects=True,
        )
        resp.raise_for_status()

        # Verifica se é realmente uma imagem ou se o conteúdo tem tamanho
        if len(resp.content) > 1000:
            with open(destino, "wb") as f:
                f.write(resp.content)
            tamanho_kb = len(resp.content) / 1024
            print(f"     📥 Imagem baixada com sucesso: {tamanho_kb:.0f} KB")
            return True
        else:
            print(f"  ⚠️  Conteúdo baixado é muito pequeno ou vazio")
            return False
    except Exception as e:
        print(f"  ⚠️  Falha ao baixar imagem: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Criação do overlay 1:1 com FFmpeg
# ─────────────────────────────────────────────────────────────────────────────
def _criar_overlay_quadrado(img_path: str, output_path: str, duracao: float):
    """
    Redimensiona a imagem para quadrado (1:1) com bordas arredondadas
    e a converte em clipe de vídeo de 'duracao' segundos.
    """
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", img_path,
        "-t", str(duracao),
        "-vf", (
            f"scale={OVERLAY_SIZE}:{OVERLAY_SIZE}:force_original_aspect_ratio=increase,"
            f"crop={OVERLAY_SIZE}:{OVERLAY_SIZE},"
            "format=yuva420p"
        ),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    resultado = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return resultado.returncode == 0


# ─────────────────────────────────────────────────────────────────────────────
# Função principal
# ─────────────────────────────────────────────────────────────────────────────
def inserir_contexto(
    video_base: str,
    texto_transcricao: str,
    output_dir: str = OUTPUT_DIR,
) -> str:
    """
    Adiciona inserções 1:1 contextuais ao Short (mantém o áudio intacto).

    Cascata de busca de imagens:
      0. Pinterest (pinscrape) → CDN pinimg.com HD [curadoria editorial superior]
      1. DuckDuckGo → Bing CDN HD (&w=800)
      2. Wikipedia PT API (pithumbsize=1000)
      3. Pexels API (fallback final)
      Aborta overlay se nenhuma estratégia funcionar (sem placeholders/imagens quebradas).

    Args:
        video_base          : caminho do short_base.mp4 (9:16 com legendas e música)
        texto_transcricao   : texto completo da transcrição
        output_dir          : pasta de saída

    Returns:
        Caminho do vídeo final (output/short_final.mp4)
    """
    os.makedirs(output_dir, exist_ok=True)
    clips_dir  = os.path.join(output_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)
    output_final = os.path.join(output_dir, "short_final.mp4")

    # ── 1. Extrai temas via IA ────────────────────────────────────────────────
    print("  🧠 Analisando transcrição com Groq AI para extrair temas visuais...")
    temas = _extrair_temas(texto_transcricao, output_dir)

    # ── 2. Busca imagens com estratégia dupla ────────────────────────────────
    overlays_prontos = []   # [(segundo_inicio, clip_path)]

    for i, tema in enumerate(temas):
        termo        = tema.get("termo_busca_a", tema.get("busca_en", "podcast microphone"))
        sujeito_wiki = tema.get("sujeito_wikipedia", "")
        segundo      = float(tema.get("segundo", i * 15 + 5))
        tema_pt      = tema.get("tema_pt", "")

        print(f"\n  🖼️  [{i+1}/{len(temas)}] Tema: '{tema_pt}'")

        # Busca imagem com cascata DDG → Wikipedia → Pexels
        url_img = _buscar_melhor_imagem(termo, tema_pt, sujeito_wiki)

        if not url_img:
            # Abortagem de segurança: pula este overlay
            print(f"     ⏭️  Overlay ignorado para '{tema_pt}' (sem imagem válida)")
            continue

        img_path  = os.path.join(clips_dir, f"overlay_img_{i}.jpg")
        clip_path = os.path.join(clips_dir, f"overlay_clip_{i}.mp4")

        if not _baixar_imagem(url_img, img_path):
            print(f"     ⏭️  Download falhou — overlay ignorado para '{tema_pt}'")
            continue

        # Pequena pausa anti-rate-limit entre overlays
        time.sleep(0.5)

        if _criar_overlay_quadrado(img_path, clip_path, OVERLAY_DUR):
            overlays_prontos.append((segundo, clip_path))
            print(f"     ✅ Overlay pronto para ~{segundo:.0f}s")
        else:
            print(f"     ⚠️  Falha ao criar overlay para '{tema_pt}'")

    # ── 3. Monta vídeo final com FFmpeg ──────────────────────────────────────
    print(f"\n  🎬 Montando vídeo final com {len(overlays_prontos)} overlays...")

    import shutil
    if not overlays_prontos:
        print("  📻 Sem overlays disponíveis. Copiando vídeo intacto...")
        shutil.copy(video_base, output_final)
    else:
        # Com overlays:
        # Input 0 é o video_base, Inputs 1..N são os overlays
        inputs = ["-i", video_base]
        for _, clip_path in overlays_prontos:
            inputs += ["-i", clip_path]

        # Encadeia overlays: [prev_v][N:v]overlay=...[next_v]
        filters = []
        prev_label = "[0:v]"
        for idx, (segundo, _) in enumerate(overlays_prontos):
            next_label = "[vfinal]" if idx == len(overlays_prontos) - 1 else f"[v{idx}]"
            filters.append(
                f"{prev_label}[{idx + 1}:v]overlay="
                f"x={OVERLAY_X}:y={OVERLAY_Y}:"
                f"enable='between(t,{segundo},{segundo + OVERLAY_DUR})'"
                f"{next_label}"
            )
            prev_label = next_label

        filter_str = ";".join(filters)

        cmd = [
            "ffmpeg", "-y",
        ] + inputs + [
            "-filter_complex", filter_str,
            "-map", "[vfinal]",
            "-map", "0:a?",          # "?" ignora graciosamente se não houver stream de áudio
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",           # Recodifica áudio para garantir compatibilidade
            "-b:a", "192k",
            "-shortest",             # Limita duração ao stream mais curto (evita áudio cortado)
            "-movflags", "+faststart",
            output_final,
        ]

        resultado = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
        if resultado.returncode != 0:
            print(f"  ⚠️  FFmpeg com overlays falhou (returncode={resultado.returncode}). Copiando vídeo original...")
            print(f"  stderr: {resultado.stderr[-500:]}")
            shutil.copy(video_base, output_final)
        else:
            print(f"  ✅ FFmpeg concluiu com {len(overlays_prontos)} overlay(s) aplicados com sucesso.")

    tamanho_mb = os.path.getsize(output_final) / (1024 * 1024)
    print(f"  ✅ Vídeo final com contexto: {output_final} ({tamanho_mb:.1f} MB)")
    return output_final


if __name__ == "__main__":
    import sys
    video   = sys.argv[1] if len(sys.argv) > 1 else "output/short_base.mp4"
    texto   = sys.argv[2] if len(sys.argv) > 2 else "Teste de contexto visual com IA"
    inserir_contexto(video, texto)
