"""Calcula o enquadramento vertical (recorte 9:16) de um corte.

Modos:
  rosto      – segue quem está falando (podcast/entrevista). Em plano aberto dá zoom
               no falante. Opções: pessoa = "esquerda"|"direita"|"centro" (fixa alguém),
               zoom (multiplica o zoom automático).
  movimento  – segue a ação (jogos, trailers) pelo centro de movimento da imagem.
               Opções: zoom.
  centro     – recorte fixo. Opções: x (0..1 centro horizontal), y, zoom.
  manual     – keyframes: pontos=[{"t": seg_absoluto, "x": 0..1, "y": 0..1, "zoom": 1.0}].
  ajustar    – quadro inteiro (16:9) reduzido para caber na largura, com fundo desfocado.
               Bom para box de edição/HUD/cenas abertas. Opções: zoom (>1 corta laterais), y (0..1).

Retorna uma lista de "planos": {t0, t1, modo, kf: [[t, cx, cy, ch], ...]} em pixels da fonte.
"""
import numpy as np

from config import (CENA_LIMIAR, LARGURA, ALTURA, ROSTO_ALTURA_ALVO, ROSTO_POS_Y, TROCA_MIN_PLANO,
                    TROCA_VANTAGEM, ZOOM_ACAO, ZOOM_MAX, MOVIMENTO_CENTRO_VISIVEL)

PADRAO_POR_TIPO = {"podcast": "rosto", "entrevista": "rosto", "jogo": "movimento",
                   "trailer": "movimento", "editado": "centro", "outro": "centro"}
PRECISA_ROSTOS = {"rosto"}


def normalizar_spec(spec, corte_ini, corte_fim, padrao):
    """Converte o campo `enquadramento` do plano em lista de segmentos absolutos."""
    if spec is None:
        spec = padrao
    if isinstance(spec, str):
        spec = {"modo": spec}
    if isinstance(spec, dict):
        spec = [dict(spec, inicio=spec.get("inicio", corte_ini), fim=spec.get("fim", corte_fim))]
    segs = []
    t = corte_ini
    for s in sorted(spec, key=lambda s: float(s.get("inicio", corte_ini))):
        i = max(corte_ini, float(s.get("inicio", corte_ini)))
        f = min(corte_fim, float(s.get("fim", corte_fim)))
        if i > t + 0.01:
            segs.append({"modo": padrao, "inicio": t, "fim": i})
        if f > i:
            segs.append(dict(s, inicio=i, fim=f))
            t = f
    if t < corte_fim - 0.01:
        segs.append({"modo": padrao, "inicio": t, "fim": corte_fim})
    return segs


def _clamp_crop(cx, cy, ch, W, H):
    ch = float(np.clip(ch, H / ZOOM_MAX, H))
    cw = ch * 9 / 16
    if cw > W:  # fonte já vertical/estreita
        cw = W
        ch = cw * 16 / 9
    cx = float(np.clip(cx, cw / 2, W - cw / 2))
    cy = float(np.clip(cy, ch / 2, H - ch / 2))
    return cx, cy, ch


def _cenas(amostras, t0, t1):
    """Divide [t0, t1] em cenas pelos cortes detectados."""
    lim = [t0]
    for a in amostras:
        if t0 < a["t"] < t1 and a["cena"] > CENA_LIMIAR and a["t"] - lim[-1] > 0.4:
            lim.append(a["t"])
    lim.append(t1)
    return list(zip(lim[:-1], lim[1:]))


def _suavizar(v, sigma):
    if len(v) < 3 or sigma <= 0:
        return np.asarray(v, float)
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    pad = np.pad(np.asarray(v, float), r, mode="edge")
    return np.convolve(pad, k, mode="valid")


