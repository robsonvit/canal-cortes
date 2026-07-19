"""
pipeline.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Orquestrador principal do Canal Cortes.

Pipeline de 7 passos para criar Shorts automÃ¡ticos a partir dos
momentos mais assistidos de podcasts no YouTube.

Passos:
  1+2. Seleciona vÃ­deo e detecta picos via heatmap do YouTube
  2.5. Ajusta pontos de corte semanticamente via transcriÃ§Ã£o Groq Whisper
  3.   Baixa o trecho exato (com A/V sync normalizado)
  4.   Transcreve Ã¡udio com Groq Whisper (legendas SRT)
  5.   Monta Short 9:16 com face tracking
  6.   Insere contexto visual 1:1 (Pexels + IA)
  7.   Publica no YouTube com SEO por IA

Uso:
    python scripts/pipeline.py
    CANAL_URL=https://www.youtube.com/@Podpah/videos python scripts/pipeline.py
"""

import os
import sys
import json
import traceback

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
import traceback

ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")
sys.path.insert(0, ROOT_DIR)


def _titulo(passo: int, total: int, descricao: str):
    print(f"\n{'â”€'*65}")
    print(f" PASSO {passo}/{total}: {descricao}")
    print(f"{'â”€'*65}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "clips"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "tmp"), exist_ok=True)
    os.makedirs(os.path.join(ROOT_DIR, "data"), exist_ok=True)
    os.makedirs(os.path.join(ROOT_DIR, "assets", "musicas"), exist_ok=True)

    print("\n" + "â•" * 65)
    print("  ðŸŽ¬  CANAL CORTES â€” PIPELINE AUTOMÃTICO DE SHORTS")
    print("â•" * 65)

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # PASSO 1 & 2 â€” Selecionar vÃ­deo e detectar picos (com trava anti-membros)
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _titulo(1, 7, "Selecionando vÃ­deo de podcast para cortar e detectando picos...")
    from scripts.selecionar_video import selecionar_video, salvar_processado
    from scripts.detectar_pico import detectar_picos
    import json as _json

    video_info = None
    todos_picos = None

    for tentativa in range(5):
        video_info = selecionar_video()
        video_url  = video_info["url"]
        video_id   = video_info["id"]

        print(f"\nâœ… VÃ­deo selecionado: {video_info['titulo']}")
        print(f"   Canal: {video_info['canal']}")
        print(f"   URL  : {video_url}")

        print("\n  ðŸ“¡ Tentando detectar picos de replay via heatmap do YouTube...")
        try:
            todos_picos = detectar_picos(video_url)
            break  # Sucesso!
        except Exception as e:
            msg = str(e).lower()
            if "members-only" in msg or "private video" in msg or "members only" in msg:
                print(f"  âš ï¸  VÃ­deo restrito (Members Only/Privado) detectado!")
            elif "heatmap" in msg or "mapa de calor" in msg:
                print(f"  âš ï¸  VÃ­deo descartado por nÃ£o possuir mapa de calor (sem dados de retenÃ§Ã£o)!")
            else:
                print(f"  âš ï¸  Falha ao acessar vÃ­deo: {e}")
            print(f"  ðŸ”„ Marcando vÃ­deo como esgotado e tentando o prÃ³ximo (Tentativa {tentativa+1}/5)...")
            # Marca com pico_inicio_s negativo e total 0 para esgotÃ¡-lo
            salvar_processado(video_id, video_info, pico_inicio_s=-1.0, total_picos=0)
    else:
        print("\nâŒ ERRO CRÃTICO: NÃ£o foi possÃ­vel encontrar um vÃ­deo acessÃ­vel apÃ³s 5 tentativas.")
        sys.exit(1)

    # Descobre quais picos jÃ¡ foram usados para este vÃ­deo
    tracking_file = os.path.join(ROOT_DIR, "data", "videos_processados.json")
    try:
        with open(tracking_file, encoding="utf-8") as _f:
            _processados = _json.load(_f)
    except Exception:
        _processados = {}

    _entrada_video = _processados.get(video_id, {})
    _picos_ja_usados = _entrada_video.get("picos_usados", []) if isinstance(_entrada_video, dict) else []

    # Filtra picos ainda nÃ£o utilizados (compara inicio_s)
    picos_disponiveis = [
        p for p in todos_picos
        if p["inicio_s"] not in _picos_ja_usados
    ]

    if not picos_disponiveis:
        print(f"\nâš ï¸  Todos os {len(todos_picos)} picos deste vÃ­deo jÃ¡ foram usados. Encerrando.")
        sys.exit(0)

    # Usa o melhor pico disponÃ­vel (jÃ¡ estÃ£o ordenados por intensidade)
    pico = picos_disponiveis[0]

    print(f"\nâœ… Pico selecionado (rank {pico['rank']}/{len(todos_picos)}):")
    print(f"   InÃ­cio  : {pico['inicio_s']:.1f}s ({pico['inicio_s']/60:.1f} min)")
    print(f"   Fim     : {pico['fim_s']:.1f}s ({pico['fim_s']/60:.1f} min)")
    print(f"   DuraÃ§Ã£o : {pico['duracao_s']:.1f}s")
    print(f"   Picos disponÃ­veis restantes apÃ³s este: {len(picos_disponiveis) - 1}")
    if pico["heatmap_disponivel"]:
        print(f"   Intensidade: {pico['intensidade']:.2%} (dado real do YouTube)")
    else:
        print(f"   âš ï¸  Heatmap nÃ£o disponÃ­vel â€” usando posiÃ§Ã£o por divisÃ£o do vÃ­deo")

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # PASSO 2.5 â€” Ajustar pontos de corte semanticamente via transcriÃ§Ã£o
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _titulo(3, 7, "Ajustando corte semanticamente (transcriÃ§Ã£o Groq Whisper)...")
    from scripts.ajustar_corte_semantico import ajustar_corte_semantico

    inicio_s_raw = pico["inicio_s"]
    fim_s_raw    = pico["fim_s"]

    inicio_s_final, fim_s_final = ajustar_corte_semantico(
        video_url,
        inicio_s=inicio_s_raw,
        fim_s=fim_s_raw,
        output_dir=OUTPUT_DIR,
    )

    # Log do delta de ajuste
    delta_ini = inicio_s_final - inicio_s_raw
    delta_fim = fim_s_final - fim_s_raw
    print(f"\nâœ… Ajuste semÃ¢ntico concluÃ­do:")
    print(f"   InÃ­cio : {inicio_s_raw:.1f}s â†’ {inicio_s_final:.1f}s  (Î” {delta_ini:+.1f}s)")
    print(f"   Fim    : {fim_s_raw:.1f}s â†’ {fim_s_final:.1f}s  (Î” {delta_fim:+.1f}s)")
    print(f"   DuraÃ§Ã£o: {fim_s_final - inicio_s_final:.1f}s")

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # PASSO 3 â€” Baixar apenas o trecho do pico (tempos semanticamente ajustados)
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _titulo(4, 7, "Baixando trecho (pontos de corte semanticamente ajustados)...")
    from scripts.baixar_trecho import baixar_trecho

    video_path = baixar_trecho(
        video_url,
        inicio_s=inicio_s_final,
        fim_s=fim_s_final,
        output_dir=OUTPUT_DIR,
    )
    print(f"\nâœ… Trecho baixado: {video_path}")

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # PASSO 4 â€” Transcrever Ã¡udio com Groq Whisper
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _titulo(5, 7, "Transcrevendo Ã¡udio com Groq Whisper (whisper-large-v3-turbo)...")
    from scripts.transcrever import transcrever

    texto_transcricao, srt_path = transcrever(video_path, OUTPUT_DIR)

    palavras = len(texto_transcricao.split())
    print(f"\nâœ… TranscriÃ§Ã£o: {palavras} palavras")
    print(f"   SRT: {srt_path}")
    print(f"   Preview: {texto_transcricao[:120]}...")

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # PASSO 5 â€” Montar Short 9:16 com face tracking
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _titulo(6, 7, "Montando Short 9:16 com face tracking (MediaPipe)...")
    from scripts.montar_short import montar_short

    short_base = montar_short(
        video_path=video_path,
        srt_path=srt_path,
        output_dir=OUTPUT_DIR,
    )
    print(f"\nâœ… Short base pronto: {short_base}")

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # PASSO 6 â€” Inserir contexto visual 1:1 (Pexels + Groq AI)
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _titulo(7, 7, "Inserindo contexto visual 1:1 (Pexels + Groq AI)...")
    from scripts.inserir_contexto import inserir_contexto

    short_final = inserir_contexto(
        video_base=short_base,
        texto_transcricao=texto_transcricao,
        output_dir=OUTPUT_DIR,
    )
    print(f"\nâœ… Short final com contexto: {short_final}")

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # PASSO 7 â€” Upload para o YouTube com SEO otimizado por IA
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _titulo(7, 7, "Publicando Short no YouTube com SEO otimizado por IA...")

    # Prepara metadados completos para upload (inclui temas da IA para SEO)
    from scripts.inserir_contexto import _extrair_temas as _extrair_temas_seo
    print("  ðŸ§  Extraindo temas para enriquecer SEO do upload...")
    try:
        temas_seo = _extrair_temas_seo(texto_transcricao, OUTPUT_DIR)
    except Exception:
        temas_seo = []

    dados_upload = {
        **video_info,
        "titulo_video": pico.get("titulo_video", video_info["titulo"]),
        "texto_transcricao": texto_transcricao,
        "pico": pico,
        "temas": temas_seo,   # ðŸ‘ˆ temas da IA para o SEO de tags
    }

    if not os.environ.get("YOUTUBE_REFRESH_TOKEN"):
        print("âš ï¸  YOUTUBE_REFRESH_TOKEN nÃ£o configurado.")
        print("   Configure os secrets no GitHub e rode novamente.")
        print(f"\n   Short salvo localmente em: {short_final}")
        print(f"   Execute: python scripts/obter_refresh_token.py")
    else:
        from scripts.upload_youtube import upload_youtube
        youtube_id = upload_youtube(short_final, dados_upload)

        # Marca o PICO especÃ­fico como processado (nÃ£o bloqueia o vÃ­deo inteiro)
        salvar_processado(
            video_id,
            video_info,
            pico_inicio_s=pico["inicio_s"],
            total_picos=len(todos_picos),
        )

        picos_restantes = len(todos_picos) - len(_picos_ja_usados) - 1
        print(f"\nðŸŽ‰ PIPELINE CONCLUÃDO COM SUCESSO!")
        print(f"   ðŸ“± https://www.youtube.com/shorts/{youtube_id}")
        if picos_restantes > 0:
            print(f"   â³ Ainda hÃ¡ {picos_restantes} pico(s) nÃ£o usados neste vÃ­deo!")
        else:
            print(f"   âœ… Todos os picos deste vÃ­deo foram esgotados.")

    # â”€â”€ Salva metadados do processamento â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    metadados_path = os.path.join(OUTPUT_DIR, "metadados.json")
    with open(metadados_path, "w", encoding="utf-8") as f:
        json.dump({
            "video_info": video_info,
            "pico": pico,
            "transcricao_preview": texto_transcricao[:500],
        }, f, ensure_ascii=False, indent=2)

    # â”€â”€ Resumo final â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print("\n" + "â•" * 65)
    print("  ðŸ“ Arquivos gerados:")
    for nome in ["trecho_original.mp4", "legendas.srt", "short_base.mp4", "short_final.mp4", "metadados.json"]:
        caminho = os.path.join(OUTPUT_DIR, nome)
        if os.path.exists(caminho):
            tamanho = os.path.getsize(caminho)
            if nome.endswith(".mp4"):
                print(f"     {nome:<28} {tamanho/1024/1024:.1f} MB")
            else:
                print(f"     {nome:<28} {tamanho/1024:.0f} KB")
    print("â•" * 65 + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nâŒ ERRO CRÃTICO: {e}")
        traceback.print_exc()
        sys.exit(1)

