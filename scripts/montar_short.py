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

try:
    import cv2
    import mediapipe as mp
    import numpy as np
    HAS_CV2_MP = True
except ImportError:
    HAS_CV2_MP = False

ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")

# Resolução alvo para Shorts (9:16)
SHORT_W = 1080
SHORT_H = 1920


def _escape_srt_path(path: str) -> str:
    """Escapa caminho para uso no filtro subtitles do FFmpeg."""
    # O uso de caminhos relativos evita problemas crônicos do FFmpeg com "C:/" no Windows
    # Mas no Linux podemos usar caminhos absolutos se preferir. Aqui usamos relativo limpo.
    rel_path = os.path.relpath(path).replace("\\", "/")
    # O FFmpeg exige escape de dois pontos se formos usar caminho absoluto
    return rel_path.replace(":", "\\:")


def _garantir_fonte() -> str:
    """Baixa a fonte Montserrat Black se não existir e retorna o caminho absoluto do .ttf."""
    fonts_dir = os.path.join(ROOT_DIR, "assets", "fonts")
    os.makedirs(fonts_dir, exist_ok=True)
    font_path = os.path.join(fonts_dir, "Montserrat-Black.ttf")
    if not os.path.exists(font_path):
        print("  🔠 Baixando fonte Montserrat Black...")
        import urllib.request
        url = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Black.ttf"
        try:
            urllib.request.urlretrieve(url, font_path)
            print("  ✅ Fonte baixada com sucesso.")
        except Exception as e:
            print(f"  ⚠️  Erro ao baixar fonte: {e}")
    return font_path


def _srt_time_to_seconds(ts: str) -> float:
    """Converte timestamp SRT (HH:MM:SS,mmm) para segundos float."""
    ts = ts.replace(',', '.')
    partes = ts.split(':')
    return int(partes[0]) * 3600 + int(partes[1]) * 60 + float(partes[2])


def _srt_para_drawtext(srt_path: str, font_path: str) -> str:
    """
    Lê o arquivo SRT e gera uma cadeia de filtros drawtext do FFmpeg.
    Usa o arquivo .ttf diretamente — sem depender de fontconfig ou libass.
    Retorna string vazia se não houver entradas.
    """
    try:
        with open(srt_path, "r", encoding="utf-8") as f:
            conteudo = f.read()
    except Exception as e:
        print(f"  ⚠️  Erro ao ler SRT: {e}")
        return ""

    # Escapa o caminho da fonte para FFmpeg (barras, dois-pontos)
    font_escaped = font_path.replace("\\", "/")
    if ":" in font_escaped:  # Windows C:\...
        font_escaped = font_escaped.replace(":", "\\\\:")

    # Parseia blocos SRT: número / timestamps / texto
    blocos = re.split(r"\n\n+", conteudo.strip())
    filtros = []

    for bloco in blocos:
        linhas = bloco.strip().splitlines()
        if len(linhas) < 3:
            continue
        try:
            # Linha 0: índice, Linha 1: timestamps, Linha 2+: texto
            arrow_line = linhas[1]
            if "-->" not in arrow_line:
                continue
            inicio_str, fim_str = arrow_line.split("-->")
            t_inicio = _srt_time_to_seconds(inicio_str.strip())
            t_fim    = _srt_time_to_seconds(fim_str.strip())
            texto    = " ".join(linhas[2:]).strip()
        except Exception:
            continue

        if not texto:
            continue

        # Escapa caracteres especiais do FFmpeg drawtext
        texto = (
            texto
            .replace("\\", "")
            .replace("'", "")
            .replace(":", " ")
            .replace("%", "%%")
            .replace("\n", " ")
        )

        f = (
            f"drawtext="
            f"fontfile='{font_escaped}':"
            f"text='{texto}':"
            f"fontsize=90:"
            f"fontcolor=yellow:"
            f"x=(w-text_w)/2:"
            f"y=h-text_h-220:"
            f"box=1:"
            f"boxcolor=black@0.55:"
            f"boxborderw=15:"
            f"enable='between(t,{t_inicio:.3f},{t_fim:.3f})'"
        )
        filtros.append(f)

    if not filtros:
        print("  ⚠️  SRT sem entradas válidas para drawtext.")
        return ""

    print(f"  📝 {len(filtros)} entradas de legenda via drawtext.")
    return ",".join(filtros)


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


import shutil

