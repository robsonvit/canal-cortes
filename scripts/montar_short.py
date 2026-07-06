"""
montar_short.py
───────────────
Passo 5 do Pipeline Canal Cortes.

Monta o Short 9:16 (1080×1920) com:
  1. Crop central inteligente (landscape → portrait)
  2. Redimensionamento para 1080×1920 (9:16)
  3. Overlay de legendas SRT em estilo moderno (fonte grande, sombra)
  4. Inversão horizontal anti-cópia + saturação elevada

ARQUITETURA: 100% FFmpeg nativo — sem dependência de OpenCV/MediaPipe
para decodificação. Garante compatibilidade com qualquer codec que o
yt-dlp baixar (H.264, AV1, VP9, etc.).

Saída: output/short_base.mp4 (sem inserções 1:1 nem música)
       (essas serão adicionadas pelo inserir_contexto.py)
"""

import os
import re
import json
import subprocess
import random
import glob

ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")

# Resolução alvo para Shorts (9:16)
SHORT_W = 1080
SHORT_H = 1920


def _escape_srt_path(path: str) -> str:
    """Escapa caminho do SRT para uso no filtro subtitles do FFmpeg."""
    path = path.replace("\\", "/")
    path = re.sub(r"^([A-Za-z]):", r"\1\\:", path)
    return path


