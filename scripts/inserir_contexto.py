"""
inserir_contexto.py
───────────────────
Passo 6 do Pipeline Canal Cortes.

Enriquece o Short com:
  1. Inserções visuais 1:1 (imagens/vídeos contextuais do Pexels)
     sobrepostas no canto inferior direito por 3-4 segundos
  2. Música de atenção ao fundo (mixada com volume baixo)

Fluxo:
  a. Envia a transcrição para Groq AI → extrai 2-3 temas visuais chave
  b. Busca imagens/vídeos no Pexels para cada tema
  c. Cria um plano de timing (quando mostrar cada inserção)
  d. Aplica os overlays via FFmpeg filter_complex
  e. Adiciona música de fundo mixada
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
OVERLAY_DUR   = 2.45  # Duração de cada inserção em segundos (reduzido em 30%)
# Posição do overlay: centro exato do vídeo
OVERLAY_X     = f"{(1080 - OVERLAY_SIZE) // 2}"
OVERLAY_Y     = f"{(1920 - OVERLAY_SIZE) // 2}"


# ─────────────────────────────────────────────────────────────────────────────
# Análise de temas via Groq AI
# ─────────────────────────────────────────────────────────────────────────────
def _extrair_temas(texto: str, output_dir: str = OUTPUT_DIR) -> list:
    """
    Envia o conteúdo do SRT (ou a transcrição) para Groq AI e extrai temas visuais chave.
    Retorna lista de dicts: [{termo_pt, termo_en, momento_inicio}]
    """
    srt_path = os.path.join(output_dir, "legendas.srt")
    try:
        with open(srt_path, "r", encoding="utf-8") as f:
            texto_para_ia = f.read()[:2000] # Passa o SRT com os timestamps para a IA
    except Exception:
        texto_para_ia = texto[:800]

    cliente = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    prompt = f"""Analise esta transcrição de um podcast em português brasileiro e extraia 3 temas visuais marcantes.

Para cada tema, retorne:
- Uma palavra-chave em português (o que foi citado/discutido)
- Um termo de busca em inglês para encontrar imagens (simples, 2-3 palavras)
- O segundo aproximado em que esse tema aparece na transcrição

Retorne APENAS um JSON válido neste formato exato:
[
  {{"tema_pt": "inteligência artificial", "busca_en": "artificial intelligence technology", "segundo": 5}},
  {{"tema_pt": "dinheiro", "busca_en": "money cash finance", "segundo": 20}},
  {{"tema_pt": "família", "busca_en": "happy family together", "segundo": 40}}
]

Transcrição com tempos (SRT):
{texto_para_ia}

Retorne apenas o JSON, sem explicações."""

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
            print(f"  🧠 Temas extraídos pela IA: {[t['tema_pt'] for t in temas]}")
            return temas
    except Exception as e:
        print(f"  ⚠️  Erro ao extrair temas: {e}")

    # Fallback com temas genéricos de podcast
    return [
        {"tema_pt": "conversa", "busca_en": "people talking conversation", "segundo": 5},
        {"tema_pt": "sucesso", "busca_en": "success achievement", "segundo": 25},
        {"tema_pt": "pensamento", "busca_en": "thinking idea inspiration", "segundo": 45},
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Busca de imagens no Pexels
# ─────────────────────────────────────────────────────────────────────────────
def _buscar_imagem_pexels(termo: str) -> str | None:
    """
    Busca uma imagem quadrada (1:1) no Pexels para o tema dado.
    Retorna URL da imagem ou None se não encontrar.
    """
    if not PEXELS_KEY:
        print(f"  ⚠️  PEXELS_API_KEY não configurada. Pulando inserção para '{termo}'.")
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
            # Usa versão medium (640px) para performance
            return foto["src"].get("medium") or foto["src"]["original"]
    except Exception as e:
        print(f"  ⚠️  Pexels falhou para '{termo}': {e}")
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
    resultado = subprocess.run(cmd, capture_output=True, text=True)
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

    # ── 2. Baixa imagens do Pexels ────────────────────────────────────────────
    overlays_prontos = []   # [(segundo_inicio, clip_path)]

    for i, tema in enumerate(temas):
        termo_en  = tema.get("busca_en", "podcast conversation")
        segundo   = float(tema.get("segundo", i * 15 + 5))
        tema_pt   = tema.get("tema_pt", "")

        print(f"  🖼️  [{i+1}/{len(temas)}] Buscando imagem para: '{tema_pt}' ({termo_en})")

        url_img = _buscar_imagem_pexels(termo_en)
        if not url_img:
            continue

        img_path  = os.path.join(clips_dir, f"overlay_img_{i}.jpg")
        clip_path = os.path.join(clips_dir, f"overlay_clip_{i}.mp4")

        if not _baixar_imagem(url_img, img_path):
            continue

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
        # Input 0 é o video_base, Inputs 1+ são os overlays
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

        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if resultado.returncode != 0:
            print(f"  ⚠️  FFmpeg com overlays falhou. Copiando vídeo original...")
            print(f"  stderr: {resultado.stderr[-300:]}")
            shutil.copy(video_base, output_final)

    tamanho_mb = os.path.getsize(output_final) / (1024 * 1024)
    print(f"  ✅ Vídeo final com contexto: {output_final} ({tamanho_mb:.1f} MB)")
    return output_final


if __name__ == "__main__":
    import sys
    video   = sys.argv[1] if len(sys.argv) > 1 else "output/short_base.mp4"
    texto   = sys.argv[2] if len(sys.argv) > 2 else "Teste de contexto visual com IA"
    inserir_contexto(video, texto)