def _calcular_tracking_dinamico_ffmpeg(video_path: str, original_w: int, original_h: int) -> str:
    """
    Usa FFmpeg para extrair frames (1 a cada 4 segs), detecta rostos com MediaPipe,
    e constrói a expressão de crop dinâmica para o FFmpeg, sem re-renderizar o vídeo.
    """
    if not HAS_CV2_MP:
        return None

    crop_w, crop_h, _, y_off = _calcular_crop_central(original_w, original_h)
    
    print("  👁️  Iniciando rastreamento facial (Nível 2 via análise matemática de 4s)...")
    
    tmp_dir = os.path.join(os.path.dirname(video_path), "tmp_frames_track")
    os.makedirs(tmp_dir, exist_ok=True)
    
    # Extrai 1 frame a cada 1 segundo
    cmd_extract = [
        "ffmpeg", "-y", "-v", "error",
        "-i", video_path,
        "-vf", "fps=1",
        "-q:v", "2",
        os.path.join(tmp_dir, "frame_%04d.jpg")
    ]
    subprocess.run(cmd_extract)
    
    frames = sorted(glob.glob(os.path.join(tmp_dir, "*.jpg")))
    if not frames:
        print("  ⚠️  Falha ao extrair frames para tracking. Usando corte estático.")
        return None
        
    mp_face_detection = mp.solutions.face_detection
    
    center_x = int((original_w - crop_w) / 2.0)
    last_x = center_x
    x_values = []
    
    with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as face_detection:
        for fpath in frames:
            img = cv2.imread(fpath)
            if img is None:
                x_values.append(last_x)
                continue
                
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = face_detection.process(img_rgb)
            
            if results.detections:
                det = results.detections[0]
                bbox = det.location_data.relative_bounding_box
                face_cx = int((bbox.xmin + bbox.width / 2) * original_w)
                ideal_x = int(face_cx - (crop_w / 2))
                ideal_x = max(0, min(ideal_x, original_w - crop_w))
                last_x = ideal_x
                
            x_values.append(last_x)
            
    # Limpeza
    shutil.rmtree(tmp_dir, ignore_errors=True)
    
    if not x_values:
        return None
        
    # Constrói a expressão de crop dinâmica
    # Ex: if(lt(t,4),X0,if(lt(t,8),X1,...))
    expr = str(x_values[-1])
    interval = 1
    for i in range(len(x_values) - 2, -1, -1):
        limit = (i + 1) * interval
        expr = f"if(lt(t,{limit}),{x_values[i]},{expr})"
        
    return expr



def _gerar_expressao_zoom(duracao_total: float) -> str:
    """
    Gera uma expressão FFmpeg para jump cuts (saltos de zoom) aleatórios.
    Cria segmentos de 3 a 6 segundos com zoom (1.15) ou sem zoom (1.0),
    garantindo que não haja 3 cortes seguidos do mesmo tipo.
    """
    t_atual = 0.0
    cortes = []
    
    opcoes = [1.0, 1.15]
    historico = []
    
    while t_atual < duracao_total:
        dur_corte = random.uniform(3.0, 6.0)
        t_fim = t_atual + dur_corte
        
        # Se os dois últimos cortes foram iguais, força a troca
        if len(historico) >= 2 and historico[-1] == historico[-2]:
            opcoes_disp = [o for o in opcoes if o != historico[-1]]
        else:
            opcoes_disp = opcoes
            
        zoom_val = random.choice(opcoes_disp)
        historico.append(zoom_val)
        cortes.append((t_fim, zoom_val))
        t_atual = t_fim
        
    # Monta a expressão FFmpeg com ifs aninhados:
    # ex: if(lt(t, 4.5), 1.0, if(lt(t, 8.2), 1.15, 1.0))
    if not cortes:
        return "1.0"
        
    expr = str(cortes[-1][1]) # O último valor serve como fallback no final
    for t_fim, zoom_val in reversed(cortes[:-1]):
        expr = f"if(lt(t,{t_fim:.2f}),{zoom_val},{expr})"
        
    return expr