def _obter_dimensoes_video(video_path: str) -> tuple:
    """Retorna (largura, altura, fps, total_frames, duracao_s) do vídeo."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        video_path,
    ]
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    dados = json.loads(resultado.stdout)
    for s in dados.get("streams", []):
        if s.get("codec_type") == "video":
            w = int(s.get("width", 1920))
            h = int(s.get("height", 1080))
            fps_raw = s.get("r_frame_rate", "30/1")
            num, den = fps_raw.split("/")
            fps = float(num) / float(den)
            dur = float(s.get("duration", 0)) or float(
                dados.get("format", {}).get("duration", 60)
            )
            frames = int(s.get("nb_frames", 0)) or int(dur * fps)
            codec  = s.get("codec_name", "unknown")
            print(f"  ℹ️  Codec detectado: {codec}")
            return w, h, fps, frames, dur
    return 1920, 1080, 30, 1800, 60.0


def _calcular_crop_central(video_w: int, video_h: int) -> tuple:
    """
    Calcula os parâmetros de crop para transformar landscape em portrait (9:16).
    Retorna (crop_w, crop_h, x_offset, y_offset).
    """
    alvo_ratio = 9 / 16

    if video_w >= video_h:
        # Landscape (mais largo): crop lateral, mantém altura total
        crop_h = video_h
        crop_w = int(video_h * alvo_ratio)
        if crop_w > video_w:
            crop_w = video_w
    else:
        # Portrait ou quadrado: crop vertical
        crop_w = video_w
        crop_h = int(video_w / alvo_ratio)
        if crop_h > video_h:
            crop_h = video_h

    # Centraliza o crop
    x_offset = (video_w - crop_w) // 2
    y_offset = max(0, (video_h - crop_h) // 4)  # Ligeiramente acima do centro (rostos)

    return crop_w, crop_h, x_offset, y_offset


def _montar_ffmpeg_puro(
    video_path: str,
    output_path: str,
    video_w: int,
    video_h: int,
    srt_path: str,
):
    """
    Monta o Short 9:16 inteiramente com FFmpeg — sem OpenCV.

    Filtros aplicados:
      1. crop      — recorta a região central de interesse
      2. scale     — redimensiona para 1080×1920
      3. pad       — garante dimensões exatas com bordas pretas
      4. hflip     — inversão horizontal anti-cópia
      5. eq        — saturação elevada (cores mais vivas)
      6. subtitles — legendas SRT em estilo moderno
    """
    crop_w, crop_h, x_off, y_off = _calcular_crop_central(video_w, video_h)

    print(f"  ✂️  Crop: {crop_w}×{crop_h} em ({x_off},{y_off}) → escala para {SHORT_W}×{SHORT_H}")

    subtitle_style = ",".join([
        "Fontname=Arial Black",
        "FontSize=16",
        "PrimaryColour=&H00FFFFFF",
        "OutlineColour=&H00000000",
        "BackColour=&H80000000",
        "BorderStyle=1",
        "Outline=2",
        "Shadow=1",
        "Alignment=2",
        "MarginV=20",
    ])

    srt_escaped = _escape_srt_path(srt_path)

    # --- Configuração dos Áudios Extras ---
    musicas_dir = os.path.join(ROOT_DIR, "assets", "audios", "musicas")
    efeitos_dir = os.path.join(ROOT_DIR, "assets", "audios", "efeitos")
    
    musica_escolhida = None
    notificacao = None
    
    if os.path.exists(musicas_dir):
        lista_musicas = glob.glob(os.path.join(musicas_dir, "*.mp3"))
        if lista_musicas:
            musica_escolhida = random.choice(lista_musicas)
            
    if os.path.exists(efeitos_dir):
        lista_efeitos = glob.glob(os.path.join(efeitos_dir, "*.mp3"))
        if lista_efeitos:
            notificacao = random.choice(lista_efeitos)
            
    print(f"  🎵 Música escolhida: {os.path.basename(musica_escolhida) if musica_escolhida else 'Nenhuma'}")
    print(f"  🔔 Notificação: {os.path.basename(notificacao) if notificacao else 'Nenhuma'}")

    vf_base = (
        f"crop={crop_w}:{crop_h}:{x_off}:{y_off},"
        f"scale={SHORT_W}:{SHORT_H}:force_original_aspect_ratio=decrease,"
        f"pad={SHORT_W}:{SHORT_H}:(ow-iw)/2:(oh-ih)/2:black,"
        f"hflip,"
        f"eq=saturation=1.3,"
        f"subtitles='{srt_escaped}':force_style='{subtitle_style}'"
    )

    cmd = ["ffmpeg", "-y", "-i", video_path]
    
    audio_inputs = ["[0:a]"]
    filter_complex = f"[0:v]{vf_base}[vout]"
    
    # Se houver música, adiciona em loop (stream_loop -1 precisa vir antes do -i)
    if musica_escolhida:
        cmd.extend(["-stream_loop", "-1", "-i", musica_escolhida])
        idx = len(audio_inputs)
        filter_complex += f"; [{idx}:a]volume=0.15[a_musica]"
        audio_inputs.append("[a_musica]")
        
    if notificacao:
        cmd.extend(["-i", notificacao])
        idx = len(audio_inputs) - 1 if not musica_escolhida else len(audio_inputs)
        filter_complex += f"; [{idx}:a]volume=0.8[a_notif]"
        audio_inputs.append("[a_notif]")

    if len(audio_inputs) > 1:
        inputs_str = "".join(audio_inputs)
        num_inputs = len(audio_inputs)
        filter_complex += f"; {inputs_str}amix=inputs={num_inputs}:duration=first:dropout_transition=2[aout]"
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]"
        ])
    else:
        cmd.extend([
            "-vf", vf_base,
        ])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ])

    print(f"  🎬 Executando FFmpeg para montagem 9:16...")
    resultado = subprocess.run(cmd, capture_output=True, text=True)

    if resultado.returncode != 0:
        erro = resultado.stderr[-800:]
        # Tenta fallback sem legendas (se o SRT for o problema)
        print(f"  ⚠️  FFmpeg com legendas falhou. Tentando sem legendas...")
        print(f"  stderr: {erro[-300:]}")

        vf_sem_sub = (
            f"crop={crop_w}:{crop_h}:{x_off}:{y_off},"
            f"scale={SHORT_W}:{SHORT_H}:force_original_aspect_ratio=decrease,"
            f"pad={SHORT_W}:{SHORT_H}:(ow-iw)/2:(oh-ih)/2:black,"
            f"hflip,"
            f"eq=saturation=1.3"
        )
        cmd_fallback = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", vf_sem_sub,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ]
        resultado2 = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if resultado2.returncode != 0:
            raise RuntimeError(
                f"FFmpeg falhou na montagem 9:16 (com e sem legendas):\n{resultado2.stderr[-500:]}"
            )
        print("  ℹ️  Short gerado sem legendas (SRT com problema).")
    else:
        print("  ✅ FFmpeg concluiu com sucesso.")


def montar_short(
    video_path: str,
    srt_path: str,
    output_dir: str = OUTPUT_DIR,
) -> str:
    """
    Formata o vídeo em 9:16 com crop central e legendas.

    Args:
        video_path : vídeo original baixado (qualquer codec)
        srt_path   : arquivo SRT com legendas
        output_dir : pasta de saída

    Returns:
        Caminho do vídeo processado (output/short_base.mp4)
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "short_base.mp4")

    # Obtém dimensões do vídeo via ffprobe (funciona com qualquer codec)
    video_w, video_h, fps, total_frames, duracao = _obter_dimensoes_video(video_path)
    print(f"  📐 Vídeo original: {video_w}×{video_h} @ {fps:.1f}fps | {duracao:.1f}s ({total_frames} frames)")

    # Monta o Short 9:16 com FFmpeg puro
    _montar_ffmpeg_puro(video_path, output_path, video_w, video_h, srt_path)

    tamanho_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  ✅ Short base pronto: {output_path} ({tamanho_mb:.1f} MB)")
    return output_path


if __name__ == "__main__":
    import sys
    video = sys.argv[1] if len(sys.argv) > 1 else "output/trecho_original.mp4"
    srt   = sys.argv[2] if len(sys.argv) > 2 else "output/legendas.srt"
    montar_short(video, srt)
