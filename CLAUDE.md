# Máquina de Cortes – Vídeos Verticais

Gera cortes verticais (9:16, **1080x1920**) para TikTok, Instagram Reels e YouTube Shorts a partir
de um vídeo original colocado em `entrada/`. Este arquivo descreve o processo completo: com um prompt
simples (veja `PROMPT_EXEMPLO.md`) o Claude deve conseguir executar tudo.

## ⚠️ Regra de ouro
**Não altere a edição da máquina** (código em `maquina/`, `maquina/config.py`, fontes, safe area,
estilo de legenda/título) para atender a um vídeo específico. Ajustes por vídeo são feitos **somente
no `plano.json`** daquele vídeo. Mudar a máquina só quando for **EXPLICITAMENTE** pedido
(ex.: "a máquina não está gerando legendas em tal cenário, ajuste"). Ao alterar, atualize este arquivo.

## Estrutura
```
entrada/                  vídeos originais (coloque aqui)
sound/                    trilhas de fundo (mp3/wav/m4a) usadas quando o áudio tem copyright
sfx/                      efeitos sonoros reaproveitáveis (sfx/transicao.mp3 = som da emenda gancho→corte; .txt = prompt usado)
.env                      ELEVENLABS_API_KEY=... (não versionar)
saida/<video>/            cortes prontos (NN_nome.mp4) + SEO.md (arquivo, título SEO e descrição de cada corte)
trabalho/<video>/         transcricao.txt/.json, plano.json, folhas de miniaturas, quadros de teste, cache de análise
maquina/                  código (config.py = TODAS as constantes de estilo/safe area/regras)
assets/fonts/             Montserrat Bold/ExtraBold/Black
assets/modelos/           YuNet (detecção de rostos) + MediaPipe FaceLandmarker (boca/fala)
assets/safearea/          safearea_referencia.png, safearea_overlay.png, safearea.json
corte                     atalho da CLI (./corte <comando>)
.venv/                    Python 3.12 (mlx-whisper, opencv, mediapipe, pillow, yt-dlp)
```
Dependências de sistema: `ffmpeg` (Homebrew), `uv`. Recriar ambiente se necessário:
`uv venv --python 3.12 .venv && VIRTUAL_ENV=.venv uv pip install mlx-whisper opencv-python-headless mediapipe pillow numpy yt-dlp fonttools`.
O ffmpeg do Homebrew **não tem libass/drawtext**: legendas e títulos são desenhados em Python (Pillow).

## Safe area (combinada TikTok + Reels + Shorts)
Retângulo seguro em 1080x1920: **x 60–880, y 380–1500** (margens: topo 380, base 420, esq 60, dir 200).
- YouTube Shorts: topo 380 / base 380 / esq 60 / dir 120
- Instagram Reels: topo ~230 / base ~290 / dir ~200 na metade inferior (botões)
- TikTok: topo ~130 / base ~370 / esq 60 / dir ~140
Centro horizontal do texto = 470 (centro da safe area). Legendas e títulos ficam com a **base em y=1500**
(limite inferior da safe area). Referência visual: `assets/safearea/safearea_referencia.png`.
Regerar imagens: `./corte safearea`.

