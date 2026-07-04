"""
montar_short.py
───────────────
Passo 5 do Pipeline Canal Cortes.

Monta o Short 9:16 (1080×1920) com:
  1. Face tracking via MediaPipe — detecta o rosto predominante
     e aplica crop dinâmico acompanhando quem fala
  2. Redimensionamento para 1080×1920 (9:16)
  3. Overlay de legendas SRT em estilo moderno (fonte grande, sombra)
  4. Safeguard: se nenhum rosto detectado, usa crop central

Saída: output/short_base.mp4 (sem inserções 1:1 nem música)
       (essas serão adicionadas pelo inserir_contexto.py)
"""

import os
import re
import json
import subprocess
import tempfile

ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")

# Resolução alvo para Shorts (9:16)
SHORT_W = 1080
SHORT_H = 1920

# A cada quantos frames detectar o rosto (performance vs. precisão)
FACE_DETECT_INTERVAL = 15   # ~0.5s a 30fps


def _escape_srt_path(path: str) -> str:
    """Escapa caminho do SRT para uso no filtro subtitles do FFmpeg."""
    path = path.replace("\\", "/")
    path = re.sub(r"^([A-Za-z]):", r"\1\\:", path)
    return path


def _detectar_rostos_mediapipe(video_path: str) -> list:
    """
    Detecta posições de rosto frame a frame usando MediaPipe.
    Retorna lista de (frame_idx, cx_norm, cy_norm) com posição
    normalizada do centro do rosto (0.0 a 1.0).

    Retorna lista vazia se MediaPipe não estiver disponível.
    """
    try:
        import cv2
        import mediapipe as mp
        # Import explícito para evitar problemas de attribute error em alguns envs
        from mediapipe.python.solutions import face_detection as mp_face
        import numpy as np

        detections_data = []

        cap = cv2.VideoCapture(video_path)
        fps          = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        print(f"  🎥 Analisando {total_frames} frames a {fps:.1f}fps...")

        with mp_face.FaceDetection(
            model_selection=1,       # Modelo de longa distância
            min_detection_confidence=0.5
        ) as detector:
            frame_idx = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % FACE_DETECT_INTERVAL == 0:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    result = detector.process(rgb)

                    if result.detections:
                        # Pega o rosto com maior bounding box (mais próximo da câmera)
                        melhor = max(
                            result.detections,
                            key=lambda d: d.location_data.relative_bounding_box.width
                                          * d.location_data.relative_bounding_box.height
                        )
                        bb = melhor.location_data.relative_bounding_box
                        cx = bb.xmin + bb.width / 2
                        cy = bb.ymin + bb.height / 2
                        detections_data.append((frame_idx, cx, cy))

                frame_idx += 1

        cap.release()
        print(f"  ✅ {len(detections_data)} detecções de rosto encontradas")
        return detections_data

    except ImportError:
        print("  ⚠️  MediaPipe/OpenCV não disponível. Usando crop central.")
        return []
    except Exception as e:
        print(f"  ⚠️  Erro no face tracking: {e}. Usando crop central.")
        return []


