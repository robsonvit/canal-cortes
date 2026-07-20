"""
baixar_musica.py
────────────────
Baixa música de fundo de atenção/energia para os Shorts.

Usa músicas livres de direitos autorais (royalty-free) de
repositórios públicos. Faz cache local para evitar downloads repetidos.
"""

import os
import random
import subprocess
from groq import Groq

ROOT_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSICA_DIR  = os.path.join(ROOT_DIR, "assets", "musicas")

# Biblioteca de músicas royalty-free por sentimento (YouTube NCS/Lofi)
BIBLIOTECA_MUSICAS = {
    "superacao": [
        "https://www.youtube.com/watch?v=pLcw3dK1yU0", # Epic
        "https://www.youtube.com/watch?v=xH3yN226z3Y",
    ],
    "licao": [
        "https://www.youtube.com/watch?v=n61ULEU7CO0", # Lofi
        "https://www.youtube.com/watch?v=5qap5aO4i9A",
    ],
    "misterio": [
        "https://www.youtube.com/watch?v=680D9R9wOms", # Suspense
        "https://www.youtube.com/watch?v=8q-ZAeYF3sU",
    ],
    "padrao": [
        "https://www.youtube.com/watch?v=pLcw3dK1yU0",
    ]
}

def _detectar_sentimento(texto: str) -> str:
    """Usa Groq AI para classificar o sentimento predominante do vídeo."""
    if not texto:
        return "padrao"
        
    cliente = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    prompt = f"""Leia o texto abaixo e classifique o SENTIMENTO PREDOMINANTE em APENAS UMA dessas 3 categorias:
1. "superacao" (Motivação, sucesso, energia alta, conquista)
2. "licao" (Reflexão, ensinamento, calmo, conselho, filosofia)
3. "misterio" (Tensão, suspense, polêmica, revelação chocante)

Retorne APENAS a palavra da categoria (sem aspas, tudo minúsculo).
Texto: {texto[:1000]}"""

    try:
        resp = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=20,
        )
        sentimento = resp.choices[0].message.content.strip().lower()
        for c in ["superacao", "licao", "misterio"]:
            if c in sentimento:
                return c
    except Exception as e:
        print(f"  ⚠️  Erro ao classificar sentimento: {e}")
        
    return "padrao"


def baixar_musica(texto_transcricao: str = "") -> str:
    """
    Baixa música baseada no sentimento da transcrição usando yt-dlp.
    """
    os.makedirs(MUSICA_DIR, exist_ok=True)
    
    sentimento = _detectar_sentimento(texto_transcricao)
    print(f"  🧠 Sentimento detectado: {sentimento.upper()}")
    
    musica_path = os.path.join(MUSICA_DIR, f"musica_{sentimento}.mp3")

    if os.path.exists(musica_path):
        tamanho = os.path.getsize(musica_path)
        if tamanho > 50_000:
            print(f"  🎵 Música já em cache: {musica_path}")
            return musica_path
        else:
            os.remove(musica_path) # Remove arquivo corrompido

    print(f"  ⬇️  Baixando música via YouTube para clima de '{sentimento}'...")
    
    urls = BIBLIOTECA_MUSICAS.get(sentimento, BIBLIOTECA_MUSICAS["padrao"])
    url_escolhida = random.choice(urls)
    
    try:
        cmd = [
            "yt-dlp",
            "-x", "--audio-format", "mp3",
            "--audio-quality", "128K",
            "--cookies", os.path.join(ROOT_DIR, "youtube_cookies.txt"), # Usa cookies pra evitar bot block
            "-o", musica_path.replace(".mp3", "") + ".%(ext)s",
            url_escolhida
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if res.returncode == 0 and os.path.exists(musica_path):
            tamanho_kb = os.path.getsize(musica_path) / 1024
            print(f"  ✅ Música baixada: {musica_path} ({tamanho_kb:.0f} KB)")
            return musica_path
        else:
            print(f"  ⚠️  yt-dlp falhou. Erro:\n{res.stderr[-500:]}")
    except Exception as e:
        print(f"  ⚠️  Falha ao executar yt-dlp: {e}")

    # Fallback 1: Download direto de um MP3 público
    print("  ⚠️  Não foi possível baixar música via yt-dlp. Baixando MP3 direto de fallback...")
    fallback_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"
    try:
        import urllib.request
        urllib.request.urlretrieve(fallback_url, musica_path)
        print("  ✅ Fallback MP3 baixado com sucesso.")
        return musica_path
    except Exception as e:
        print(f"  ⚠️  Fallback MP3 falhou: {e}. Usando silêncio absoluto...")
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "120",
            "-b:a", "128k",
            musica_path,
        ], capture_output=True)
        return musica_path


if __name__ == "__main__":
    import sys
    texto = sys.argv[1] if len(sys.argv) > 1 else "História triste sobre fracasso"
    p = baixar_musica(texto)
    print(f"Música: {p}")

