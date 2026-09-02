"""
test_qualidade.py
─────────────────
Script de teste: roda o download de um trecho real do YouTube
e valida que a trava de qualidade 1080p está funcionando.

NÃO faz upload para o YouTube.
NÃO altera videos_processados.json.

Uso:
    python test_qualidade.py
    python test_qualidade.py https://www.youtube.com/watch?v=VIDEO_ID 300 360
"""

import os
import sys
import subprocess

# Adiciona scripts/ ao path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "scripts"))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

OUTPUT_DIR = os.path.join(ROOT_DIR, "output_test")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "tmp"), exist_ok=True)

# URL de teste padrao: podcast longo com 1080p disponivel
URL_TESTE = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=VBzH5wOuTVc"
INICIO_S  = float(sys.argv[2]) if len(sys.argv) > 2 else 300.0  # 5min
FIM_S     = float(sys.argv[3]) if len(sys.argv) > 3 else 360.0  # 6min

print("\n" + "=" * 65)
print("  TESTE DE TRAVA DE QUALIDADE - Canal Cortes")
print("=" * 65)
print(f"\n  URL    : {URL_TESTE}")
print(f"  Trecho : {INICIO_S:.0f}s -> {FIM_S:.0f}s ({(FIM_S-INICIO_S):.0f}s de duracao)")
print(f"  Output : {OUTPUT_DIR}")
print()

from scripts.baixar_trecho import baixar_trecho, _verificar_resolucao

try:
    caminho = baixar_trecho(URL_TESTE, INICIO_S, FIM_S, output_dir=OUTPUT_DIR)

    print(f"\n{'-'*65}")
    print("  RESULTADO DO TESTE:")
    print(f"{'-'*65}")
    print(f"  Download concluido: {caminho}")

    tamanho_mb = os.path.getsize(caminho) / (1024 * 1024)
    print(f"  Tamanho: {tamanho_mb:.1f} MB")

    resolucao = _verificar_resolucao(caminho)
    if resolucao:
        largura, altura = resolucao
        status = "APROVADO" if altura >= 1080 else "REPROVADO - ABAIXO DE 1080p!"
        print(f"  Resolucao final: {largura}x{altura} -> {status}")
        if altura < 1080:
            print(f"\n  PROBLEMA: O video baixado esta em {altura}p!")
            sys.exit(1)
        else:
            print(f"\n  TRAVA DE QUALIDADE FUNCIONANDO CORRETAMENTE!")
            print(f"  O video esta em {altura}p >= 1080p")
    else:
        print("  Nao foi possivel verificar a resolucao via ffprobe")

    print(f"\n  Arquivo salvo em: {caminho}")
    print("  Nenhum upload foi feito no YouTube.")
    print("=" * 65 + "\n")

except RuntimeError as e:
    print(f"\n{'='*65}")
    print(str(e))
    print(f"{'='*65}")
    print("\n  Isso pode acontecer em ambiente local por bot-check do YouTube.")
    print("  No GitHub Actions com WARP + curl-cffi, as chances de sucesso sao maiores.")
    sys.exit(1)
except Exception as e:
    print(f"\n  Erro inesperado: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