def _calcular_trajetoria_suave(detections: list, total_frames: int, video_w: int, video_h: int) -> list:
    """
    Suaviza a trajetória do centro de crop para evitar movimentos bruscos.
    Retorna lista de (frame_idx, crop_x, crop_y) com coordenadas absolutas.

    crop_x, crop_y = canto superior esquerdo do crop de 9:16 centrado no rosto.
    """
    import numpy as np

    # Determina dimensões do crop para 9:16
    if video_h / video_w >= 9 / 16:
        # Vídeo mais alto que 9:16 → crop horizontal
        crop_h = video_h
        crop_w = int(video_h * 9 / 16)
    else:
        # Vídeo mais largo que 9:16 → crop vertical (mais comum em podcasts landscape)
        crop_w = int(video_h * 9 / 16)
        crop_h = video_h
        if crop_w > video_w:
            crop_w = video_w
            crop_h = int(video_w * 16 / 9)

    # Limita crop ao tamanho do vídeo
    crop_w = min(crop_w, video_w)
    crop_h = min(crop_h, video_h)

    # Posições brutas dos rostos
    frames_det = [d[0] for d in detections]
    cx_norm    = [d[1] for d in detections]
    cy_norm    = [d[2] for d in detections]

    # Interpola para todos os frames
    if not frames_det:
        # Sem rosto: crop central
        cx_all = np.full(total_frames, 0.5)
        cy_all = np.full(total_frames, 0.4)  # Ligeiramente acima do centro
    else:
        cx_all = np.interp(range(total_frames), frames_det, cx_norm)
        cy_all = np.interp(range(total_frames), frames_det, cy_norm)
        # Preenche bordas com o primeiro/último valor
        cx_all[:frames_det[0]]  = cx_norm[0]
        cy_all[:frames_det[0]]  = cy_norm[0]
        cx_all[frames_det[-1]:] = cx_norm[-1]
        cy_all[frames_det[-1]:] = cy_norm[-1]

    # Suavização com média móvel (janela de 90 frames = ~3s)
    window = 90
    kernel = np.ones(window) / window
    cx_smooth = np.convolve(cx_all, kernel, mode='same')
    cy_smooth = np.convolve(cy_all, kernel, mode='same')

    # Converte para coordenadas absolutas do crop
    trajetoria = []
    for i in range(total_frames):
        # Centro do rosto em pixels
        rosto_x = int(cx_smooth[i] * video_w)
        rosto_y = int(cy_smooth[i] * video_h)

        # Canto superior esquerdo do crop
        x = rosto_x - crop_w // 2
        y = rosto_y - crop_h // 2

        # Clampeia dentro dos limites
        x = max(0, min(x, video_w - crop_w))
        y = max(0, min(y, video_h - crop_h))

        trajetoria.append((i, x, y, crop_w, crop_h))

    return trajetoria


def _obter_dimensoes_video(video_path: str) -> tuple:
    """Retorna (largura, altura, fps, total_frames) do vídeo."""
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
            frames = int(s.get("nb_frames", 0)) or int(float(s.get("duration", 60)) * fps)
            return w, h, fps, frames
    return 1920, 1080, 30, 1800


