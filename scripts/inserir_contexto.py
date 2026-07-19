"""
inserir_contexto.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Passo 6 do Pipeline Canal Cortes.

Enriquece o Short com:
  1. InserÃ§Ãµes visuais 1:1 (imagens/vÃ­deos contextuais do Pexels)
     sobrepostas no canto inferior direito por 3-4 segundos
  2. MÃºsica de atenÃ§Ã£o ao fundo (mixada com volume baixo)

Fluxo:
  a. Envia a transcriÃ§Ã£o para Groq AI â†’ extrai 2-3 temas visuais chave
  b. Busca imagens/vÃ­deos no Pexels para cada tema
  c. Cria um plano de timing (quando mostrar cada inserÃ§Ã£o)
  d. Aplica os overlays via FFmpeg filter_complex
  e. Adiciona mÃºsica de fundo mixada
"""

import os
import json
import re
import random
import subprocess
import requests

from groq import Groq

ROOT_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR    = os.path.join(ROOT_DIR, "output")
PEXELS_KEY    = os.environ.get("PEXELS_API_KEY", "")

# Tamanho do overlay 1:1 (quadrado) em pixels na tela 9:16
OVERLAY_SIZE  = 800   # Aumentado para 800px para ficar em destaque no centro
OVERLAY_DUR   = 2.45  # DuraÃ§Ã£o de cada inserÃ§Ã£o em segundos (reduzido em 30%)
# PosiÃ§Ã£o do overlay: centro exato do vÃ­deo
OVERLAY_X     = f"{(1080 - OVERLAY_SIZE) // 2}"
OVERLAY_Y     = f"{(1920 - OVERLAY_SIZE) // 2}"


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# AnÃ¡lise de temas via Groq AI
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _extrair_temas(texto: str, output_dir: str = OUTPUT_DIR) -> list:
    """
    Envia o conteÃºdo do SRT (ou a transcriÃ§Ã£o) para Groq AI e extrai temas visuais chave.
    Retorna lista de dicts: [{termo_pt, termo_en, momento_inicio}]
    """
    srt_path = os.path.join(output_dir, "legendas.srt")
    try:
        with open(srt_path, "r", encoding="utf-8") as f:
            texto_para_ia = f.read()[:2000] # Passa o SRT com os timestamps para a IA
    except Exception:
        texto_para_ia = texto[:800]

    cliente = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    prompt = f"""Analise esta transcriÃ§Ã£o de um podcast em portuguÃªs brasileiro e extraia 3 temas visuais marcantes.

Para cada tema, retorne:
- Uma palavra-chave em portuguÃªs (o que foi citado/discutido)
- Um termo de busca em inglÃªs para encontrar imagens (simples, 2-3 palavras)
- O segundo aproximado em que esse tema aparece na transcriÃ§Ã£o

Retorne APENAS um JSON vÃ¡lido neste formato exato:
[
  {{"tema_pt": "inteligÃªncia artificial", "busca_en": "artificial intelligence technology", "segundo": 5}},
  {{"tema_pt": "dinheiro", "busca_en": "money cash finance", "segundo": 20}},
  {{"tema_pt": "famÃ­lia", "busca_en": "happy family together", "segundo": 40}}
]

TranscriÃ§Ã£o com tempos (SRT):
{texto_para_ia}

Retorne apenas o JSON, sem explicaÃ§Ãµes."""

    try:
        resp = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
        )
        conteudo = resp.choices[0].message.content.strip()

        # Extrai o JSON da resposta
        match = re.search(r"\[.*?\]", conteudo, re.DOTALL)
        if match:
            temas = json.loads(match.group())
            print(f"  ðŸ§  Temas extraÃ­dos pela IA: {[t['tema_pt'] for t in temas]}")
            return temas
    except Exception as e:
        print(f"  âš ï¸  Erro ao extrair temas: {e}")

    # Fallback com temas genÃ©ricos de podcast
    return [
        {"tema_pt": "conversa", "busca_en": "people talking conversation", "segundo": 5},
        {"tema_pt": "sucesso", "busca_en": "success achievement", "segundo": 25},
        {"tema_pt": "pensamento", "busca_en": "thinking idea inspiration", "segundo": 45},
    ]


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Busca de imagens no Pexels
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _buscar_imagem_pexels(termo: str) -> str | None:
    """
    Busca uma imagem quadrada (1:1) no Pexels para o tema dado.
    Retorna URL da imagem ou None se nÃ£o encontrar.
    """
    if not PEXELS_KEY:
        print(f"  âš ï¸  PEXELS_API_KEY nÃ£o configurada. Pulando inserÃ§Ã£o para '{termo}'.")
        return None

    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_KEY},
            params={"query": termo, "per_page": 5, "size": "medium"},
            timeout=15,
        )
        resp.raise_for_status()
        fotos = resp.json().get("photos", [])
        if fotos:
            foto = random.choice(fotos)
            # Usa versÃ£o medium (640px) para performance
            return foto["src"].get("medium") or foto["src"]["original"]
    except Exception as e:
        print(f"  âš ï¸  Pexels falhou para '{termo}': {e}")
    return None


