# ✂️ Short Machine – Máquina de Cortes Verticais

Gera **cortes verticais 9:16 (1080x1920)** prontos para **TikTok, Instagram Reels e YouTube Shorts** a partir de
um vídeo longo: podcast, entrevista, gameplay, trailer ou vídeo editado.

O pipeline é **local** (Apple Silicon) e **determinístico**: transcrição com Whisper, enquadramento automático
que segue quem fala ou a ação, legendas estilizadas, gancho de abertura, transição com efeito sonoro e um
`SEO.md` com título e descrição de cada corte. A curadoria (quais trechos cortar, ganchos, títulos, tradução e
SEO) é feita pelo **[Claude Code](https://claude.com/claude-code)**, que opera a CLI seguindo o
[`CLAUDE.md`](CLAUDE.md).

---

## ✨ Recursos

- **Transcrição local** com `mlx-whisper` (large-v3-turbo), com timestamps por palavra e detecção de idioma
- **Enquadramento inteligente**
  - `rosto`: segue quem está falando (atividade da boca via MediaPipe) e dá zoom em plano aberto
  - `movimento`: segue a ação em jogos e trailers (fluxo óptico sem o movimento da câmera, ignora o HUD, zoom dinâmico)
  - `centro`, `manual` (keyframes) e `ajustar` (quadro 16:9 inteiro sobre fundo desfocado)
- **Legendas** Montserrat ExtraBold, brancas com borda preta, uma linha por bloco, com correção de termos via glossário
- **Gancho viral obrigatório**: o trecho mais chamativo do corte vem antes, em P&B, com o badge "Ainda neste vídeo",
  seguido de uma transição de flash branco com whoosh
- **Card de título** animado (gaveta) para jogos e trailers
- **Safe area combinada** TikTok + Reels + Shorts (x 60–880, y 380–1500), para nada ficar embaixo dos botões
- **Áudio com copyright**: troca o áudio original por uma trilha da pasta `sound/` (fade e loudness -14 LUFS)
- **Ranking de ação** (áudio + movimento + ritmo de cortes) para achar os melhores momentos de gameplay e trailers
- **Vídeos em outro idioma**: legendas traduzidas para PT-BR, distribuídas no tempo da fala original
- **SEO.md** gerado automaticamente com nome do arquivo, título e descrição de cada corte

---

## 🧰 Stack

| Ferramenta | Uso |
|---|---|
| [ffmpeg](https://ffmpeg.org/) | leitura e encode (H.264 CRF 18 + AAC 192k), normalização de loudness |
| [mlx-whisper](https://github.com/ml-explore/mlx-examples) | transcrição local no Apple Silicon |
| [OpenCV](https://opencv.org/) + YuNet | detecção de rostos, cenas e movimento |
| [MediaPipe](https://ai.google.dev/edge/mediapipe) FaceLandmarker | detecção de fala (boca) |
| [Pillow](https://python-pillow.org/) | desenho de legendas, card, badge e marca (o ffmpeg do Homebrew não tem libass/drawtext) |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | download de vídeos |
| [ElevenLabs](https://elevenlabs.io/) *(opcional)* | geração do efeito sonoro de transição |
| [Claude Code](https://claude.com/claude-code) | escolha dos cortes, ganchos, títulos, tradução e SEO |

---

## 🚀 Instalação

Requisitos: **macOS com Apple Silicon**, [Homebrew](https://brew.sh/) e [uv](https://github.com/astral-sh/uv).

```bash
brew install ffmpeg uv

git clone <url-do-repositorio> short-machine
cd short-machine

uv venv --python 3.12 .venv
VIRTUAL_ENV=.venv uv pip install mlx-whisper opencv-python-headless mediapipe pillow numpy yt-dlp fonttools

mkdir -p entrada saida trabalho
chmod +x corte
```

Opcional, só para gerar novos efeitos sonoros:

```bash
echo "ELEVENLABS_API_KEY=sua_chave" > .env
```

> As fontes Montserrat, os modelos YuNet/MediaPipe, a safe area, o som de transição (`sfx/transicao.mp3`) e uma
> trilha de fundo (`sound/`) já vêm no repositório.

---

## 🎬 Uso com o Claude Code (recomendado)

1. Coloque o vídeo em `entrada/` (ou tenha a URL em mãos).
2. Abra o Claude Code na pasta do projeto.
3. Peça:

```
Gere os cortes do vídeo entrada/meu_podcast.mp4

- Tipo: podcast
- Contexto: episódio do podcast X com o convidado Y
- Foco dos cortes: opiniões polêmicas, histórias pessoais, dicas práticas
- Quantidade: 5 a 8 cortes
- Nomes/termos com grafia correta: "Claude Code", "Nubank"
```

O Claude transcreve, assiste ao vídeo pelas folhas de miniaturas, escolhe os trechos, escreve o `plano.json`,
confere os quadros e renderiza. Mais exemplos (trailer, gameplay) em [`PROMPT_EXEMPLO.md`](PROMPT_EXEMPLO.md).

---

## 🛠️ Uso manual (sem IA)

Escrevendo o `plano.json` à mão, a máquina roda sozinha:

```bash
./corte info meu_podcast                        # resolução, fps, duração
./corte transcrever meu_podcast                 # → trabalho/meu_podcast/transcricao.txt
./corte folha meu_podcast                       # folha de miniaturas para ver o vídeo
./corte plano meu_podcast --tipo podcast        # cria trabalho/meu_podcast/plano.json
# ... edite o plano.json ...
./corte quadros meu_podcast                     # quadros de teste com a safe area
./corte renderizar meu_podcast                  # → saida/meu_podcast/NN_nome.mp4 + SEO.md
```

### Comandos

| Comando | Descrição |
|---|---|
| `./corte baixar <url>` | baixa um vídeo para `entrada/` |
| `./corte info <video>` | resolução, fps, duração e pasta de trabalho |
| `./corte transcrever <video> [--idioma auto\|pt\|en]` | transcrição com timestamps por palavra |
| `./corte traduzir <video> [--cortes 1,2]` | exporta as frases para tradução (`traducao_NN.json`) |
| `./corte folha <video> [--inicio s --fim s --n 16]` | folha de miniaturas com timestamps |
| `./corte cenas <video>` | lista os cortes de cena |
| `./corte acao <video> [--janela 35 --top 12]` | ranking dos momentos de mais ação |
| `./corte sfx "<prompt>" [--nome transicao]` | gera um efeito sonoro na ElevenLabs |
| `./corte plano <video> --tipo <tipo>` | cria um `plano.json` modelo |
| `./corte quadros <video> [--cortes 1,2] [--t 12.5]` | quadros de teste já editados |
| `./corte renderizar <video> [--cortes 1,3] [--rapido] [--preview] [--forcar]` | renderiza os cortes |
| `./corte safearea` | regera as imagens de referência da safe area |

`<video>` pode ser o nome do arquivo em `entrada/`, uma parte única dele ou um caminho.

### Exemplo de `plano.json`

```json
{
  "video": "meu_podcast.mp4",
  "tipo": "podcast",
  "contexto": "Podcast X com convidado Y sobre IA",
  "glossario": { "cloud code": "Claude Code" },
  "copyright_audio": false,
  "cortes": [
    {
      "id": 1,
      "nome": "opiniao-polemica-sobre-ia",
      "inicio": 754.2,
      "fim": 842.9,
      "titulo": null,
      "enquadramento": "rosto",
      "gancho": { "inicio": 800.2, "fim": 807.9 },
      "post": {
        "titulo": "IA vai substituir programadores? A resposta surpreende 🤖",
        "descricao": "Convidado Y explica por que a IA ... Comente sua opinião!",
        "hashtags": ["#ia", "#programacao", "#podcast"]
      }
    }
  ]
}
```

A referência completa dos campos e dos modos de enquadramento está no [`CLAUDE.md`](CLAUDE.md#planjson).

---

## 📏 Regras de corte

- Duração de **45 a 120s** (gancho + corte). Com `copyright_audio`, **30 a 60s**.
- O corte começa no início da ideia e termina quando ela fecha. Início e fim são encaixados nas palavras automaticamente.
- Nunca corta no meio de uma risada ou reação: a máquina estende o fim enquanto houver reação sem fala.
- Jogos e trailers: **sem legenda das falas**, apenas o card de título.
- Todo texto entregue (legendas, títulos, SEO) é em **português do Brasil**.

---

## 📁 Estrutura

```
entrada/          vídeos originais
saida/<video>/    cortes prontos (NN_nome.mp4) + SEO.md
trabalho/<video>/ transcrição, plano.json, folhas, quadros de teste, cache de análise
maquina/          código (config.py concentra todas as constantes de estilo e regras)
assets/           fontes, modelos de visão e safe area
sound/            trilhas de fundo (vídeos com copyright)
sfx/              efeitos sonoros (transicao.mp3)
corte             atalho da CLI
CLAUDE.md         processo completo e regras (lido pelo Claude Code)
```

| Arquivo | Responsabilidade |
|---|---|
| `maquina/cortes.py` | CLI |
| `maquina/transcrever.py` | Whisper e utilidades de transcrição |
| `maquina/analise.py` | rostos, fala, cenas, movimento, energia do áudio (com cache) |
| `maquina/enquadramento.py` | modos de enquadramento |
| `maquina/texto.py` | legendas, card, badge e marca |
| `maquina/render.py` | composição, gancho, transição, áudio e encode |
| `maquina/config.py` | constantes globais (fontes, safe area, durações, zoom etc.) |

---

## ⚡ Desempenho (M1 Pro)

| Etapa | Velocidade aproximada |
|---|---|
| Transcrição | 4–10x tempo real |
| Análise de rostos | ~5x tempo real (com cache) |
| Renderização | ~2x tempo real por corte |

---

## ⚠️ Avisos

- Respeite os direitos autorais dos vídeos que você corta e publica.
- Ajustes para um vídeo específico vão **somente no `plano.json`**. Altere `maquina/` apenas para mudanças globais.
- Nunca versione o `.env`.
