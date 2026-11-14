"""Legendas e títulos: agrupamento das palavras e renderização (Pillow) em RGBA."""
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import config as C

_fontes = {}
ABREVIACOES = {"mr.", "mrs.", "ms.", "dr.", "st.", "jr.", "sr.", "sra.", "dra.", "prof.", "vs.", "etc.", "u.s.", "e.g.", "i.e."}


def fim_de_frase(palavra):
    return re.search(r"[.!?…]$", palavra) is not None and palavra.lower() not in ABREVIACOES


def fonte(caminho, tamanho):
    k = (str(caminho), tamanho)
    if k not in _fontes:
        _fontes[k] = ImageFont.truetype(str(caminho), tamanho)
    return _fontes[k]


def _quebrar(texto, f, largura_max, borda):
    palavras = texto.split()
    linhas, atual = [], ""
    for p in palavras:
        tent = (atual + " " + p).strip()
        if f.getlength(tent) + 2 * borda <= largura_max or not atual:
            atual = tent
        else:
            linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas


def render_texto(texto, fonte_path, tamanho, borda, cor, cor_borda, largura_max, max_linhas, entrelinha):
    """Retorna imagem RGBA (numpy) com o texto centralizado. Reduz a fonte se não couber."""
    tam = tamanho
    while True:
        f = fonte(fonte_path, tam)
        linhas = _quebrar(texto, f, largura_max, borda)
        if len(linhas) <= max_linhas and all(f.getlength(l) + 2 * borda <= largura_max for l in linhas):
            break
        if tam <= 36:
            break
        tam -= 4
    asc, desc = f.getmetrics()
    alt_linha = int((asc + desc) * entrelinha)
    larg = int(max(f.getlength(l) for l in linhas)) + 4 * borda
    alt = alt_linha * len(linhas) + 4 * borda
    img = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # sombra suave + borda
    for i, l in enumerate(linhas):
        x = (larg - f.getlength(l)) / 2
        y = 2 * borda + i * alt_linha
        d.text((x + 3, y + 5), l, font=f, fill=(0, 0, 0, 110), stroke_width=borda, stroke_fill=(0, 0, 0, 110))
    for i, l in enumerate(linhas):
        x = (larg - f.getlength(l)) / 2
        y = 2 * borda + i * alt_linha
        d.text((x, y), l, font=f, fill=cor + (255,), stroke_width=borda, stroke_fill=cor_borda + (255,))
    return np.array(img)


def render_legenda(texto):
    return render_texto(texto, C.LEGENDA_FONTE, C.LEGENDA_TAMANHO, C.LEGENDA_BORDA, C.LEGENDA_COR,
                        C.LEGENDA_COR_BORDA, C.LEGENDA_LARGURA_MAX, C.LEGENDA_MAX_LINHAS, C.LEGENDA_ENTRELINHA)


def render_titulo(texto):
    return render_texto(texto.upper(), C.TITULO_FONTE, C.TITULO_TAMANHO, C.TITULO_BORDA, C.TITULO_COR,
                        C.TITULO_COR_BORDA, C.TITULO_LARGURA_MAX, C.TITULO_MAX_LINHAS, C.TITULO_ENTRELINHA)


def render_card(texto):
    """Card do título: fundo branco, texto preto, faixa amarela à esquerda, sombra suave.
    Retorna dict(img=RGBA numpy, margem=px de sombra, faixa=px)."""
    from PIL import ImageFilter
    texto = texto.upper()
    largura_texto = C.CARD_LARGURA_MAX - C.CARD_FAIXA - 2 * C.CARD_PAD_X
    tam = C.CARD_TAMANHO
    while True:
        f = fonte(C.CARD_FONTE, tam)
        linhas = _quebrar(texto, f, largura_texto, 0)
        if (len(linhas) <= C.CARD_MAX_LINHAS and all(f.getlength(l) <= largura_texto for l in linhas)) or tam <= 30:
            break
        tam -= 2
    asc, desc = f.getmetrics()
    alt_linha = int((asc + desc) * C.CARD_ENTRELINHA)
    cw = int(C.CARD_FAIXA + 2 * C.CARD_PAD_X + max(f.getlength(l) for l in linhas))
    ch = int(2 * C.CARD_PAD_Y + alt_linha * len(linhas) - (alt_linha - asc - desc))
    m = C.CARD_SOMBRA
    W, H = cw + 2 * m, ch + 2 * m
    # sombra
    sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((m, m + 6, m + cw, m + ch + 6), C.CARD_RAIO, fill=(0, 0, 0, 120))
    img = sombra.filter(ImageFilter.GaussianBlur(8))
    # card (supersampling 3x para bordas suaves)
    k = 3
    mask = Image.new("L", (cw * k, ch * k), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, cw * k - 1, ch * k - 1), C.CARD_RAIO * k, fill=255)
    mask = mask.resize((cw, ch), Image.LANCZOS)
    corpo = Image.new("RGB", (cw, ch), C.CARD_COR_FUNDO)
    ImageDraw.Draw(corpo).rectangle((0, 0, C.CARD_FAIXA - 1, ch), fill=C.CARD_COR_FAIXA)
    d = ImageDraw.Draw(corpo)
    for i, l in enumerate(linhas):
        d.text((C.CARD_FAIXA + C.CARD_PAD_X, C.CARD_PAD_Y + i * alt_linha), l, font=f, fill=C.CARD_COR_TEXTO)
    img.paste(corpo, (m, m), mask)
    return {"img": np.array(img), "margem": m, "faixa": C.CARD_FAIXA}


