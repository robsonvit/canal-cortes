import os
import subprocess

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSICAS_DIR = os.path.join(ROOT_DIR, "assets", "audios", "musicas")
EFEITOS_DIR = os.path.join(ROOT_DIR, "assets", "audios", "efeitos")

os.makedirs(MUSICAS_DIR, exist_ok=True)
os.makedirs(EFEITOS_DIR, exist_ok=True)

MUSICAS = [
    "Metamorphosis - Interworld",
    "Murder In My Mind - Kordhell",
    "Sahara - Hensonn",
    "Neon Blade - MoonDeity",
    "Disaster - KSLV Noh",
    "Paris - Else",
    "Blade Runner 2049 - Synthwave Goose",
    "In Essence - Ka$tro",
    "After Dark Slowed Reverb - Mr.Kitty",
    "Aesthetic - Tollan Kim"
]

EFEITOS = {
    "notificacao": "iphone notification ding sound effect no copyright"
}

def baixar_audio(query, pasta, nome_arquivo):
    print(f"Baixando: {query}")
    caminho_saida = os.path.join(pasta, f"{nome_arquivo}.%(ext)s")
    
    # Verifica se já existe mp3
    if os.path.exists(os.path.join(pasta, f"{nome_arquivo}.mp3")):
        print(f"  -> Já existe: {nome_arquivo}.mp3. Pulando.")
        return
        
    cmd = [
        "yt-dlp",
        f"ytsearch1:{query}",
        "-x",
        "--audio-format", "mp3",
        "-o", caminho_saida,
        "--quiet", "--no-warnings"
    ]
    subprocess.run(cmd)
    print(f"  -> Concluído: {nome_arquivo}.mp3")

if __name__ == "__main__":
    print("Iniciando download de efeitos...")
    for chave, query in EFEITOS.items():
        baixar_audio(query, EFEITOS_DIR, chave)
        
    print("\nIniciando download de músicas de fundo...")
    for i, query in enumerate(MUSICAS, 1):
        # Cria um nome seguro para o arquivo
        nome_seguro = f"{i:02d}_{query.replace(' - ', '_').replace(' ', '_').lower()}"
        baixar_audio(query, MUSICAS_DIR, nome_seguro)
        
    print("\n✅ Todos os áudios foram baixados.")