# ---------------------------------------------------------------------------
def _planos_rosto(amostras, t0, t1, W, H, opts):
    am = [a for a in amostras if t0 - 1e-6 <= a["t"] < t1]
    zoom = float(opts.get("zoom", 1.0))
    if not am:
        return None
    # trilhas
    trilhas = {}
    for k, a in enumerate(am):
        for f in a["faces"]:
            trilhas.setdefault(f["id"], {})[k] = f
    if not trilhas:
        return None
    n = len(am)
    maior_h = max(np.median([f["h"] for f in d.values()]) for d in trilhas.values())
    validas = {}
    for tid, d in trilhas.items():
        hmed = np.median([f["h"] for f in d.values()])
        if len(d) >= max(2, 0.25 * n) and hmed >= 0.45 * maior_h:
            validas[tid] = d
    if not validas:
        validas = {max(trilhas, key=lambda i: len(trilhas[i])): trilhas[max(trilhas, key=lambda i: len(trilhas[i]))]}

    pessoa = opts.get("pessoa")
    if pessoa:
        xs = {tid: np.median([f["x"] + f["w"] / 2 for f in d.values()]) for tid, d in validas.items()}
        alvo = {"esquerda": min, "direita": max}.get(pessoa)
        tid = alvo(xs, key=xs.get) if alvo else min(xs, key=lambda i: abs(xs[i] - W / 2))
        validas = {tid: validas[tid]}

    ids = list(validas)
    # atividade de fala por trilha: desvio padrão móvel do jawOpen
    jan = 6
    act = np.zeros((len(ids), n))
    for j, tid in enumerate(ids):
        jaw = np.array([validas[tid][k]["jaw"] if k in validas[tid] and validas[tid][k]["jaw"] is not None
                        else np.nan for k in range(n)])
        for k in range(n):
            w = jaw[max(0, k - jan // 2): k + jan // 2 + 1]
            w = w[~np.isnan(w)]
            act[j, k] = (np.std(w) + 0.15 * np.mean(w)) if len(w) >= 2 else -1.0  # -1 = ausente
    # escolha do falante com histerese
    dt = 1.0 / max(1, round(1 / (am[1]["t"] - am[0]["t"]))) if n > 1 else 0.2
    min_k = int(TROCA_MIN_PLANO / dt)
    sust_k = max(2, int(0.6 / dt))
    atual = int(np.argmax(act[:, :min(n, 10)].mean(axis=1)))
    escolha = np.zeros(n, int)
    inicio_plano = 0
    cand, cand_desde = None, None
    for k in range(n):
        melhor = int(np.argmax(act[:, k]))
        ausente = act[atual, k] < 0
        if ausente and act[melhor, k] >= 0:
            atual, inicio_plano, cand = melhor, k, None
        elif melhor != atual and act[melhor, k] > TROCA_VANTAGEM * max(act[atual, k], 0.01):
            if cand != melhor:
                cand, cand_desde = melhor, k
            if k - cand_desde + 1 >= sust_k and cand_desde - inicio_plano >= min_k:
                escolha[cand_desde:k] = melhor
                atual, inicio_plano, cand = melhor, cand_desde, None
        else:
            cand = None
        escolha[k] = atual

    # agrupa em planos
    planos = []
    ini = 0
    for k in range(1, n + 1):
        if k == n or escolha[k] != escolha[ini]:
            planos.append((ini, k, ids[escolha[ini]]))
            ini = k
    # funde planos muito curtos no anterior
    fund = []
    for p in planos:
        if fund and (p[1] - p[0]) * dt < 1.0:
            fund[-1] = (fund[-1][0], p[1], fund[-1][2])
        else:
            fund.append(p)
    saida = []
    for (a, b, tid) in fund:
        fs = [(am[k]["t"], validas[tid][k]) for k in range(a, b) if k in validas[tid]]
        if not fs:
            fs = [(am[a]["t"], next(iter(validas[tid].values())))]
        hmed = float(np.median([f["h"] for _, f in fs]))
        ch = hmed / ROSTO_ALTURA_ALVO / zoom
        cxs = np.array([f["x"] + f["w"] / 2 for _, f in fs])
        cys = np.array([f["y"] + f["h"] / 2 for _, f in fs])
        ta = am[a]["t"] if a > 0 else t0
        tb = am[b]["t"] if b < n else t1
        ch_c = _clamp_crop(0, 0, ch, W, H)[2]
        cw = ch_c * 9 / 16
        mx, my = np.median(cxs), np.median(cys)
        ws = np.array([f["w"] for _, f in fs])
        hs = np.array([f["h"] for _, f in fs])
        cabe_x = np.all(np.abs(cxs - mx) + ws / 2 <= 0.44 * cw)
        cabe_y = np.all(np.abs(cys - my) + hs / 2 <= 0.30 * ch_c)
        if cabe_x and cabe_y:  # rosto sempre dentro do quadro fixo: câmera parada
            cx, cy, chh = _clamp_crop(np.median(cxs), np.median(cys) - (ROSTO_POS_Y - 0.5) * ch_c, ch_c, W, H)
            kf = [[ta, cx, cy, chh], [tb, cx, cy, chh]]
        else:  # pessoa se move: acompanha suavemente
            ts = [t for t, _ in fs]
            sx = _suavizar(cxs, 7)
            sy = _suavizar(cys, 7)
            kf = []
            for t, x, y in zip(ts, sx, sy):
                cx, cy, chh = _clamp_crop(x, y - (ROSTO_POS_Y - 0.5) * ch_c, ch_c, W, H)
                kf.append([t, cx, cy, chh])
            kf.insert(0, [ta] + kf[0][1:])
            kf.append([tb] + kf[-1][1:])
        saida.append({"t0": ta, "t1": tb, "modo": "rosto", "pessoa": int(tid), "kf": kf})
    return saida


def _ema_bidirecional(v, alfas):
    """Suavização com resposta variável (alfa alto = segue rápido) e sem atraso (ida e volta)."""
    ida = np.empty(len(v)); volta = np.empty(len(v))
    ida[0] = v[0]
    for k in range(1, len(v)):
        ida[k] = ida[k - 1] + alfas[k] * (v[k] - ida[k - 1])
    volta[-1] = v[-1]
    for k in range(len(v) - 2, -1, -1):
        volta[k] = volta[k + 1] + alfas[k] * (v[k] - volta[k + 1])
    return (ida + volta) / 2


def _planos_movimento(amostras, t0, t1, W, H, opts):
    """Segue a ação: centro do movimento próprio dos objetos (fluxo óptico sem o movimento da câmera).
    Tracking mais rápido quanto maior a ação + zoom dinâmico nos picos (desligue com zoom_acao=false)."""
    am = [a for a in amostras if t0 - 1e-6 <= a["t"] < t1]
    zoom_base = float(opts.get("zoom", 1.0))
    if len(am) < 2:
        cx, cy, ch = _clamp_crop(W / 2, H / 2, H / zoom_base, W, H)
        return [{"t0": t0, "t1": t1, "modo": "movimento", "kf": [[t0, cx, cy, ch], [t1, cx, cy, ch]]}]
    dt = am[1]["t"] - am[0]["t"]
    me = np.array([a["me"] for a in am])
    mx = np.array([a["mx"] for a in am])
    my = np.array([a.get("my", 0.5) for a in am])
    esp = np.array([a.get("esp", 0.25) for a in am])
    ref = max(float(np.percentile(me, 90)), 0.25)
    inten = np.clip(me / ref, 0, 1)
    ativo = me > 0.06
    # alvo: segura a última posição quando não há ação; leve atração para o centro (personagem)
    alvo_x = np.empty(len(am)); alvo_y = np.empty(len(am))
    ux, uy = 0.5, 0.5
    for k in range(len(am)):
        if ativo[k]:
            ux, uy = 0.65 * mx[k] + 0.35 * 0.5, 0.7 * my[k] + 0.3 * 0.5
        alvo_x[k], alvo_y[k] = ux, uy
    passo = dt / 0.1  # alfas calibrados para 10 amostras/s
    alfas = np.clip((0.06 + 0.30 * inten) * passo, 0.02, 0.9)
    px = _suavizar(_ema_bidirecional(alvo_x, alfas), 1.0)
    py = _suavizar(_ema_bidirecional(alvo_y, alfas), 1.0)
    # zoom dinâmico na ação concentrada
    zoom_max = max(1.0, min(1 + ZOOM_ACAO, H / 760))
    if opts.get("zoom_acao", True):
        conc = np.clip(1 - esp / 0.25, 0, 1)
        z = 1 + (zoom_max - 1) * inten * (0.4 + 0.6 * conc)
        z = _suavizar(_ema_bidirecional(z, np.full(len(z), 0.08 * passo)), max(1.0, 0.4 / dt))
    else:
        z = np.ones(len(am))
    kf = []
    for a, x, y, zz in zip(am, px, py, z):
        ch = H / (zoom_base * zz)
        # sem zoom fica centralizado na vertical; com zoom acompanha a altura da ação
        peso_y = (zz - 1) / max(zoom_max - 1, 1e-6)
        cy = H / 2 * (1 - peso_y) + y * H * peso_y
        # o centro da tela (mira/personagem em jogos) nunca sai da parte central do recorte
        lim = MOVIMENTO_CENTRO_VISIVEL * (ch * 9 / 16) / 2
        xc = float(np.clip(x * W, W / 2 - lim, W / 2 + lim))
        kf.append(list((a["t"],) + _clamp_crop(xc, cy, ch, W, H)))
    kf[0][0] = t0
    kf.append([t1] + kf[-1][1:])
    return [{"t0": t0, "t1": t1, "modo": "movimento", "kf": kf}]


def _planos_fixo(t0, t1, W, H, opts):
    ch = H / float(opts.get("zoom", 1.0))
    cx, cy, ch = _clamp_crop(float(opts.get("x", 0.5)) * W, float(opts.get("y", 0.5)) * H, ch, W, H)
    return [{"t0": t0, "t1": t1, "modo": "centro", "kf": [[t0, cx, cy, ch], [t1, cx, cy, ch]]}]


def _planos_manual(t0, t1, W, H, opts):
    pts = sorted(opts.get("pontos", []), key=lambda p: float(p["t"]))
    if not pts:
        return _planos_fixo(t0, t1, W, H, opts)
    kf = []
    for p in pts:
        cx, cy, ch = _clamp_crop(float(p.get("x", 0.5)) * W, float(p.get("y", 0.5)) * H,
                                 H / float(p.get("zoom", 1.0)), W, H)
        kf.append([float(p["t"]), cx, cy, ch])
    kf.insert(0, [t0] + kf[0][1:])
    kf.append([t1] + kf[-1][1:])
    return [{"t0": t0, "t1": t1, "modo": "manual", "kf": kf}]


def calcular(spec_segs, analise, W, H):
    planos = []
    amostras = analise["amostras"] if analise else []
    for s in spec_segs:
        modo = s["modo"]
        if modo == "ajustar":
            planos.append({"t0": s["inicio"], "t1": s["fim"], "modo": "ajustar",
                           "zoom": float(s.get("zoom", 1.0)), "y": s.get("y")})
            continue
        if modo == "centro":
            planos += _planos_fixo(s["inicio"], s["fim"], W, H, s)
            continue
        if modo == "manual":
            planos += _planos_manual(s["inicio"], s["fim"], W, H, s)
            continue
        for (c0, c1) in _cenas(amostras, s["inicio"], s["fim"]):
            p = None
            if modo == "rosto":
                p = _planos_rosto(amostras, c0, c1, W, H, s)
                if p is None:  # cena sem rostos (b-roll): segue movimento
                    p = _planos_movimento(amostras, c0, c1, W, H, {})
            else:
                p = _planos_movimento(amostras, c0, c1, W, H, s)
            planos += p
    return planos


def crop_em(planos, t):
    """Retorna (plano, cx, cy, ch) para o tempo t (interpolação linear dentro do plano)."""
    p = planos[-1]
    for q in planos:
        if q["t0"] - 1e-6 <= t < q["t1"]:
            p = q
            break
    if p["modo"] == "ajustar":
        return p, None, None, None
    kf = p["kf"]
    ts = [k[0] for k in kf]
    cx = float(np.interp(t, ts, [k[1] for k in kf]))
    cy = float(np.interp(t, ts, [k[2] for k in kf]))
    ch = float(np.interp(t, ts, [k[3] for k in kf]))
    return p, cx, cy, ch
