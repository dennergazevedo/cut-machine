# Como pedir cortes para a Máquina de Cortes

1. Coloque o vídeo original em `entrada/` (ou envie uma URL do YouTube).
2. Abra o Claude Code nesta pasta e use um dos prompts abaixo.

## Prompt mínimo
```
Gere os cortes do vídeo entrada/NOME_DO_VIDEO.mp4
```

## Prompt recomendado (cortes mais consistentes)
```
Gere os cortes do vídeo entrada/NOME_DO_VIDEO.mp4

- Tipo: podcast            (podcast | entrevista | jogo | trailer | editado)
- Contexto: episódio do podcast X com o convidado Y (empresário, fundador da Z)
- Pessoas: host = Fulano (esquerda), convidado = Ciclano (direita)
- Público/tema do canal: empreendedorismo e tecnologia
- Foco dos cortes: opiniões polêmicas sobre IA, histórias de fracasso, dicas práticas
- Quantidade: 5 a 8 cortes (ou "todos que valerem a pena")
- Nomes/termos com grafia correta: "Claude Code", "Nubank", "Ciclano da Silva"
- Evitar: trechos sobre patrocinador
```

## Exemplo – trailer
```
Gere cortes do trailer entrada/gta6_trailer2.mp4
Tipo: trailer de jogo (GTA VI). Pesquise o que está sendo mais comentado e faça 3 cortes
com títulos diferentes (ex.: realismo gráfico, Vice City real x jogo, possibilidades de gameplay).
```

## Exemplo – gameplay
```
Gere cortes da gameplay entrada/partida_ranked.mp4
Tipo: jogo (Valorant). Foque nas jogadas de clutch e nos abates múltiplos. Título curto e chamativo.
```

## Informações que ajudam (quanto mais, melhor)
| Informação | Por quê |
|---|---|
| Tipo do vídeo | define enquadramento padrão e se terá legenda ou título |
| Contexto (quem, sobre o quê) | ajuda a escolher trechos e escrever títulos/descrições |
| Nomes e termos técnicos | corrige a grafia nas legendas (glossário) |
| Posição das pessoas | permite fixar o foco em alguém (`pessoa: esquerda/direita`) |
| Temas de interesse / a evitar | direciona a escolha dos cortes |
| Quantidade de cortes | para vídeos longos |
| Áudio tem copyright? | troca o som por trilha de `sound/` e faz cortes curtos (30–60s) nos momentos de mais ação |
| Idioma do vídeo (opcional) | é detectado automaticamente; legendas, títulos e textos saem **sempre em PT-BR** (vídeos estrangeiros são traduzidos) |

## Pedidos de ajuste
- Ajuste de **um corte**: "No corte 3 comece 10s antes" / "No corte 2 foque no convidado da direita"
  → muda só o `plano.json` daquele vídeo.
- Ajuste da **máquina** (vale para todos os vídeos) precisa ser explícito:
  "A máquina de cortes não está gerando legendas em tal cenário, ajuste".