def quadro_card(card, t):
    """Recorte animado do card no tempo t (s desde o início do corte): abre como gaveta."""
    p = (t - C.CARD_ATRASO) / C.CARD_DURACAO
    if p <= 0:
        return None
    img = card["img"]
    if p >= 1:
        return img
    e = 1 - (1 - p) ** 3  # ease-out cúbico
    m, faixa = card["margem"], card["faixa"]
    cw = img.shape[1] - 2 * m
    vis = int(m + faixa + e * (cw - faixa))
    out = img[:, :vis].copy()
    out[:, :, 3] = (out[:, :, 3].astype(np.float32) * min(1.0, p * 4)).astype(np.uint8)
    return out


def render_badge():
    """Badge pílula branca com texto preto ("Ainda neste vídeo") e espaço para a bolinha vermelha.
    Retorna dict(img=RGBA, bolinha=(cx, cy, r))."""
    k = 3
    f = fonte(C.BADGE_FONTE, C.BADGE_TAMANHO * k)
    asc, desc = f.getmetrics()
    tw = f.getlength(C.BADGE_TEXTO)
    d_bol = C.BADGE_BOLINHA * k
    gap = 14 * k
    w = int(C.BADGE_PAD_X * k * 2 + d_bol + gap + tw)
    h = int(C.BADGE_PAD_Y * k * 2 + asc + desc * 0.4)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=(255, 255, 255, 255))
    x_txt = C.BADGE_PAD_X * k + d_bol + gap
    d.text((x_txt, h / 2), C.BADGE_TEXTO, font=f, fill=(17, 17, 17, 255), anchor="lm")
    img = img.resize((w // k, h // k), Image.LANCZOS)
    cx = (C.BADGE_PAD_X * k + d_bol / 2) / k
    return {"img": np.array(img), "bolinha": (cx, h / k / 2, C.BADGE_BOLINHA / 2)}


def quadro_badge(badge, t):
    """Badge com a bolinha vermelha piscando (pulso suave) no tempo t."""
    import math
    img = badge["img"].copy()
    a = (0.5 + 0.5 * math.cos(2 * math.pi * t / C.BADGE_PISCA)) ** 0.6
    cx, cy, r = badge["bolinha"]
    k = 4
    tam = int(2 * r * k + 4)
    bol = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    ImageDraw.Draw(bol).ellipse((2, 2, tam - 3, tam - 3), fill=C.BADGE_COR_BOLINHA + (int(255 * a),))
    bol = np.array(bol.resize((tam // k, tam // k), Image.LANCZOS)).astype(np.float32)
    x0, y0 = int(round(cx - bol.shape[1] / 2)), int(round(cy - bol.shape[0] / 2))
    reg = img[y0:y0 + bol.shape[0], x0:x0 + bol.shape[1]].astype(np.float32)
    al = bol[:, :, 3:4] / 255
    reg[:, :, :3] = bol[:, :, :3] * al + reg[:, :, :3] * (1 - al)
    img[y0:y0 + bol.shape[0], x0:x0 + bol.shape[1]] = reg.astype(np.uint8)
    return img


def render_marca():
    """Faixa inferior da marca (fora da safe area): degradê preto -> transparente + grade fina.
    Retorna RGBA (LARGURA x (ALTURA - SAFE_Y1)), para colar em y = SAFE_Y1."""
    h = C.ALTURA - C.SAFE_Y1
    w = C.LARGURA
    y = np.linspace(0, 1, h)[:, None]
    g = y * y * (3 - 2 * y)                       # smoothstep: 0 no limite da safe area, 1 na base
    a_preto = np.repeat(C.MARCA_ALFA_BASE * g, w, axis=1)
    grade = np.zeros((h, w), np.float32)
    passo = C.MARCA_GRADE
    yy = np.arange(h) + C.SAFE_Y1
    xx = np.arange(w)
    grade[(yy % passo) == 0, :] = 1
    grade[:, (xx % passo) == 0] = 1
    a_grade = grade * C.MARCA_GRADE_ALFA * g
    # composição: grade branca sobre preto
    A = a_grade + a_preto * (1 - a_grade)
    cor = np.where(A > 0, 255 * a_grade / np.maximum(A, 1e-6), 0)
    out = np.zeros((h, w, 4), np.uint8)
    out[:, :, 0] = out[:, :, 1] = out[:, :, 2] = np.clip(cor, 0, 255).astype(np.uint8)
    out[:, :, 3] = np.clip(A * 255, 0, 255).astype(np.uint8)
    return out


def aplicar_glossario(palavras, glossario):
    if not glossario:
        return palavras
    regras = [(re.compile(r"\b" + re.escape(k) + r"\b", re.IGNORECASE), v) for k, v in glossario.items()]
    for w in palavras:
        for rx, v in regras:
            w["w"] = rx.sub(v, w["w"])
    return palavras


def blocos_legenda(palavras, inicio, fim):
    """Agrupa palavras em blocos curtos (estilo shorts). Tempos relativos ao corte."""
    blocos, atual = [], []

    def fecha():
        if atual:
            blocos.append({"i": atual[0]["i"], "f": atual[-1]["f"], "texto": " ".join(w["w"] for w in atual)})

    for k, w in enumerate(palavras):
        if atual:
            pausa = w["i"] - atual[-1]["f"]
            dur = w["f"] - atual[0]["i"]
            texto = " ".join(x["w"] for x in atual + [w])
            pont = fim_de_frase(atual[-1]["w"])
            virg = re.search(r"[,;:]$", atual[-1]["w"]) is not None and len(atual) >= 3
            f = fonte(C.LEGENDA_FONTE, C.LEGENDA_TAMANHO)
            cabe = len(_quebrar(texto, f, C.LEGENDA_LARGURA_MAX, C.LEGENDA_BORDA)) <= C.LEGENDA_LINHAS_BLOCO
            if (pausa > C.LEGENDA_PAUSA_QUEBRA or dur > C.LEGENDA_MAX_DURACAO or pont or virg
                    or len(atual) >= C.LEGENDA_MAX_PALAVRAS or not cabe):
                fecha()
                atual = []
        atual.append(w)
    fecha()
    # tempos relativos e preenchimento de pequenos buracos
    out = []
    for k, b in enumerate(blocos):
        i = max(0.0, b["i"] - inicio)
        f = min(fim, b["f"] + 0.25) - inicio
        if k + 1 < len(blocos):
            prox = blocos[k + 1]["i"] - inicio
            f = prox if prox - f < 0.6 else min(f, prox)
        if f > i:
            out.append({"i": i, "f": f, "texto": b["texto"].strip()})
    return out


def frases(palavras):
    """Agrupa as palavras originais em frases (unidade de tradução)."""
    out, atual = [], []

    def fecha():
        if atual:
            out.append({"i": atual[0]["i"], "f": atual[-1]["f"], "original": " ".join(w["w"] for w in atual)})

    for w in palavras:
        if atual:
            pausa = w["i"] - atual[-1]["f"]
            fim_frase = fim_de_frase(atual[-1]["w"])
            longa = len(atual) >= 14 and re.search(r"[,;:]$", atual[-1]["w"]) is not None
            if fim_frase or pausa > 0.8 or longa or len(atual) >= 24:
                fecha()
                atual = []
        atual.append(w)
    fecha()
    return out


def palavras_traduzidas(frases_trad):
    """Distribui cada frase traduzida no intervalo da frase original (proporcional ao nº de letras),
    gerando 'palavras' sintéticas que seguem o mesmo fluxo das legendas normais."""
    out = []
    for fr in frases_trad:
        ws = fr["pt"].split()
        if not ws:
            continue
        pesos = [len(w) + 1 for w in ws]
        total = sum(pesos)
        t = fr["i"]
        dur = fr["f"] - fr["i"]
        for w, p in zip(ws, pesos):
            d = dur * p / total
            out.append({"w": w, "i": t, "f": t + d})
            t += d
    return out