def _processar_dinamico_cv2_ffmpeg(
    video_path: str,
    trajetoria: list,
    output_path: str,
    video_w: int,
    video_h: int,
    srt_path: str,
):
    """
    Processa o vídeo:
      1. Lê frame a frame com OpenCV e corta usando a trajetória dinâmica
      2. Envia frames cortados via pipe (stdin) para o FFmpeg
      3. FFmpeg recebe, junta o áudio original, aplica filtros (escala, hflip, saturação, legendas) e codifica.
    """
    import cv2
    import numpy as np
    
    if not trajetoria:
        # Fallback se não há trajetória (crop central)
        cw = int(video_h * 9 / 16)
        ch = video_h
        x0 = (video_w - cw) // 2
        y0 = 0
        trajetoria = [(i, x0, y0, cw, ch) for i in range(1800)] # dummy
    
    # Todos os crops devem ter o mesmo tamanho (do primeiro frame)
    _, _, _, cw, ch = trajetoria[0]
    crop_w = min(cw, video_w)
    crop_h = min(ch, video_h)
    
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # ── Configura os filtros do FFmpeg ─────────────────────────────────────────
    subtitle_style = ",".join([
        "Fontname=Arial Black",
        "FontSize=16",           # Ajustado para a escala do FFmpeg (equivale a ~100px no vídeo real)
        "PrimaryColour=&H00FFFFFF",
        "OutlineColour=&H00000000",
        "BackColour=&H80000000",
        "BorderStyle=1",
        "Outline=2",
        "Shadow=1",
        "Alignment=2",           # Inferior centralizado
        "MarginV=20",            # Ajustado para ~130px de distância do rodapé real
    ])

    srt_escaped = _escape_srt_path(srt_path)

    filter_complex = (
        f"[0:v]scale={SHORT_W}:{SHORT_H}:force_original_aspect_ratio=decrease,"
        f"pad={SHORT_W}:{SHORT_H}:(ow-iw)/2:(oh-ih)/2:black,"
        f"hflip," # Inversão horizontal anti-cópia
        f"eq=saturation=1.3," # Cores mais vivas
        f"subtitles='{srt_escaped}':force_style='{subtitle_style}'[v]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{crop_w}x{crop_h}",
        "-pix_fmt", "bgr24",
        "-r", str(fps),
        "-i", "-",               # Entrada 0: Pipe de vídeo do OpenCV
        "-i", video_path,        # Entrada 1: Vídeo original (para pegar o áudio)
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "1:a",           # Mapeia áudio do arquivo original
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]

    print(f"  🔄 Processando {total_frames} frames com crop dinâmico e enviando ao FFmpeg...")
    
    # Inicia processo do FFmpeg aguardando frames pelo stdin
    processo = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    
    frame_idx = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            # Garante que temos as coordenadas pro frame atual
            if frame_idx < len(trajetoria):
                _, x, y, _, _ = trajetoria[frame_idx]
            else:
                _, x, y, _, _ = trajetoria[-1]
                
            # Realiza o crop no OpenCV
            frame_crop = frame[y:y+crop_h, x:x+crop_w]
            
            # Envia frame cortado pro FFmpeg
            processo.stdin.write(frame_crop.tobytes())
            frame_idx += 1
            
        if frame_idx == 0:
            raise RuntimeError("OpenCV falhou ao ler frames do vídeo original (codec não suportado?).")

            
    except BrokenPipeError:
        pass
    except Exception as e:
        print(f"  ⚠️ Erro durante o envio de frames: {e}")
    finally:
        cap.release()
        if processo.stdin:
            processo.stdin.close()
        processo.wait()
        
    if processo.returncode != 0:
        stderr_output = processo.stderr.read().decode('utf-8', errors='ignore')
        raise RuntimeError(f"FFmpeg falhou na montagem 9:16:\n{stderr_output[-500:]}")


def montar_short(
    video_path: str,
    srt_path: str,
    output_dir: str = OUTPUT_DIR,
) -> str:
    """
    Aplica face tracking e formata o vídeo em 9:16 com legendas.

    Args:
        video_path : vídeo original baixado
        srt_path   : arquivo SRT com legendas
        output_dir : pasta de saída

    Returns:
        Caminho do vídeo processado (output/short_base.mp4)
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "short_base.mp4")

    # Obtém dimensões do vídeo
    video_w, video_h, fps, total_frames = _obter_dimensoes_video(video_path)
    print(f"  📐 Vídeo original: {video_w}×{video_h} @ {fps:.1f}fps ({total_frames} frames)")

    # Detecta rostos
    print("  👤 Detectando rostos com MediaPipe...")
    detections = _detectar_rostos_mediapipe(video_path)

    # Calcula trajetória suave do crop
    trajetoria = _calcular_trajetoria_suave(detections, total_frames, video_w, video_h)

    # Aplica crop dinâmico (OpenCV) + escala + filtros + legendas (FFmpeg)
    print(f"  🎬 Montando Short 9:16 ({SHORT_W}×{SHORT_H}) com filtros visuais...")
    _processar_dinamico_cv2_ffmpeg(
        video_path, trajetoria, output_path,
        video_w, video_h, srt_path
    )

    tamanho_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  ✅ Short base pronto: {output_path} ({tamanho_mb:.1f} MB)")
    return output_path


if __name__ == "__main__":
    import sys
    video = sys.argv[1] if len(sys.argv) > 1 else "output/trecho_original.mp4"
    srt   = sys.argv[2] if len(sys.argv) > 2 else "output/legendas.srt"
    montar_short(video, srt)
