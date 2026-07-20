"""
pipeline.py
───────────
Orquestrador principal do Canal Cortes.

Pipeline de 7 passos para criar Shorts automáticos a partir dos
momentos mais assistidos de podcasts no YouTube.

Passos:
  1+2. Seleciona vídeo e detecta picos via heatmap do YouTube
  2.5. Ajusta pontos de corte semanticamente via transcrição Groq Whisper
  3.   Baixa o trecho exato (com A/V sync normalizado)
  4.   Transcreve áudio com Groq Whisper (legendas SRT)
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
    # PASSO 1 & 2 — Selecionar vídeo e detectar picos (com trava anti-membros)
    # ──────────────────────────────────────────────────────────────────────────
    _titulo(1, 7, "Selecionando vídeo de podcast para cortar e detectando picos...")
    from scripts.selecionar_video import selecionar_video, salvar_processado
    from scripts.detectar_pico import detectar_picos
    import json as _json

    video_info = None
    todos_picos = None

    for tentativa in range(5):
        video_info = selecionar_video()
        video_url  = video_info["url"]
        video_id   = video_info["id"]

        print(f"\n✅ Vídeo selecionado: {video_info['titulo']}")
        print(f"   Canal: {video_info['canal']}")
        print(f"   URL  : {video_url}")

        print("\n  📡 Tentando detectar picos de replay via heatmap do YouTube...")
        try:
            todos_picos = detectar_picos(video_url)
            break  # Sucesso!
        except Exception as e:
            msg = str(e).lower()
            if "members-only" in msg or "private video" in msg or "members only" in msg:
                print(f"  ⚠️  Vídeo restrito (Members Only/Privado) detectado!")
            elif "heatmap" in msg or "mapa de calor" in msg:
                print(f"  ⚠️  Vídeo descartado por não possuir mapa de calor (sem dados de retenção)!")
            else:
                print(f"  ⚠️  Falha ao acessar vídeo: {e}")
            print(f"  🔄 Marcando vídeo como esgotado e tentando o próximo (Tentativa {tentativa+1}/5)...")
            # Marca com pico_inicio_s negativo e total 0 para esgotá-lo
            salvar_processado(video_id, video_info, pico_inicio_s=-1.0, total_picos=0)
    else:
        print("\n❌ ERRO CRÍTICO: Não foi possível encontrar um vídeo acessível após 5 tentativas.")
        sys.exit(1)

    # Descobre quais picos já foram usados para este vídeo
    tracking_file = os.path.join(ROOT_DIR, "data", "videos_processados.json")
    try:
        with open(tracking_file, encoding="utf-8") as _f:
            _processados = _json.load(_f)
    except Exception:
        _processados = {}

    _entrada_video = _processados.get(video_id, {})
    _picos_ja_usados = _entrada_video.get("picos_usados", []) if isinstance(_entrada_video, dict) else []

    # Filtra picos ainda não utilizados (compara inicio_s)
    picos_disponiveis = [
        p for p in todos_picos
        if p["inicio_s"] not in _picos_ja_usados
    ]

    if not picos_disponiveis:
        print(f"\n⚠️  Todos os {len(todos_picos)} picos deste vídeo já foram usados. Encerrando.")
        sys.exit(0)

    # Usa o melhor pico disponível (já estão ordenados por intensidade)
    pico = picos_disponiveis[0]

    print(f"\n✅ Pico selecionado (rank {pico['rank']}/{len(todos_picos)}):")
    print(f"   Início  : {pico['inicio_s']:.1f}s ({pico['inicio_s']/60:.1f} min)")
    print(f"   Fim     : {pico['fim_s']:.1f}s ({pico['fim_s']/60:.1f} min)")
    print(f"   Duração : {pico['duracao_s']:.1f}s")
    print(f"   Picos disponíveis restantes após este: {len(picos_disponiveis) - 1}")
    if pico["heatmap_disponivel"]:
        print(f"   Intensidade: {pico['intensidade']:.2%} (dado real do YouTube)")
    else:
        print(f"   ⚠️  Heatmap não disponível — usando posição por divisão do vídeo")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 2.5 — Ajustar pontos de corte semanticamente via transcrição
    # ──────────────────────────────────────────────────────────────────────────
    _titulo(3, 7, "Ajustando corte semanticamente (transcrição Groq Whisper)...")
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
    print(f"\n✅ Ajuste semântico concluído:")
    print(f"   Início : {inicio_s_raw:.1f}s → {inicio_s_final:.1f}s  (Δ {delta_ini:+.1f}s)")
    print(f"   Fim    : {fim_s_raw:.1f}s → {fim_s_final:.1f}s  (Δ {delta_fim:+.1f}s)")
    print(f"   Duração: {fim_s_final - inicio_s_final:.1f}s")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 3 — Baixar apenas o trecho do pico (tempos semanticamente ajustados)
    # ──────────────────────────────────────────────────────────────────────────
    _titulo(4, 7, "Baixando trecho (pontos de corte semanticamente ajustados)...")
    from scripts.baixar_trecho import baixar_trecho

    video_path = baixar_trecho(
        video_url,
        inicio_s=inicio_s_final,
        fim_s=fim_s_final,
        output_dir=OUTPUT_DIR,
    )
    print(f"\n✅ Trecho baixado: {video_path}")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 4 — Transcrever áudio com Groq Whisper
    # ──────────────────────────────────────────────────────────────────────────
    _titulo(5, 7, "Transcrevendo áudio com Groq Whisper (whisper-large-v3-turbo)...")
    from scripts.transcrever import transcrever

    texto_transcricao, srt_path = transcrever(video_path, OUTPUT_DIR)

    palavras = len(texto_transcricao.split())
    print(f"\n✅ Transcrição: {palavras} palavras")
    print(f"   SRT: {srt_path}")
    print(f"   Preview: {texto_transcricao[:120]}...")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 5 — Montar Short 9:16 com face tracking
    # ──────────────────────────────────────────────────────────────────────────
    _titulo(6, 7, "Montando Short 9:16 com face tracking (MediaPipe)...")
    from scripts.montar_short import montar_short

    short_base = montar_short(
        video_path=video_path,
        srt_path=srt_path,
        output_dir=OUTPUT_DIR,
    )
    print(f"\n✅ Short base pronto: {short_base}")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 6 — Inserir contexto visual 1:1 (Pexels + Groq AI)
    # ──────────────────────────────────────────────────────────────────────────
    _titulo(7, 7, "Inserindo contexto visual 1:1 (Pexels + Groq AI)...")
    from scripts.inserir_contexto import inserir_contexto

    short_final = inserir_contexto(
        video_base=short_base,
        texto_transcricao=texto_transcricao,
        output_dir=OUTPUT_DIR,
    )
    print(f"\n✅ Short final com contexto: {short_final}")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 7 — Upload para o YouTube com SEO otimizado por IA
    # ──────────────────────────────────────────────────────────────────────────
    _titulo(7, 7, "Publicando Short no YouTube com SEO otimizado por IA...")

    # Prepara metadados completos para upload (inclui temas da IA para SEO)
    from scripts.inserir_contexto import _extrair_temas as _extrair_temas_seo
    print("  🧠 Extraindo temas para enriquecer SEO do upload...")
    try:
        temas_seo = _extrair_temas_seo(texto_transcricao, OUTPUT_DIR)
    except Exception:
        temas_seo = []

    dados_upload = {
        **video_info,
        "titulo_video": pico.get("titulo_video", video_info["titulo"]),
        "texto_transcricao": texto_transcricao,
        "pico": pico,
        "temas": temas_seo,   # 👈 temas da IA para o SEO de tags
    }

    if not os.environ.get("YOUTUBE_REFRESH_TOKEN"):
        print("⚠️  YOUTUBE_REFRESH_TOKEN não configurado.")
        print("   Configure os secrets no GitHub e rode novamente.")
        print(f"\n   Short salvo localmente em: {short_final}")
        print(f"   Execute: python scripts/obter_refresh_token.py")
    else:
        from scripts.upload_youtube import upload_youtube
        youtube_id = upload_youtube(short_final, dados_upload)

        # Marca o PICO específico como processado (não bloqueia o vídeo inteiro)
        salvar_processado(
            video_id,
            video_info,
            pico_inicio_s=pico["inicio_s"],
            total_picos=len(todos_picos),
        )

        picos_restantes = len(todos_picos) - len(_picos_ja_usados) - 1
        print(f"\n🎉 PIPELINE CONCLUÍDO COM SUCESSO!")
        print(f"   📱 https://www.youtube.com/shorts/{youtube_id}")
        if picos_restantes > 0:
            print(f"   ⏳ Ainda há {picos_restantes} pico(s) não usados neste vídeo!")
        else:
            print(f"   ✅ Todos os picos deste vídeo foram esgotados.")

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