## Ferramentas (CLI `./corte`)
| Comando | O que faz |
|---|---|
| `./corte baixar <url>` | baixa vídeo (yt-dlp) para `entrada/` |
| `./corte info <video>` | resolução, fps, duração, pasta de trabalho |
| `./corte transcrever <video> [--idioma auto\|pt\|en...]` | Whisper large-v3-turbo (MLX) c/ timestamps por palavra e **detecção automática de idioma** (padrão `auto`) → `trabalho/<video>/transcricao.txt` |
| `./corte traduzir <video> [--cortes 1,2]` | vídeo fora do português: exporta as frases de cada corte para `trabalho/<video>/traducao_NN.json` (o Claude preenche `pt`) |
| `./corte folha <video> [--inicio s --fim s --n 16]` | folha de miniaturas c/ timestamps (para **ver** o vídeo com Read) |
| `./corte cenas <video>` | lista cortes de cena (trailers/vídeos editados) |
| `./corte acao <video> [--janela 35 --top 12]` | ranking dos **momentos de mais ação** (barulho do áudio original + movimento real dos objetos + ritmo de cortes) → `trabalho/<video>/acao.txt` |
| `./corte sfx "<prompt>" [--nome transicao --duracao 1.2]` | gera efeito sonoro na **ElevenLabs** (chave em `.env`) e salva em `sfx/<nome>.mp3` |
| `./corte plano <video> --tipo podcast\|entrevista\|jogo\|trailer\|editado\|outro` | cria `plano.json` modelo |
| `./corte quadros <video> [--cortes 1,2] [--t 12.5,40]` | quadros de teste já editados, com safe area desenhada → `trabalho/<video>/quadros/cNN_folha.jpg` |
| `./corte renderizar <video> [--cortes 1,3] [--rapido] [--preview] [--forcar]` | renderiza os cortes → `saida/<video>/` |

`<video>` pode ser o nome do arquivo em `entrada/` (ou parte única dele) ou caminho.
`--preview` desenha a safe area no vídeo (só p/ conferência); `--forcar` ignora a validação 45–120s.

## Processo passo a passo (siga sempre)
1. **Identificar** o vídeo em `entrada/` (ou baixar a URL) → `./corte info`.
2. **Transcrever** → `./corte transcrever <video>` e **ler** `trabalho/<video>/transcricao.txt`
   (formato: `[mm:ss -> mm:ss] (ini-fim em segundos) texto`). Vídeo sem fala relevante (gameplay/trailer sem
   diálogo) também transcreve, mas pode ser vazio.
3. **Ver o vídeo** → `./corte folha <video>` (e com `--inicio/--fim` para trechos) e abrir a imagem.
   Identificar o tipo: podcast fechado (close-ups), podcast aberto (mesa inteira), jogo, trailer, editado (box de edição).
4. **Trailers de filmes/jogos**: pesquisar na internet (WebSearch) os assuntos mais comentados sobre o
   trailer/jogo/filme para escolher ângulos virais. `./corte cenas <video>` ajuda a achar as cenas.
5. **Escolher os cortes** (regras abaixo) e escrever `trabalho/<video>/plano.json` (`./corte plano` cria o modelo).
5b. **Vídeo em outro idioma** (o `transcrever` avisa; idioma fica em `transcricao.json`): rodar
   `./corte traduzir <video>`, abrir cada `trabalho/<video>/traducao_NN.json` e preencher **todos** os campos
   `"pt"` com a tradução em português do Brasil (natural, curta, estilo legenda; nomes próprios mantidos;
   não alterar `original`, `i`, `f`). A máquina distribui cada frase traduzida no tempo da frase original.
   Sem tradução completa, `quadros`/`renderizar` param com erro. Se o corte mudar de trecho, rode `traduzir`
   de novo (traduções já feitas são preservadas).
6. **Conferir** → `./corte quadros <video>` e abrir `trabalho/<video>/quadros/cNN_folha.jpg`: o assunto
   deve estar dentro do retângulo verde, legendas/título legíveis na base da safe area. Ajustar o
   `enquadramento` no plano se necessário.
7. **Renderizar** → `./corte renderizar <video>`. Saída em `saida/<video>/` + **`SEO.md`** gerado a partir do
   campo `post` de cada corte (obrigatório preencher): **nome do arquivo**, **título com bom SEO** e **descrição**.
   - Título SEO (PT-BR, até ~70 caracteres): palavra-chave principal no início (ex.: "GTA 6"), gancho de
     curiosidade/benefício, sem clickbait enganoso; pode ter 1 emoji.
   - Descrição (PT-BR, 2–4 frases): resume o corte com as palavras-chave e variações de busca (ex.: "GTA 6",
     "GTA VI", "gameplay"), termina com chamada para ação; `hashtags` (3–6) vão ao final da descrição.
8. **Responder** ao usuário com a lista de cortes (arquivo, trecho, por que foi escolhido).

