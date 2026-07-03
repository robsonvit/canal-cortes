"""
baixar_musica.py
────────────────
Baixa música de fundo de atenção/energia para os Shorts.

Usa músicas livres de direitos autorais (royalty-free) de
repositórios públicos. Faz cache local para evitar downloads repetidos.
"""

import os
import requests

ROOT_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSICA_DIR  = os.path.join(ROOT_DIR, "assets", "musicas")
MUSICA_PATH = os.path.join(MUSICA_DIR, "musica_atencao.mp3")

# Músicas royalty-free de energia/atenção para Shorts
# Fonte: pixabay.com (licença royalty-free para uso comercial)
MUSICAS_URLS = [
    # Beats energéticos de atenção — ideais para Shorts de podcast
    "https://cdn.pixabay.com/download/audio/2022/10/25/audio_89891a5a45.mp3",
    "https://cdn.pixabay.com/download/audio/2022/08/02/audio_884fe92c21.mp3",
    "https://cdn.pixabay.com/download/audio/2021/11/25/audio_91b32e02f7.mp3",
]


def baixar_musica() -> str:
    """
    Garante que a música de atenção está disponível localmente.
    Faz download apenas se não existir.

    Returns:
        Caminho do arquivo MP3 da música.
    """
    os.makedirs(MUSICA_DIR, exist_ok=True)

    if os.path.exists(MUSICA_PATH):
        tamanho = os.path.getsize(MUSICA_PATH)
        if tamanho > 50_000:  # Pelo menos 50 KB (arquivo válido)
            print(f"  🎵 Música já em cache: {MUSICA_PATH}")
            return MUSICA_PATH

    print("  ⬇️  Baixando música de atenção royalty-free...")

    for url in MUSICAS_URLS:
        try:
            resp = requests.get(url, timeout=30, stream=True)
            if resp.status_code == 200:
                with open(MUSICA_PATH, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                tamanho_kb = os.path.getsize(MUSICA_PATH) / 1024
                print(f"  ✅ Música baixada: {MUSICA_PATH} ({tamanho_kb:.0f} KB)")
                return MUSICA_PATH
        except Exception as e:
            print(f"  ⚠️  Falha ao baixar {url}: {e}")
            continue

    # Fallback: gera silêncio se não conseguir baixar
    print("  ⚠️  Não foi possível baixar música. Usando silêncio...")
    import subprocess
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=stereo",
        "-t", "120",
        "-b:a", "128k",
        MUSICA_PATH,
    ], capture_output=True)
    return MUSICA_PATH


if __name__ == "__main__":
    p = baixar_musica()
    print(f"Música: {p}")
