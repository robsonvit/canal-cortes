"""
baixar_musica.py
────────────────
Baixa música de fundo de atenção/energia para os Shorts.

Usa músicas livres de direitos autorais (royalty-free) de
repositórios públicos. Faz cache local para evitar downloads repetidos.
"""

import os
import requests
import json
import re
from groq import Groq

ROOT_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSICA_DIR  = os.path.join(ROOT_DIR, "assets", "musicas")

# Biblioteca de músicas royalty-free por sentimento (Pixabay)
BIBLIOTECA_MUSICAS = {
    "superacao": [
        "https://cdn.pixabay.com/download/audio/2022/10/25/audio_89891a5a45.mp3", # Epic / Inspiring
        "https://cdn.pixabay.com/download/audio/2022/11/06/audio_0313f890f4.mp3",
    ],
    "licao": [
        "https://cdn.pixabay.com/download/audio/2022/08/02/audio_884fe92c21.mp3", # Lo-Fi / Relax
        "https://cdn.pixabay.com/download/audio/2021/11/25/audio_91b32e02f7.mp3",
    ],
    "misterio": [
        "https://cdn.pixabay.com/download/audio/2022/03/15/audio_6506f2dfcb.mp3", # Dark / Suspense
        "https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0a13f69d2.mp3",
    ],
    "padrao": [
        "https://cdn.pixabay.com/download/audio/2022/10/25/audio_89891a5a45.mp3",
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
        # Garante que é uma das categorias
        for c in ["superacao", "licao", "misterio"]:
            if c in sentimento:
                return c
    except Exception as e:
        print(f"  ⚠️  Erro ao classificar sentimento: {e}")
        
    return "padrao"


def baixar_musica(texto_transcricao: str = "") -> str:
    """
    Baixa música baseada no sentimento da transcrição.
    
    Args:
        texto_transcricao: Texto para análise de sentimento.
        
    Returns:
        Caminho do arquivo MP3 da música.
    """
    os.makedirs(MUSICA_DIR, exist_ok=True)
    
    sentimento = _detectar_sentimento(texto_transcricao)
    print(f"  🧠 Sentimento detectado: {sentimento.upper()}")
    
    # Define arquivo baseado no sentimento
    musica_path = os.path.join(MUSICA_DIR, f"musica_{sentimento}.mp3")

    if os.path.exists(musica_path):
        tamanho = os.path.getsize(musica_path)
        if tamanho > 50_000:
            print(f"  🎵 Música já em cache: {musica_path}")
            return musica_path

    print(f"  ⬇️  Baixando música royalty-free para clima de '{sentimento}'...")
    
    import random
    urls = BIBLIOTECA_MUSICAS.get(sentimento, BIBLIOTECA_MUSICAS["padrao"])
    url_escolhida = random.choice(urls)
    
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url_escolhida, timeout=30, stream=True, headers=headers)
        if resp.status_code == 200:
            with open(musica_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            tamanho_kb = os.path.getsize(musica_path) / 1024
            print(f"  ✅ Música baixada: {musica_path} ({tamanho_kb:.0f} KB)")
            return musica_path
    except Exception as e:
        print(f"  ⚠️  Falha ao baixar {url_escolhida}: {e}")

    # Fallback: gera silêncio se não conseguir baixar
    print("  ⚠️  Não foi possível baixar música. Usando silêncio...")
    import subprocess
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