## Regras de corte
1. Objeto em evidência dentro da safe area: podcast → quem fala; jogo → a ação; vídeo editado → o box de edição.
2. **Não cortar com gente rindo/reagindo**: se o trecho termina numa piada/punchline, o fim vai **depois** da
   risada ou reação (escolha o `fim` depois da reação ou da frase que fecha a piada). A máquina também
   estende o fim automaticamente enquanto houver som de reação sem fala (até 8s, sem invadir a próxima fala;
   no gancho até 1s) – `"reacao_max": s` no corte/gancho muda o limite.
   **Mínimo 45s**, nunca interromper o assunto no meio (podcast: começar no início da ideia/pergunta e
   terminar quando a ideia fecha). A máquina encaixa início/fim nas palavras automaticamente (`ajustar_fala`).
3. **Máximo 120s** (a renderização recusa fora de 45–120s sem `--forcar`).
4. **Jogos e trailers: sem legenda das falas**, apenas um **título** em evidência durante todo o vídeo
   (ex.: "GTA VI: REALISMO SURREAL!", "DR. DESTINO CAPTURA WANDA"). O título é exibido como **card** (ver "Card do título").
5. Vídeos longos (+5min): criar **vários cortes** com todas as partes interessantes.
6. Ler a transcrição antes e escolher o que pode viralizar: opiniões polêmicas, relatos de acontecimentos,
   histórias pessoais, assuntos relevantes/atuais, frases de efeito, conselhos práticos.
7. Trailers de filmes/jogos: pesquisar na internet os assuntos mais falados para criar cortes relevantes.
8. Trailers curtos (-5min): pode criar **vários cortes com as mesmas imagens e títulos diferentes**
   (ex. GTA VI: realismo gráfico / lugar real retratado de forma surreal / possibilidades de gameplay).
   Se o trailer tiver menos de 45s, use `--forcar` e avise o usuário.
9. Podcast em plano aberto: foco em **quem está falando** (modo `rosto` já faz zoom no falante), não na mesa inteira, salvo se necessário.
10. **Idioma: todo texto entregue é em Português do Brasil**, mesmo que o vídeo seja em inglês ou outro idioma:
   legendas (via tradução, passo 5b), títulos/cards na tela, `post.titulo`, `post.descricao`, hashtags e nomes
   dos arquivos. O áudio original é mantido (exceto com copyright – regra 11).
11. **Áudio com copyright** (jogos, trailers, filmes, músicas – ou quando o usuário avisar): usar
   `"copyright_audio": true` no plano (geral ou por corte). A máquina **remove o áudio original** e coloca
   uma trilha da pasta `sound/` (fade in 0,4s / fade out 1,5s, loop se precisar, -14 LUFS).
   `"musica": "arquivo.mp3"` escolhe a faixa (padrão: rodízio entre as faixas da pasta) e `"musica_inicio": s`
   pula intros fracas (comece onde a faixa já tem energia). Com copyright:
   - **cortes de 30–60s** (padrão de validação muda para 30–60s), focados nos **momentos de mais ação**;
   - rodar `./corte acao <video>` e priorizar as janelas do topo (tiroteios, perseguições, explosões, lutas),
     conferindo com a `folha` – o ranking usa o barulho do áudio original, mesmo que ele seja removido;
   - enquadramento `movimento` (tracking de ação com zoom dinâmico – ver Enquadramento).

## Legendas (falas)
Montserrat ExtraBold 60px, **branca com borda preta** (6px) + sombra leve, centralizadas em x=470 com a
**base em y=1500**. Cada bloco cabe em **uma linha só** (≤6 palavras / ≤2,8s, quebra em pausas e pontuação):
nunca joga palavra para a linha de baixo, exceto palavra gigante que sozinha não cabe na linha.
Erros de transcrição (nomes, marcas) → corrigir pelo `glossario` do plano (não editar a máquina).
Podcast com título + legendas: o card do título vai para o **topo** da safe area e a legenda fica na base.

