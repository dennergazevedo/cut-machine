"""Configuração central da Máquina de Cortes.

NÃO altere estes valores para um vídeo específico. Mudanças aqui afetam
todos os cortes e só devem ser feitas quando EXPLICITAMENTE solicitado.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "entrada"
SAIDA = RAIZ / "saida"
TRABALHO = RAIZ / "trabalho"
ASSETS = RAIZ / "assets"
FONTES = ASSETS / "fonts"
MODELOS = ASSETS / "modelos"

# ---------------------------------------------------------------------------
# Saída: vertical 9:16, 1080x1920
# ---------------------------------------------------------------------------
LARGURA = 1080
ALTURA = 1920
FPS_MAX = 60
CRF = 18
PRESET = "medium"
AUDIO_BITRATE = "192k"
LOUDNESS_ALVO = -14.0               # LUFS (padrão das redes). Medido na 1ª passada e aplicado como ganho fixo
LOUDNORM = "loudnorm=I=-14:TP=-1.5:LRA=11"  # usado só para medir (e como reserva se a medição falhar)
LIMITADOR = "alimiter=limit=0.84:attack=5:release=50:level=false:latency=true"  # teto ~-1,5 dBFS após a mixagem (SFX)
AUDIO_FADE_BORDA = 0.02              # s de fade no 1º/último instante do áudio (evita estalo no corte seco)
COR_SAIDA = "bt709"                  # matriz/primárias/transferência marcadas no H.264 (padrão HD do YouTube)

# ---------------------------------------------------------------------------
# Safe area combinada (TikTok + Instagram Reels + YouTube Shorts) em 1080x1920
#   YouTube Shorts : topo 380, base 380, esq 60, dir 120
#   Instagram Reels: topo ~230, base ~290, esq ~40, dir ~200 (metade inferior)
#   TikTok         : topo ~130, base ~370, esq ~60, dir ~140 (coluna de botões)
#   Combinada      : pior caso de cada lado (+ folga na base para descrições longas)
# ---------------------------------------------------------------------------
SAFE_TOPO = 380
SAFE_BASE = 420      # margem inferior -> limite y = 1500
SAFE_ESQ = 60
SAFE_DIR = 200       # margem direita -> limite x = 880
SAFE_X0, SAFE_X1 = SAFE_ESQ, LARGURA - SAFE_DIR          # 60 .. 880
SAFE_Y0, SAFE_Y1 = SAFE_TOPO, ALTURA - SAFE_BASE         # 380 .. 1500
SAFE_CX = (SAFE_X0 + SAFE_X1) // 2                       # 470
SAFE_CY = (SAFE_Y0 + SAFE_Y1) // 2                       # 940

# ---------------------------------------------------------------------------
# Legendas (falas) – Montserrat branca com borda preta, na base da safe area
# ---------------------------------------------------------------------------
LEGENDA_FONTE = FONTES / "Montserrat-ExtraBold.ttf"
LEGENDA_TAMANHO = 60
LEGENDA_BORDA = 6
LEGENDA_COR = (255, 255, 255)
LEGENDA_COR_BORDA = (0, 0, 0)
LEGENDA_LARGURA_MAX = 760          # px (cabe com folga em 60..880)
LEGENDA_MAX_LINHAS = 2            # só para palavra gigante que não cabe numa linha
LEGENDA_LINHAS_BLOCO = 1          # cada bloco de legenda cabe em UMA linha (não joga palavra p/ linha de baixo)
LEGENDA_MAX_PALAVRAS = 6           # palavras por bloco de legenda
LEGENDA_MAX_DURACAO = 2.8          # segundos por bloco
LEGENDA_PAUSA_QUEBRA = 0.45        # pausa (s) que força novo bloco
LEGENDA_ENTRELINHA = 1.12

# ---------------------------------------------------------------------------
# Título (jogos / trailers) – visível durante todo o corte
# ---------------------------------------------------------------------------
TITULO_FONTE = FONTES / "Montserrat-Black.ttf"
TITULO_TAMANHO = 84
TITULO_BORDA = 9
TITULO_COR = (255, 255, 255)
TITULO_COR_BORDA = (0, 0, 0)
TITULO_LARGURA_MAX = 780
TITULO_MAX_LINHAS = 3
TITULO_ENTRELINHA = 1.08

# ---------------------------------------------------------------------------
# Card do título fixo (jogos / trailers / qualquer corte com "titulo")
#   fundo branco, texto preto, faixa amarela no canto esquerdo,
#   abre como gaveta (drawer) da esquerda para a direita no início do vídeo
# ---------------------------------------------------------------------------
CARD_FONTE = FONTES / "Montserrat-ExtraBold.ttf"
CARD_TAMANHO = 50
CARD_COR_FUNDO = (255, 255, 255)
CARD_COR_TEXTO = (17, 17, 17)
CARD_COR_FAIXA = (255, 196, 0)       # amarelo
CARD_FAIXA = 16                      # largura da faixa amarela (px)
CARD_PAD_X = 30
CARD_PAD_Y = 22
CARD_RAIO = 12
CARD_LARGURA_MAX = 760
CARD_MAX_LINHAS = 3
CARD_ENTRELINHA = 1.12
CARD_ATRASO = 0.25                   # s até começar a abrir
CARD_DURACAO = 0.75                  # s de animação de abertura
CARD_SOMBRA = 14                     # margem da sombra (px)

# ---------------------------------------------------------------------------
# Gancho (abertura viral): trecho mais chamativo do corte repetido no início,
# em preto e branco, com badge "Ainda neste vídeo" e transição para o corte
# ---------------------------------------------------------------------------
GANCHO_MIN = 3.0
GANCHO_MAX = 12.0
BADGE_TEXTO = "Ainda neste vídeo"
BADGE_FONTE = FONTES / "Montserrat-Bold.ttf"
BADGE_TAMANHO = 34
BADGE_PAD_X = 26
BADGE_PAD_Y = 14
BADGE_BOLINHA = 18                   # diâmetro da bolinha vermelha (px)
BADGE_COR_BOLINHA = (235, 32, 32)
BADGE_PISCA = 1.0                    # período da piscada (s)
TRANSICAO_SAIDA = 0.18               # s de flash branco no fim do gancho
TRANSICAO_ENTRADA = 0.25             # s de flash branco saindo no início do corte
TRANSICAO_AUDIO = 0.12               # micro fade de áudio na emenda

# Som de transição (pasta sfx/ reaproveitável): arquivo sfx/transicao.* tocado na emenda gancho -> corte
SFX = RAIZ / "sfx"
SFX_TRANSICAO = "transicao"          # nome-base do arquivo em sfx/ (mp3/wav/m4a)
SFX_VOLUME = 0.9                     # volume do efeito na mixagem
SFX_ANTECIPA = 0.08                   # s antes da emenda em que o efeito começa (pico do whoosh na emenda)

# Reação final: não cortar com gente rindo/reagindo. Depois da última palavra, o corte se estende
# enquanto houver som de reação (risada, aplauso) até ele acabar ou alguém voltar a falar.
REACAO_MAX = 8.0                     # extensão máxima no fim do corte (s)
REACAO_GANCHO_MAX = 1.0              # extensão máxima no fim do gancho (s) – só um gostinho da risada
REACAO_QUEDA_DB = 13.0               # reação = energia acima de (mediana da fala - X dB)
REACAO_SILENCIO = 0.3                # s abaixo do limiar que encerram a reação

# ---------------------------------------------------------------------------
# Marca dos cortes: degradê preto->transparente com grade fina, só na faixa
# inferior FORA da safe area (y >= SAFE_Y1). Fica abaixo (z-index) das legendas.
# ---------------------------------------------------------------------------
MARCA_ALFA_BASE = 0.88               # opacidade do preto na borda inferior
MARCA_GRADE = 26                     # tamanho dos quadrados (px)
MARCA_GRADE_ALFA = 0.13              # opacidade das linhas da grade (no ponto mais escuro)

# ---------------------------------------------------------------------------
# Regras de corte
# ---------------------------------------------------------------------------
DURACAO_MIN = 45.0
DURACAO_MAX = 120.0
# Áudio com copyright: trilha de fundo da pasta sound/ substitui o áudio original;
# cortes mais curtos e focados nos momentos de mais ação
SOUND = RAIZ / "sound"
COPYRIGHT_DURACAO_MIN = 30.0
COPYRIGHT_DURACAO_MAX = 60.0
MUSICA_FADE_IN = 0.4
MUSICA_FADE_OUT = 1.5
VIDEO_LONGO = 300.0                # +5min = vários cortes

# ---------------------------------------------------------------------------
# Enquadramento
# ---------------------------------------------------------------------------
ANALISE_FPS = 5                    # amostras/s na análise de rostos
ANALISE_FPS_MOVIMENTO = 10         # amostras/s no tracking de ação (modo movimento)
ZOOM_ACAO = 0.4                    # zoom extra máximo nos picos de ação (modo movimento)
MOVIMENTO_CENTRO_VISIVEL = 0.7     # centro da tela fica sempre nos 70% centrais do recorte (mira/personagem)
ANALISE_ALTURA = 720               # resolução usada na análise
ZOOM_MAX = 1.9                     # zoom máximo sobre o recorte de altura total
ROSTO_ALTURA_ALVO = 0.17           # altura do rosto / altura do recorte (plano médio)
ROSTO_POS_Y = 0.36                 # posição vertical do rosto no recorte (0=topo)
TROCA_MIN_PLANO = 1.8              # duração mínima (s) de um plano antes de trocar de falante
TROCA_VANTAGEM = 1.35              # novo falante precisa de X vezes mais atividade
CENA_LIMIAR = 0.45                 # diferença de histograma que indica corte de cena
TRANSCRICAO_MODELO = "mlx-community/whisper-large-v3-turbo"
