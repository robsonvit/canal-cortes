# 🎬 Canal Cortes — Pipeline Automático de Shorts de Podcast

Automação que monitora os principais podcasts brasileiros no YouTube, detecta os **momentos mais assistidos** (pico de replay), cria Shorts em 9:16 com **rastreio de rosto**, **inserções visuais contextuais 1:1** e **legendas automáticas**, e publica automaticamente no canal do YouTube.

---

## 🎯 Como Funciona (7 Passos)

```
1. 📡 Seleciona vídeo → Canal mais recente não processado
2. 📊 Detecta pico   → Heatmap do YouTube via yt-dlp
3. ⬇️  Baixa trecho  → yt-dlp --download-sections (só o pico)
4. 🎙️  Transcreve    → Groq Whisper → SRT com timestamps
5. 👤 Face Tracking  → MediaPipe + FFmpeg → 9:16 dinâmico
6. 🖼️  Contexto 1:1  → Groq AI + Pexels → overlays + música
7. 📤 Upload         → YouTube Data API v3 (OAuth2)
```

---

## 📡 Canais Monitorados

Configurados em `data/canais.json`:
- **Podpah** — `@Podpah`
- **Flow Podcast** — `@flowpodcast`
- **Inteligência Ltda** — `@inteligencialtda`

> Para adicionar mais canais, edite `data/canais.json` e adicione novos objetos com `nome`, `url` e `ativo: true`.

---

## ⚙️ Configuração

### 1. Secrets no GitHub
Vá em **Settings → Secrets and variables → Actions** e adicione:

| Secret | Descrição |
|--------|-----------|
| `GROQ_API_KEY` | Chave da API Groq (Whisper + LLM) |
| `PEXELS_API_KEY` | Chave da API Pexels (imagens contextuais) |
| `YOUTUBE_CLIENT_ID` | ID do cliente OAuth2 do Google |
| `YOUTUBE_CLIENT_SECRET` | Secret do cliente OAuth2 |
| `YOUTUBE_REFRESH_TOKEN` | Refresh token gerado localmente |

### 2. Obter Refresh Token do YouTube

Execute **uma vez** na sua máquina local:

```bash
# Instale as dependências
pip install -r requirements.txt

# Coloque o client_secret.json na raiz do projeto
# (baixado do Google Cloud Console)

# Execute o helper
python scripts/obter_refresh_token.py
```

O script abrirá o browser, você faz login e ele exibe os tokens para configurar nos secrets.

---

## 🚀 Executar

### Via GitHub Actions (automático)
- **Schedule:** Todo dia às 10h Brasília (UTC-3)
- **Manual:** Actions → "🎬 Gerar Short de Podcast" → Run workflow

### Localmente
```bash
# Clone o projeto
git clone https://github.com/robsonvit/canal-cortes.git
cd canal-cortes

# Configure o .env
cp .env.example .env
# Edite .env com suas chaves

# Instale dependências
pip install -r requirements.txt

# Execute
python scripts/pipeline.py

# Forçar canal específico:
CANAL_URL=https://www.youtube.com/@Podpah/videos python scripts/pipeline.py
```

---

## 📁 Estrutura

```
canal-cortes/
├── .github/workflows/main.yml   # GitHub Actions
├── data/
│   ├── canais.json              # Canais monitorados (editável)
│   └── videos_processados.json  # Tracking de vídeos já cortados
├── scripts/
│   ├── pipeline.py              # Orquestrador principal
│   ├── selecionar_video.py      # Passo 1: Escolha do vídeo
│   ├── detectar_pico.py         # Passo 2: Heatmap do YouTube
│   ├── baixar_trecho.py         # Passo 3: yt-dlp sections
│   ├── transcrever.py           # Passo 4: Groq Whisper
│   ├── montar_short.py          # Passo 5: Face tracking + 9:16
│   ├── inserir_contexto.py      # Passo 6: Pexels + IA + música
│   ├── baixar_musica.py         # Música royalty-free
│   ├── upload_youtube.py        # Passo 7: YouTube API
│   └── obter_refresh_token.py   # Helper: gerar token OAuth2
├── requirements.txt
└── README.md
```

---

## 🛠️ Tecnologias

| Tecnologia | Uso |
|-----------|-----|
| `yt-dlp` | Download de vídeos + extração de heatmap |
| `Groq Whisper` | Transcrição automática em PT-BR |
| `Groq LLM` | Análise contextual da transcrição |
| `MediaPipe` | Detecção de rosto (face tracking) |
| `FFmpeg` | Crop 9:16, legendas, overlays, mixagem |
| `Pexels API` | Imagens contextuais 1:1 |
| `YouTube Data API v3` | Upload e publicação dos Shorts |
| `GitHub Actions` | Automação diária gratuita |

---

## 📝 Licença

Uso pessoal. Créditos aos canais originais nas descrições dos Shorts.