def _baixar_imagem(url: str, destino: str) -> bool:
    """Baixa imagem para disco. Retorna True se sucesso."""
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        with open(destino, "wb") as f:
            f.write(resp.content)
        return True
    except Exception as e:
        print(f"  âš ï¸  Falha ao baixar imagem: {e}")
        return False


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CriaÃ§Ã£o do overlay 1:1 com FFmpeg
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _criar_overlay_quadrado(img_path: str, output_path: str, duracao: float):
    """
    Redimensiona a imagem para quadrado (1:1) com bordas arredondadas
    e a converte em clipe de vÃ­deo de 'duracao' segundos.
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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# FunÃ§Ã£o principal
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def inserir_contexto(
    video_base: str,
    texto_transcricao: str,
    output_dir: str = OUTPUT_DIR,
) -> str:
    """
    Adiciona inserÃ§Ãµes 1:1 contextuais ao Short (mantÃ©m o Ã¡udio intacto).

    Args:
        video_base          : caminho do short_base.mp4 (9:16 com legendas e mÃºsica)
        texto_transcricao   : texto completo da transcriÃ§Ã£o
        output_dir          : pasta de saÃ­da

    Returns:
        Caminho do vÃ­deo final (output/short_final.mp4)
    """
    os.makedirs(output_dir, exist_ok=True)
    clips_dir  = os.path.join(output_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)
    output_final = os.path.join(output_dir, "short_final.mp4")

    # â”€â”€ 1. Extrai temas via IA â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print("  ðŸ§  Analisando transcriÃ§Ã£o com Groq AI para extrair temas visuais...")
    temas = _extrair_temas(texto_transcricao, output_dir)

    # â”€â”€ 2. Baixa imagens do Pexels â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    overlays_prontos = []   # [(segundo_inicio, clip_path)]

    for i, tema in enumerate(temas):
        termo_en  = tema.get("busca_en", "podcast conversation")
        segundo   = float(tema.get("segundo", i * 15 + 5))
        tema_pt   = tema.get("tema_pt", "")

        print(f"  ðŸ–¼ï¸  [{i+1}/{len(temas)}] Buscando imagem para: '{tema_pt}' ({termo_en})")

        url_img = _buscar_imagem_pexels(termo_en)
        if not url_img:
            continue

        img_path  = os.path.join(clips_dir, f"overlay_img_{i}.jpg")
        clip_path = os.path.join(clips_dir, f"overlay_clip_{i}.mp4")

        if not _baixar_imagem(url_img, img_path):
            continue

        if _criar_overlay_quadrado(img_path, clip_path, OVERLAY_DUR):
            overlays_prontos.append((segundo, clip_path))
            print(f"     âœ… Overlay pronto para ~{segundo:.0f}s")
        else:
            print(f"     âš ï¸  Falha ao criar overlay para '{tema_pt}'")

    # â”€â”€ 3. Monta vÃ­deo final com FFmpeg â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print(f"\n  ðŸŽ¬ Montando vÃ­deo final com {len(overlays_prontos)} overlays...")

    import shutil
    if not overlays_prontos:
        print("  ðŸ“» Sem overlays disponÃ­veis. Copiando vÃ­deo intacto...")
        shutil.copy(video_base, output_final)
    else:
        # Com overlays:
        # Input 0 Ã© o video_base, Inputs 1..N sÃ£o os overlays
        inputs = ["-i", video_base]
        for _, clip_path in overlays_prontos:
            inputs += ["-i", clip_path]

        # Encadeia overlays: [prev_v][N:v]overlay=...[next_v]
        # Input 0 Ã© o video_base, Inputs 1+ sÃ£o os overlays
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
            "-map", "0:a",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            "-movflags", "+faststart",
            output_final,
        ]

        resultado = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
        if resultado.returncode != 0:
            print(f"  âš ï¸  FFmpeg com overlays falhou. Copiando vÃ­deo original...")
            print(f"  stderr: {resultado.stderr[-300:]}")
            shutil.copy(video_base, output_final)

    tamanho_mb = os.path.getsize(output_final) / (1024 * 1024)
    print(f"  âœ… VÃ­deo final com contexto: {output_final} ({tamanho_mb:.1f} MB)")
    return output_final


if __name__ == "__main__":
    import sys
    video   = sys.argv[1] if len(sys.argv) > 1 else "output/short_base.mp4"
    texto   = sys.argv[2] if len(sys.argv) > 2 else "Teste de contexto visual com IA"
    inserir_contexto(video, texto)