def _montar_ffmpeg_puro(
    video_path: str,
    output_path: str,
    video_w: int,
    video_h: int,
    srt_path: str,
    duracao: float,
    crop_x_expr: str = None,
):
    """
    Monta o Short 9:16 inteiramente com FFmpeg — sem OpenCV.

    Filtros aplicados:
      1. crop      — recorta a região central ou rastreada dinamicamente
      2. scale     — redimensiona para 1080×1920
      3. pad       — garante dimensões exatas com bordas pretas
      4. hflip     — inversão horizontal anti-cópia
      5. eq        — saturação elevada (cores mais vivas)
      6. subtitles — legendas SRT em estilo moderno
    """
    crop_w, crop_h, default_x_off, y_off = _calcular_crop_central(video_w, video_h)

    if crop_x_expr:
        x_off_str = f"'{crop_x_expr}'"
        print(f"  ✂️  Crop Dinâmico: {crop_w}×{crop_h} em Y={y_off} → escala para {SHORT_W}×{SHORT_H}")
    else:
        x_off_str = str(default_x_off)
        print(f"  ✂️  Crop Estático: {crop_w}×{crop_h} em ({x_off_str},{y_off}) → escala para {SHORT_W}×{SHORT_H}")

    # Usa fonte embarcada e drawtext (sem libass/fontconfig) para legendas garantidas
    font_path = _garantir_fonte()
    drawtext_chain = _srt_para_drawtext(srt_path, font_path)

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

    zoom_expr = _gerar_expressao_zoom(duracao)
    print(f"  🔍 Zoom Aleatório (Jump Cuts): ativo para {duracao:.1f}s")
    
    # Monta a cadeia de filtros de vídeo
    # O drawtext é adicionado APÓS os demais filtros visuais
    vf_base = (
        f"crop={crop_w}:{crop_h}:{x_off_str}:{y_off},"
        f"scale={SHORT_W}:{SHORT_H}:force_original_aspect_ratio=decrease,"
        f"pad={SHORT_W}:{SHORT_H}:(ow-iw)/2:(oh-ih)/2:black,"
        f"scale=w='{SHORT_W}*({zoom_expr})':h='{SHORT_H}*({zoom_expr})':eval=frame,"
        f"crop={SHORT_W}:{SHORT_H}:(iw-{SHORT_W})/2:(ih-{SHORT_H})/2:exact=1,"
        f"hflip,"
        f"eq=saturation=1.3"
    )
    # Concatena drawtext se houver entradas válidas
    if drawtext_chain:
        vf_base = vf_base + "," + drawtext_chain
    # Imprime preview do drawtext para debug no log
    if drawtext_chain:
        print(f"  📝 {drawtext_chain.count('drawtext=')} entrada(s) de legenda via drawtext.")
        print(f"  📂 Fonte: {font_path}")
    else:
        print("  ⚠️  Nenhuma entrada de legenda gerada!")

    cmd = ["ffmpeg", "-y", "-i", video_path]
    input_idx = 1
    audio_filters = []
    
    # Áudios extras
    if musica_escolhida:
        cmd.extend(["-stream_loop", "-1", "-i", musica_escolhida])
        audio_filters.append((input_idx, "volume=0.10", "a_musica"))
        input_idx += 1
        
    if notificacao:
        cmd.extend(["-i", notificacao])
        audio_filters.append((input_idx, "silenceremove=start_periods=1:start_duration=0:start_threshold=-50dB,volume=1.5", "a_notif"))
        input_idx += 1

    # SEMPRE usa -vf para o vídeo (evita conflito de aspas no filter_complex com drawtext)
    cmd.extend(["-vf", vf_base])
    
    if audio_filters:
        # Monta filter_complex só para o áudio
        fc_parts = []
        mix_inputs = ["[0:a]"]
        for idx, filtro, label in audio_filters:
            fc_parts.append(f"[{idx}:a]{filtro}[{label}]")
            mix_inputs.append(f"[{label}]")
        n = len(mix_inputs)
        mix_str = "".join(mix_inputs)
        fc_parts.append(f"{mix_str}amix=inputs={n}:duration=first:dropout_transition=0[aout]")
        cmd.extend([
            "-filter_complex", ";".join(fc_parts),
            "-map", "0:v",
            "-map", "[aout]",
        ])
    else:
        cmd.extend(["-map", "0:v", "-map", "0:a"])

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
        print(f"  ⚠️  FFmpeg falhou. Detalhes:")
        print(f"  stderr: {erro[-400:]}")
        raise RuntimeError(f"FFmpeg falhou na montagem 9:16:\n{erro}")
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

    crop_x_expr = None
    if HAS_CV2_MP:
        crop_x_expr = _calcular_tracking_dinamico_ffmpeg(video_path, video_w, video_h)

    # Monta o Short 9:16 com FFmpeg
    _montar_ffmpeg_puro(video_path, output_path, video_w, video_h, srt_path, duracao, crop_x_expr)

    tamanho_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  ✅ Short base pronto: {output_path} ({tamanho_mb:.1f} MB)")
    return output_path


if __name__ == "__main__":
    import sys
    video = sys.argv[1] if len(sys.argv) > 1 else "output/trecho_original.mp4"
    srt   = sys.argv[2] if len(sys.argv) > 2 else "output/legendas.srt"
    montar_short(video, srt)
