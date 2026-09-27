from pytubefix import YouTube
from pytubefix.cli import on_progress

url = "https://youtube.com/shorts/Brl0mNugIs0"
print(f"Buscando {url}...")
yt = YouTube(url)
audio_stream = yt.streams.get_audio_only()
print("Baixando áudio...")
audio_stream.download(filename="reference_audio.mp3")
print("Áudio baixado com sucesso.")
