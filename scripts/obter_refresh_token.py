"""
obter_refresh_token.py
──────────────────────
Script auxiliar para gerar o refresh_token OAuth2 do YouTube.

Execute UMA VEZ localmente para obter o token que será salvo
como secret YOUTUBE_REFRESH_TOKEN no GitHub.

Pré-requisitos:
  1. Crie um projeto no Google Cloud Console
  2. Habilite YouTube Data API v3
  3. Crie credenciais OAuth 2.0 (tipo: Desktop App)
  4. Baixe o client_secret.json e coloque na raiz do projeto

Uso:
  python scripts/obter_refresh_token.py

O script abrirá o browser para autenticação e salvará:
  - refresh_token_PRIVADO.json (NÃO COMMITE ESTE ARQUIVO)
"""

import os
import json

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CLIENT_SECRET_FILE = os.path.join(ROOT_DIR, "client_secret.json")
TOKEN_OUTPUT_FILE  = os.path.join(ROOT_DIR, "refresh_token_PRIVADO.json")

SCOPES = [
    "https://www.googleapis.com/auth/youtube",          # Gerenciar playlists
    "https://www.googleapis.com/auth/youtube.upload",   # Upload de vídeos
]


def obter_token():
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not os.path.exists(CLIENT_SECRET_FILE):
        print("❌ Arquivo client_secret.json não encontrado!")
        print(f"   Esperado em: {CLIENT_SECRET_FILE}")
        print("\n   Passos:")
        print("   1. Acesse: https://console.cloud.google.com/")
        print("   2. Crie projeto → Ative YouTube Data API v3")
        print("   3. Credenciais → Criar credencial → ID do cliente OAuth")
        print("   4. Tipo: App para computador → Baixar JSON")
        print("   5. Renomeie para client_secret.json e coloque na raiz")
        return

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    token_data = {
        "refresh_token":  creds.refresh_token,
        "client_id":      creds.client_id,
        "client_secret":  creds.client_secret,
    }

    with open(TOKEN_OUTPUT_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

    print("\n" + "═" * 60)
    print("  ✅ TOKEN OBTIDO COM SUCESSO!")
    print("═" * 60)
    print(f"\n  Arquivo salvo: {TOKEN_OUTPUT_FILE}")
    print(f"\n  Scopes autorizados:")
    print(f"    • youtube        — gerenciar playlists")
    print(f"    • youtube.upload — fazer upload de vídeos")
    print(f"\n  Agora configure estes secrets no GitHub:")
    print(f"  (Settings → Secrets and variables → Actions → New repository secret)")
    print()
    print(f"  YOUTUBE_REFRESH_TOKEN = {creds.refresh_token}")
    print(f"  YOUTUBE_CLIENT_ID     = {creds.client_id}")
    print(f"  YOUTUBE_CLIENT_SECRET = {creds.client_secret}")
    print()
    print("  ⚠️  NÃO commite o arquivo refresh_token_PRIVADO.json!")
    print("=" * 60)


if __name__ == "__main__":
    obter_token()