## Gancho (abertura viral) – OBRIGATÓRIO em todo corte (validado)
Campo `"gancho": {"inicio": s, "fim": s}` no corte (tempos da fonte, 3–12s, normalmente de dentro do próprio
corte): o **trecho mais viral/chamativo** do corte (frase de efeito, punchline, momento mais polêmico ou engraçado).
A máquina renderiza esse trecho **antes** do corte, em **preto e branco**, com legendas, e um **badge pílula
branco** "Ainda neste vídeo" (texto preto, **bolinha vermelha piscando** à esquerda) no canto superior esquerdo
da safe area (x=60, y=380). Depois vem uma **transição de flash branco** (0,18s saindo + 0,25s entrando, com
micro fade no áudio) com o **som `sfx/transicao.mp3`** (whoosh da ElevenLabs; pico alinhado à emenda, volume
`SFX_VOLUME`) e o corte normal. Para trocar o som: `./corte sfx "<descrição>" --nome transicao`. A validação de duração (máx. 120s) considera **gancho + corte**.
Escolha do gancho: ler a transcrição do corte e pegar a frase que, isolada, mais desperta curiosidade
(ex.: "Você já fez sexo com um gorila?", "Eu sei que o Fernandinho nunca mais jogou"). Confira as palavras
do gancho e as bordas do corte (início/fim por palavra) antes de renderizar. Se gancho + corte passar de 120s,
encurte o corte no trecho menos essencial (introdução ou conclusão redundante) ou use um gancho mais curto;
`"reacao_max"` no gancho limita a risada mantida no fim dele. Encaixe nas palavras é automático. Constantes `GANCHO_*`,
`BADGE_*`, `TRANSICAO_*` em `config.py`.

## Marca dos cortes (todos os vídeos)
Faixa inferior **fora da safe area** (y 1500–1920): degradê do **preto (base) para transparente (y=1500)** com
uma **grade de quadrados bem finos** (linhas de 1px a cada 26px, mais visível perto da base). Nunca entra na safe
area e fica **abaixo (z-index) das legendas, card e badge**. Ordem de desenho: vídeo → marca → card/legendas →
badge. Constantes `MARCA_*` em `config.py`; desenho em `texto.py` (`render_marca`).

