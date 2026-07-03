"""
pipeline.py
───────────
Orquestrador principal do Canal Cortes.

Pipeline de 7 passos para criar Shorts automáticos a partir dos
momentos mais assistidos de podcasts no YouTube.

Uso:
    python scripts/pipeline.py
    CANAL_URL=https://www.youtube.com/@Podpah/videos python scripts/pipeline.py
"""

import os
import sys
import json
import traceback

ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")
sys.path.insert(0, ROOT_DIR)


def _titulo(passo: int, total: int, descricao: str):
    print(f"\n{'─'*65}")
    print(f" PASSO {passo}/{total}: {descricao}")
    print(f"{'─'*65}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "clips"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "tmp"), exist_ok=True)
    os.makedirs(os.path.join(ROOT_DIR, "data"), exist_ok=True)
    os.makedirs(os.path.join(ROOT_DIR, "assets", "musicas"), exist_ok=True)

    print("\n" + "═" * 65)
    print("  🎬  CANAL CORTES — PIPELINE AUTOMÁTICO DE SHORTS")
    print("═" * 65)

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 1 — Selecionar vídeo de podcast para cortar
    # ──────────────────────────────────────────────────────────────────────────
    _titulo(1, 7, "Selecionando vídeo de podcast para cortar...")
    from scripts.selecionar_video import selecionar_video, salvar_processado

    video_info = selecionar_video()
    video_url  = video_info["url"]
    video_id   = video_info["id"]

    print(f"\n✅ Vídeo selecionado: {video_info['titulo']}")
    print(f"   Canal: {video_info['canal']}")
    print(f"   URL  : {video_url}")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 2 — Detectar pico de replay (heatmap)
    # ──────────────────────────────────────────────────────────────────────────
    _titulo(2, 7, "Detectando pico de replay via heatmap do YouTube...")
    from scripts.detectar_pico import detectar_pico

    pico = detectar_pico(video_url)

    print(f"\n✅ Pico detectado:")
    print(f"   Início  : {pico['inicio_s']:.1f}s ({pico['inicio_s']/60:.1f} min)")
    print(f"   Fim     : {pico['fim_s']:.1f}s ({pico['fim_s']/60:.1f} min)")
    print(f"   Duração : {pico['duracao_s']:.1f}s")
    if pico["heatmap_disponivel"]:
        print(f"   Intensidade: {pico['intensidade']:.2%} (dado real do YouTube)")
    else:
        print(f"   ⚠️  Heatmap não disponível — usando terço médio do vídeo")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 3 — Baixar apenas o trecho do pico
    # ──────────────────────────────────────────────────────────────────────────
    _titulo(3, 7, "Baixando trecho do pico de replay via yt-dlp...")
    from scripts.baixar_trecho import baixar_trecho

    video_path = baixar_trecho(
        video_url,
        inicio_s=pico["inicio_s"],
        fim_s=pico["fim_s"],
        output_dir=OUTPUT_DIR,
    )
    print(f"\n✅ Trecho baixado: {video_path}")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 4 — Transcrever áudio com Groq Whisper
    # ──────────────────────────────────────────────────────────────────────────
    _titulo(4, 7, "Transcrevendo áudio com Groq Whisper (whisper-large-v3-turbo)...")
    from scripts.transcrever import transcrever

    texto_transcricao, srt_path = transcrever(video_path, OUTPUT_DIR)

    palavras = len(texto_transcricao.split())
    print(f"\n✅ Transcrição: {palavras} palavras")
    print(f"   SRT: {srt_path}")
    print(f"   Preview: {texto_transcricao[:120]}...")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 5 — Montar Short 9:16 com face tracking
    # ──────────────────────────────────────────────────────────────────────────
    _titulo(5, 7, "Montando Short 9:16 com face tracking (MediaPipe)...")
    from scripts.montar_short import montar_short

    short_base = montar_short(
        video_path=video_path,
        srt_path=srt_path,
        output_dir=OUTPUT_DIR,
    )
    print(f"\n✅ Short base pronto: {short_base}")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 6 — Inserir contexto visual 1:1 + música de atenção
    # ──────────────────────────────────────────────────────────────────────────
    _titulo(6, 7, "Inserindo contexto visual 1:1 (Pexels + Groq AI) e música...")
    from scripts.baixar_musica import baixar_musica
    from scripts.inserir_contexto import inserir_contexto

    musica_path = baixar_musica()
    print(f"  🎵 Música: {musica_path}")

    short_final = inserir_contexto(
        video_base=short_base,
        texto_transcricao=texto_transcricao,
        musica_path=musica_path,
        output_dir=OUTPUT_DIR,
    )
    print(f"\n✅ Short final com contexto: {short_final}")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 7 — Upload para o YouTube
    # ──────────────────────────────────────────────────────────────────────────
    _titulo(7, 7, "Publicando Short no YouTube...")

    # Prepara metadados completos para upload
    dados_upload = {
        **video_info,
        "titulo_video": pico.get("titulo_video", video_info["titulo"]),
        "texto_transcricao": texto_transcricao,
        "pico": pico,
    }

    if not os.environ.get("YOUTUBE_REFRESH_TOKEN"):
        print("⚠️  YOUTUBE_REFRESH_TOKEN não configurado.")
        print("   Configure os secrets no GitHub e rode novamente.")
        print(f"\n   Short salvo localmente em: {short_final}")
        print(f"   Execute: python scripts/obter_refresh_token.py")
    else:
        from scripts.upload_youtube import upload_youtube
        youtube_id = upload_youtube(short_final, dados_upload)

        # Marca vídeo como processado APÓS upload bem-sucedido
        salvar_processado(video_id, video_info)

        print(f"\n🎉 PIPELINE CONCLUÍDO COM SUCESSO!")
        print(f"   📱 https://www.youtube.com/shorts/{youtube_id}")

    # ── Salva metadados do processamento ──────────────────────────────────────
    metadados_path = os.path.join(OUTPUT_DIR, "metadados.json")
    with open(metadados_path, "w", encoding="utf-8") as f:
        json.dump({
            "video_info": video_info,
            "pico": pico,
            "transcricao_preview": texto_transcricao[:500],
        }, f, ensure_ascii=False, indent=2)

    # ── Resumo final ──────────────────────────────────────────────────────────
    print("\n" + "═" * 65)
    print("  📁 Arquivos gerados:")
    for nome in ["trecho_original.mp4", "legendas.srt", "short_base.mp4", "short_final.mp4", "metadados.json"]:
        caminho = os.path.join(OUTPUT_DIR, nome)
        if os.path.exists(caminho):
            tamanho = os.path.getsize(caminho)
            if nome.endswith(".mp4"):
                print(f"     {nome:<28} {tamanho/1024/1024:.1f} MB")
            else:
                print(f"     {nome:<28} {tamanho/1024:.0f} KB")
    print("═" * 65 + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERRO CRÍTICO: {e}")
        traceback.print_exc()
        sys.exit(1)
