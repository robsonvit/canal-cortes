"""
ajustar_corte_semantico.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Passo 2.5 do Pipeline Canal Cortes.

ApÃ³s detectar a zona quente via heatmap, refina os pontos de corte
usando a transcriÃ§Ã£o do trecho como guia semÃ¢ntico e um LLM para entender o contexto.

Problema que resolve:
  O heatmap define os limites do clipe matematicamente â€” sem saber o
  que estÃ¡ sendo dito. Isso faz o corte cair no meio de uma frase,
  gerando clipes que comeÃ§am sem contexto ou terminam sem conclusÃ£o.

SoluÃ§Ã£o:
  1. Expande o trecho detectado (atÃ© 90s antes e depois) para ter contexto
  2. Baixa apenas o Ã UDIO dessa janela expandida (baixo consumo)
  3. Transcreve com Groq Whisper (verbose_json com timestamps de segmentos)
  4. Envia os segmentos transcritos para um LLM da Groq (LLaMA 3.1) analisar
     semanticamente onde a histÃ³ria/piada comeÃ§a e termina.
  5. Retorna (inicio_ajustado, fim_ajustado) baseando-se na inteligÃªncia da IA.
"""

import os
import sys
import subprocess
import json

from groq import Groq

ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")

# Janela de expansÃ£o para busca de contexto (em segundos)
JANELA_EXPANSAO_S = 90.0   # Expande atÃ© 90s antes e depois do pico

def _formatar_tempo(segundos: float) -> str:
    """Converte segundos para formato HH:MM:SS.mmm usado pelo yt-dlp."""
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = segundos % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def _baixar_audio_expandido(
    video_url: str,
    inicio_s: float,
    fim_s: float,
    output_dir: str,
) -> tuple[str, float]:
    """
    Baixa apenas o Ã¡udio do trecho expandido para uso na transcriÃ§Ã£o.
    Usa qualidade mÃ­nima (bestaudio) para ser rÃ¡pido.

    Returns:
        (caminho_audio_mp3, offset_s) onde offset_s Ã© o inÃ­cio real do trecho
        baixado (para converter os timestamps do Whisper de volta ao tempo global)
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ytdlp_helper import args_base_ytdlp

    inicio_exp = max(0.0, inicio_s - JANELA_EXPANSAO_S)
    fim_exp    = fim_s + JANELA_EXPANSAO_S
    trecho_str = f"*{_formatar_tempo(inicio_exp)}-{_formatar_tempo(fim_exp)}"

    audio_dir  = os.path.join(output_dir, "tmp")
    os.makedirs(audio_dir, exist_ok=True)
    audio_path = os.path.join(audio_dir, "_semantico_audio.mp3")

    print(f"  ðŸŽ™ï¸   [SemÃ¢ntico] Baixando Ã¡udio expandido: {_formatar_tempo(inicio_exp)} â†’ {_formatar_tempo(fim_exp)}...")

    # Tenta com anti-bot completo primeiro
    cmds = [
        args_base_ytdlp([
            "--download-sections", trecho_str,
            "-f", "bestaudio/best",
            "-x",                              # Extrai apenas Ã¡udio
            "--audio-format", "mp3",
            "--audio-quality", "3",            # Qualidade mÃ©dia â€” suficiente para ASR
            "-o", audio_path,
            "--quiet",
        ]) + [video_url],
        [
            "yt-dlp",
            "--download-sections", trecho_str,
            "--extractor-args", "youtube:player_client=web,android,tv_downgraded",
            "-f", "bestaudio/best",
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "3",
            "-o", audio_path,
            "--no-playlist", "--no-warnings", "--quiet",
            video_url,
        ],
    ]

    for cmd in cmds:
        resultado = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
        # yt-dlp com -x pode gerar .mp3 diretamente ou com sufixo diferente
        arquivo_real = _encontrar_audio(audio_path)
        if resultado.returncode == 0 and arquivo_real:
            tamanho_mb = os.path.getsize(arquivo_real) / (1024 * 1024)
            print(f"  âœ… [SemÃ¢ntico] Ã udio baixado: {arquivo_real} ({tamanho_mb:.1f} MB)")
            return arquivo_real, inicio_exp
        print(f"  âš ï¸   [SemÃ¢ntico] Falhou: {resultado.stderr[-100:]}")

    raise RuntimeError(f"[SemÃ¢ntico] NÃ£o foi possÃ­vel baixar Ã¡udio expandido de {video_url}")


def _encontrar_audio(output_path: str) -> str | None:
    """Localiza o arquivo de Ã¡udio gerado pelo yt-dlp (ignora extensÃ£o)."""
    base = output_path.rsplit(".", 1)[0]
    for ext in [".mp3", ".m4a", ".opus", ".webm", ".ogg"]:
        cand = base + ext
        if os.path.exists(cand):
            return cand
    if os.path.exists(output_path):
        return output_path
    return None


def _transcrever_audio(audio_path: str, groq_key: str) -> list:
    """
    Transcreve o Ã¡udio via Groq Whisper (verbose_json).

    Returns:
        Lista de segmentos [{start, end, text}, ...]
        onde start/end sÃ£o relativos ao inÃ­cio do arquivo de Ã¡udio.
    """
    cliente = Groq(api_key=groq_key)

    # Whisper aceita arquivos atÃ© 25 MB. Para Ã¡udios maiores, corta o trecho
    tamanho_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"  ðŸ¤– [SemÃ¢ntico] Transcrevendo {tamanho_mb:.1f} MB com Groq Whisper...")

    with open(audio_path, "rb") as f:
        transcricao = cliente.audio.transcriptions.create(
            file=(os.path.basename(audio_path), f.read()),
            model="whisper-large-v3-turbo",
            response_format="verbose_json",
            language="pt",
        )

    if isinstance(transcricao, dict):
        segmentos = transcricao.get("segments", [])
    else:
        segmentos = getattr(transcricao, "segments", [])

    # Normaliza para dicts
    resultado = []
    for seg in segmentos:
        start = seg.start if hasattr(seg, "start") else seg["start"]
        end   = seg.end   if hasattr(seg, "end")   else seg["end"]
        text  = seg.text  if hasattr(seg, "text")  else seg["text"]
        resultado.append({"start": float(start), "end": float(end), "text": text.strip()})

    print(f"  âœ… [SemÃ¢ntico] {len(resultado)} segmentos transcritos")
    return resultado


def _analisar_contexto_com_llm(segmentos_abs: list, inicio_heatmap: float, fim_heatmap: float, groq_key: str) -> tuple[float, float]:
    """
    Envia a transcriÃ§Ã£o com tempos absolutos para o LLM analisar semanticamente
    o melhor ponto de inÃ­cio e fim da histÃ³ria.
    """
    if not segmentos_abs:
        return None, None
        
    texto_formatado = []
    for i, seg in enumerate(segmentos_abs):
        texto_formatado.append(f"ID {i} | Tempo: {seg['start']:.1f}s - {seg['end']:.1f}s | Texto: {seg['text']}")
    
    transcricao_texto = "\n".join(texto_formatado)
    
    prompt = f"""VocÃª Ã© um editor de vÃ­deos virais especialista em retenÃ§Ã£o de pÃºblico no TikTok e YouTube Shorts.