## Card do título (legenda fixa – jogos/trailers ou qualquer corte com `titulo`)
Card estilizado, menor que a legenda: **fundo branco**, texto **preto** Montserrat ExtraBold 50px em CAIXA ALTA
alinhado à esquerda, **faixa amarela** (#FFC400, 16px) no canto esquerdo, cantos arredondados e sombra suave.
Largura máx. 760px, até 3 linhas (reduz a fonte se não couber), centralizado em x=470 com a base em y=1500.
**Animação:** abre suavemente como uma gaveta (drawer) da esquerda para a direita no início do vídeo
(começa em 0,25s, dura 0,75s, ease-out) e fica fixo até o fim. Constantes `CARD_*` em `config.py`;
desenho/animação em `texto.py` (`render_card`, `quadro_card`).

## plano.json
```json
{
  "video": "nome-do-arquivo.mp4",
  "tipo": "podcast",                       // podcast | entrevista | jogo | trailer | editado | outro
  "contexto": "Podcast X com convidado Y sobre Z",
  "glossario": {"cloud code": "Claude Code"}, // correções aplicadas às legendas
  "copyright_audio": false,                // true = troca o áudio por trilha de sound/ (regra 11)
  "musica": null, "musica_inicio": 0,      // faixa de sound/ e ponto de início (s)
  "cortes": [
    {
      "id": 1,
      "nome": "opiniao-polemica-sobre-ia",  // vira o nome do arquivo
      "inicio": 754.2, "fim": 842.9,         // segundos (ou "12:34.2")
      "titulo": null,                        // texto fixo na tela (obrigatório em jogo/trailer)
      "legendas": true,                      // padrão: true, exceto jogo/trailer
      "enquadramento": null,                 // padrão pelo tipo (ver abaixo)
      "gancho": {"inicio": 800.2, "fim": 807.9}, // abertura viral (P&B + badge) antes do corte
      "post": {"titulo": "...", "descricao": "...", "hashtags": ["#..."]}
    }
  ]
}
```
Campos opcionais por corte: `tipo` (sobrescreve o geral), `ajustar_fala` (encaixe nas palavras; padrão
true exceto jogo/trailer), `glossario`.

### Enquadramento
Padrão por tipo: podcast/entrevista → `rosto`; jogo/trailer → `movimento`; editado/outro → `centro`.
Pode ser um modo (`"rosto"`), um objeto (`{"modo": "centro", "x": 0.3}`) ou uma lista de trechos com tempos
absolutos (`[{"inicio": 100, "fim": 130, "modo": "ajustar"}, {"inicio": 130, "fim": 190, "modo": "rosto"}]`);
trechos não cobertos usam o padrão.

| Modo | Uso | Opções |
|---|---|---|
| `rosto` | segue o falante (atividade da boca via MediaPipe, troca com histerese ≥1,8s, zoom automático em plano aberto, câmera parada se o rosto cabe no quadro). Cena sem rosto → `movimento`. | `pessoa`: esquerda/direita/centro (fixa alguém); `zoom` |
| `movimento` | segue a ação – jogos/trailers. Fluxo óptico a 10 amostras/s **sem o movimento da câmera** (só o que se move de verdade), ignora HUD (topo 10%, base 20%: estrelas/minimapa), resposta mais rápida quanto maior a ação, **zoom dinâmico** (até +40%) nos picos de ação concentrada e o **centro da tela (mira/personagem) sempre dentro dos 70% centrais do recorte**. | `zoom`, `zoom_acao` (false desliga o zoom dinâmico) |
| `centro` | recorte fixo | `x`, `y` (0–1, centro do recorte), `zoom` |
| `manual` | keyframes | `pontos: [{"t": 105.0, "x": 0.3, "zoom": 1.2}, ...]` |
| `ajustar` | quadro 16:9 inteiro sobre fundo desfocado (box de edição, HUD, cena aberta onde cortar perde a ação) | `zoom` (>1 corta laterais), `y` |

Escolha: jogo com ação concentrada → `movimento`; jogo com HUD/minimapa importante ou cena panorâmica →
`ajustar`; vídeo editado com box → `centro` com `x/zoom` no box (descubra a posição pela `folha`) ou `ajustar`.

## Saída
H.264 (CRF 18) 1080x1920, cor marcada **BT.709** (matriz/primárias/transferência, faixa tv), fps da fonte encaixado
numa taxa padrão (29,97 → 30000/1001; máx. 60). Áudio AAC 192k, 48 kHz estéreo, -14 LUFS, compatível com YouTube:
- loudness em **2 passadas**: mede o áudio montado (gancho + corte ou trilha) e aplica **ganho fixo** (`LOUDNESS_ALVO`).
  Não usar loudnorm de passada única: o modo dinâmico "bombeia" o volume nos primeiros segundos (o gancho);
- SFX da transição somado **depois** do ganho e **limitador final** (`LIMITADOR`, ~-1,5 dBFS) para a soma voz + SFX
  nunca estourar 0 dBFS (o re-encode do YouTube transforma isso em distorção);
- micro fade (`AUDIO_FADE_BORDA`) no primeiro e no último instante para não estalar no corte seco.
Arquivos: `saida/<video>/NN_nome.mp4` + `saida/<video>/SEO.md`.

## Desempenho (M1 Pro)
Transcrição ≈ 4–10x tempo real; análise de rostos ≈ 5x tempo real (cache em `trabalho/<video>/analise/`);
renderização ≈ 2x tempo real por corte.

## Ajustes globais (só com pedido explícito)
Tudo em `maquina/config.py`: tamanhos/fontes de legenda e título, safe area, duração mín/máx, zoom máximo,
sensibilidade de troca de falante, modelo do Whisper. Lógica: `enquadramento.py` (modos), `texto.py`
(legendas/título), `render.py` (composição/encode), `analise.py` (rostos/fala/cenas/movimento).