Sua tarefa Ã© ler a transcriÃ§Ã£o de um vÃ­deo e encontrar o MELHOR trecho contÃ­nuo que conte uma histÃ³ria, piada, ou ideia completa.

Os algoritmos do YouTube apontaram que o clÃ­max de interesse do pÃºblico ocorreu entre {inicio_heatmap:.1f}s e {fim_heatmap:.1f}s.
O seu corte final DEVE conter a informaÃ§Ã£o mais importante falada dentro desse intervalo, mas vocÃª deve recuar o inÃ­cio para pegar o contexto e avanÃ§ar o final para pegar a conclusÃ£o.

Regras Estritas:
1. O id_inicio deve ser o momento EXATO onde a pessoa comeÃ§a a introduzir o contexto daquela histÃ³ria/ideia.
2. O id_fim deve ser o momento EXATO onde o raciocÃ­nio Ã© plenamente concluÃ­do (uma reflexÃ£o, punchline ou encerramento da ideia). NUNCA corte no meio do assunto, durante uma respiraÃ§Ã£o no meio da histÃ³ria ou deixando a frase suspensa sem desfecho. O espectador precisa sentir que o vÃ­deo teve inÃ­cio, meio e fim!
3. NÃ£o inclua conversas paralelas irrelevantes se nÃ£o fizerem parte do clÃ­max.
4. Responda APENAS com um objeto JSON vÃ¡lido, contendo exatamente as chaves: "id_inicio", "id_fim" e "justificativa". NÃ£o adicione blocos de cÃ³digo ```json ao redor ou nenhum outro texto.

Exemplo de formato esperado:
{{"id_inicio": 4, "id_fim": 15, "justificativa": "O assunto principal comeÃ§a no ID 4 quando ele introduz a histÃ³ria, e a conclusÃ£o ocorre no ID 15."}}

TranscriÃ§Ã£o DisponÃ­vel:
{transcricao_texto}
"""
    
    print("  ðŸ§  [SemÃ¢ntico] Solicitando anÃ¡lise de contexto ao LLM (llama-3.1-70b-versatile)...")
    cliente = Groq(api_key=groq_key)
    
    try:
        resposta = cliente.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        conteudo = resposta.choices[0].message.content.strip()
        resultado = json.loads(conteudo)
        
        id_inicio = int(resultado["id_inicio"])
        id_fim = int(resultado["id_fim"])
        
        # Garante que os IDs estÃ£o no intervalo
        id_inicio = max(0, min(id_inicio, len(segmentos_abs) - 1))
        id_fim = max(0, min(id_fim, len(segmentos_abs) - 1))
        if id_inicio > id_fim:
            id_inicio, id_fim = id_fim, id_inicio
            
        print(f"  âœ… [SemÃ¢ntico] LLM justificou: {resultado.get('justificativa', '')}")
        
        return segmentos_abs[id_inicio]["start"], segmentos_abs[id_fim]["end"]
        
    except Exception as e:
        print(f"  âš ï¸   [SemÃ¢ntico] Falha na anÃ¡lise do LLM: {e}")
        return None, None


def ajustar_corte_semantico(
    video_url: str,
    inicio_s: float,
    fim_s: float,
    output_dir: str = OUTPUT_DIR,
) -> tuple[float, float]:
    """
    Refina os pontos de corte de um clipe usando IA SemÃ¢ntica (LLM) para entender contexto.

    Fluxo:
      1. Baixa Ã¡udio expandido (Â±90s alÃ©m do pico)
      2. Transcreve com Groq Whisper
      3. Envia os segmentos ao LLaMA para achar a histÃ³ria completa
      4. Retorna os tempos ajustados

    Args:
        video_url : URL do vÃ­deo original
        inicio_s  : ponto de inÃ­cio do heatmap (segundos absolutos no vÃ­deo)
        fim_s     : ponto de fim do heatmap (segundos absolutos no vÃ­deo)
        output_dir: pasta de trabalho

    Returns:
        (inicio_ajustado_s, fim_ajustado_s)
        Se o ajuste falhar, retorna os valores originais.
    """
    print(f"\n  ðŸ”  [Ajuste SemÃ¢ntico] Refinando corte {inicio_s:.0f}s â†’ {fim_s:.0f}s com InteligÃªncia Artificial...")

    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        print("  âš ï¸   [SemÃ¢ntico] GROQ_API_KEY nÃ£o configurado. Usando tempos originais.")
        return inicio_s, fim_s

    try:
        # 1. Baixa Ã¡udio expandido
        audio_path, offset_s = _baixar_audio_expandido(video_url, inicio_s, fim_s, output_dir)

        # 2. Transcreve
        segmentos = _transcrever_audio(audio_path, groq_key)

        # Remove arquivo de Ã¡udio temporÃ¡rio
        if os.path.exists(audio_path):
            os.remove(audio_path)

        if not segmentos:
            print("  âš ï¸   [SemÃ¢ntico] Sem segmentos na transcriÃ§Ã£o. Usando tempos originais.")
            return inicio_s, fim_s

        # Converte timestamps relativos (ao inÃ­cio do arquivo de Ã¡udio) para absolutos
        segs_abs = [
            {
                "start": s["start"] + offset_s,
                "end":   s["end"]   + offset_s,
                "text":  s["text"],
            }
            for s in segmentos
        ]

        # 3. Analisa o Contexto com LLM
        inicio_ajustado, fim_ajustado = _analisar_contexto_com_llm(segs_abs, inicio_s, fim_s, groq_key)
        
        if inicio_ajustado is None or fim_ajustado is None:
            print("  âš ï¸   [SemÃ¢ntico] LLM nÃ£o retornou pontos vÃ¡lidos. Usando tempos originais.")
            return inicio_s, fim_s

        if inicio_ajustado >= fim_ajustado:
            print("  âš ï¸   [SemÃ¢ntico] Ajuste invÃ¡lido (inÃ­cio >= fim). Usando originais.")
            return inicio_s, fim_s

        duracao = fim_ajustado - inicio_ajustado
        print(f"  ðŸ“  [SemÃ¢ntico] DuraÃ§Ã£o final: {duracao:.1f}s ({duracao/60:.1f} min)")
        print(f"     Ajuste: InÃ­cio {inicio_s:.1f}s â†’ {inicio_ajustado:.1f}s | Fim {fim_s:.1f}s â†’ {fim_ajustado:.1f}s")

        return inicio_ajustado, fim_ajustado

    except Exception as e:
        print(f"  âš ï¸   [SemÃ¢ntico] Falha crÃ­tica no ajuste semÃ¢ntico: {e}. Usando tempos originais.")
        return inicio_s, fim_s


if __name__ == "__main__":
    # Teste rÃ¡pido
    url      = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=example"
    inicio_s = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
    fim_s    = float(sys.argv[3]) if len(sys.argv) > 3 else 700.0
    i, f = ajustar_corte_semantico(url, inicio_s, fim_s)
    print(f"\nResultado final: {i:.1f}s â†’ {f:.1f}s  (duraÃ§Ã£o: {f - i:.1f}s)")
