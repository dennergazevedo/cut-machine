"""Renderização dos cortes: recorte 9:16 + legendas/título + áudio normalizado."""
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np

import config as C
import enquadramento as E
import texto as T
from analise import analisar
from transcrever import idioma_transcricao, palavras_no_intervalo
from util import ler_json, fmt, parse_tempo, pasta_saida, pasta_trabalho, probe, resolver_video, salvar_json, slug

TIPOS_SEM_LEGENDA = {"jogo", "trailer"}


# ---------------------------------------------------------------------------
def _blend(dst, rgba, x, y):
    h, w = rgba.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return
    src = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = src[:, :, 3:4].astype(np.float32) / 255.0
    reg = dst[y0:y1, x0:x1].astype(np.float32)
    dst[y0:y1, x0:x1] = (src[:, :, :3] * a + reg * (1 - a)).astype(np.uint8)


_overlay_safe = None


def overlay_safearea():
    global _overlay_safe
    if _overlay_safe is None:
        _overlay_safe = cv2.imread(str(C.ASSETS / "safearea" / "safearea_overlay.png"), cv2.IMREAD_UNCHANGED)
        _overlay_safe = cv2.cvtColor(_overlay_safe, cv2.COLOR_BGRA2RGBA)
    return _overlay_safe


def compor(frame, plano, cx, cy, ch, yc_padrao=None):
    """Frame da fonte (RGB) -> quadro vertical 1080x1920 (RGB)."""
    H, W = frame.shape[:2]
    if plano["modo"] == "ajustar":
        # fundo desfocado
        esc = max(C.LARGURA / W, C.ALTURA / H)
        pequeno = cv2.resize(frame, (max(1, int(W * esc / 12)), max(1, int(H * esc / 12))), interpolation=cv2.INTER_AREA)
        pequeno = cv2.GaussianBlur(pequeno, (0, 0), 4)
        fundo = cv2.resize(pequeno, (int(W * esc) + 2, int(H * esc) + 2), interpolation=cv2.INTER_LINEAR)
        ox, oy = (fundo.shape[1] - C.LARGURA) // 2, (fundo.shape[0] - C.ALTURA) // 2
        out = (fundo[oy:oy + C.ALTURA, ox:ox + C.LARGURA].astype(np.float32) * 0.55).astype(np.uint8)
        zoom = max(1.0, plano.get("zoom", 1.0))
        cw = W / zoom
        x0 = int((W - cw) / 2)
        src = frame[:, x0:x0 + int(cw)]
        nh = int(round(C.LARGURA * H / cw / 2) * 2)
        fg = cv2.resize(src, (C.LARGURA, nh), interpolation=cv2.INTER_AREA if cw > C.LARGURA else cv2.INTER_CUBIC)
        yc = plano.get("y")
        yc = (yc_padrao or C.SAFE_CY) if yc is None else float(yc) * C.ALTURA
        y0 = int(np.clip(yc - nh / 2, 0, max(0, C.ALTURA - nh)))
        nh = min(nh, C.ALTURA - y0)
        out[y0:y0 + nh] = fg[:nh]
        return np.ascontiguousarray(out)
    cw = ch * 9 / 16
    x0 = cx - cw / 2
    y0 = cy - ch / 2
    # recorte subpixel via warpAffine (movimento suave) e escala para 1080x1920
    s = C.LARGURA / cw
    M = np.float32([[s, 0, -x0 * s], [0, s, -y0 * s]])
    return cv2.warpAffine(frame, M, (C.LARGURA, C.ALTURA), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


# ---------------------------------------------------------------------------
def _ajustar_limites(palavras, inicio, fim):
    """Encaixa início/fim nas palavras para não cortar fala no meio."""
    if not palavras:
        return inicio, fim
    todas = palavras
    # só palavras que COMEÇAM dentro do trecho (a folga de 0,6s vale apenas para terminar a última palavra)
    dentro = [w for w in todas if w["i"] >= inicio - 0.35 and w["i"] < fim and w["f"] <= fim + 0.6]
    if not dentro:
        return inicio, fim
    primeira, ultima = dentro[0], dentro[-1]
    antes = [w for w in todas if w["f"] <= primeira["i"]]
    depois = [w for w in todas if w["i"] >= ultima["f"]]
    ni = primeira["i"] - 0.15
    if antes:
        ni = max(ni, antes[-1]["f"] + 0.02)
    nf = ultima["f"] + 0.4
    if depois:
        nf = min(nf, depois[0]["i"] - 0.02)
    return max(0.0, ni), nf


def carregar_traducao(corte, so_exportar=False):
    """Vídeos fora do português: as legendas vêm de trabalho/<video>/traducao_NN.json,
    com uma tradução PT-BR (campo "pt") por frase do original (campo "original").
    Se o arquivo não existir ou estiver incompleto, ele é (re)gerado e a renderização para."""
    p = corte.trab / f"traducao_{corte.id:02d}.json"
    frases = T.frases(corte.palavras)
    antigo = {}
    if p.exists():
        for f in ler_json(p).get("frases", []):
            if f.get("pt"):
                antigo[f["original"]] = f["pt"]
    for f in frases:
        f["pt"] = antigo.get(f["original"], "")
    faltando = [f for f in frases if not f["pt"].strip()]
    salvar_json(p, {"idioma_original": corte.idioma, "corte": corte.id,
                    "instrucoes": "Preencha 'pt' com a tradução em português do Brasil, natural e curta (estilo legenda). "
                                  "Não altere 'original', 'i' e 'f'.",
                    "frases": frases})
    if so_exportar:
        return p, len(faltando)
    if faltando:
        raise SystemExit(f"Corte {corte.id}: vídeo em '{corte.idioma}'. Legendas precisam ser em PT-BR: "
                         f"traduza {len(faltando)} frase(s) em {p} e rode novamente.")
    return frases


def escolher_musica(nome, idx):
    """Trilha de fundo: nome explícito (arquivo em sound/) ou rodízio pelas faixas da pasta."""
    faixas = sorted(p for p in C.SOUND.glob("*") if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"})
    if nome:
        p = C.SOUND / nome
        if not p.exists():
            raise SystemExit(f"Trilha não encontrada: {p}")
        return p
    return faixas[(idx - 1) % len(faixas)] if faixas else None


_marca = None
_badge = None


def marca():
    global _marca
    if _marca is None:
        _marca = T.render_marca()
    return _marca


def badge():
    global _badge
    if _badge is None:
        _badge = T.render_badge()
    return _badge


def estender_reacao(video, palavras, inicio, fim, cap):
    """Regra da reação: se depois da última fala há risada/aplauso/reação (som sem palavras),
    estende o fim até a reação acabar, sem invadir a próxima fala e no máximo `cap` segundos."""
    from analise import energia_audio
    if cap <= 0 or not palavras:
        return fim
    db = energia_audio(video, 0.1)
    fala = [db[int(w["i"] * 10): int(w["f"] * 10) + 1].mean() for w in palavras
            if inicio <= w["i"] and w["f"] <= fim and int(w["f"] * 10) < len(db)]
    if not fala:
        return fim
    limiar = float(np.median(fala)) - C.REACAO_QUEDA_DB
    prox = [w["i"] for w in palavras if w["i"] >= fim - 0.01]
    limite = min(fim + cap, (min(prox) - 0.05) if prox else fim + cap, len(db) / 10 - 0.1)
    t, quieto = fim, 0.0
    while t < limite:
        if db[int(t * 10)] < limiar:
            quieto += 0.1
            if quieto >= C.REACAO_SILENCIO:
                return max(fim, t - C.REACAO_SILENCIO + 0.15)
        else:
            quieto = 0.0
        t += 0.1
    return max(fim, limite)


class Corte:
    def __init__(self, plano_geral, c, video, info, trab, sufixo=""):
        self.sufixo = sufixo
        self.c = c
        self.video = video
        self.info = info
        self.trab = trab
        self.tipo = c.get("tipo", plano_geral.get("tipo", "podcast"))
        self.id = int(c.get("id", 0))
        self.nome = slug(c.get("nome", f"corte-{self.id}"))
        self.inicio = parse_tempo(c["inicio"])
        self.fim = min(parse_tempo(c["fim"]), info["duracao"])
        self.legendas = c.get("legendas", self.tipo not in TIPOS_SEM_LEGENDA)
        self.titulo = c.get("titulo")
        palavras_amplas = palavras_no_intervalo(trab, self.inicio - 5, self.fim + 5)
        if c.get("ajustar_fala", self.tipo not in TIPOS_SEM_LEGENDA):
            self.inicio, self.fim = _ajustar_limites(palavras_amplas, self.inicio, self.fim)
            cap = c.get("reacao_max", C.REACAO_GANCHO_MAX if sufixo == "_gancho" else C.REACAO_MAX)
            fim_fala = self.fim
            self.fim = min(info["duracao"], estender_reacao(video, palavras_amplas, self.inicio, self.fim, cap))
            if self.fim - fim_fala > 0.2:
                print(f"  reação{' (gancho)' if sufixo else ''}: +{self.fim - fim_fala:.1f}s para a risada/reação terminar")
        self.dur = self.fim - self.inicio
        self.palavras = [w for w in palavras_amplas if w["f"] > self.inicio and w["i"] < self.fim]
        self.idioma = idioma_transcricao(trab)
        self.glossario = {**plano_geral.get("glossario", {}), **c.get("glossario", {})}
        # áudio com copyright -> trilha de fundo de sound/ no lugar do áudio original
        self.copyright = bool(c.get("copyright_audio", plano_geral.get("copyright_audio", False)))
        self.musica = escolher_musica(c.get("musica", plano_geral.get("musica")), self.id) if self.copyright else None
        self.musica_inicio = float(c.get("musica_inicio", plano_geral.get("musica_inicio", 0.0)))
        self.dmin = C.COPYRIGHT_DURACAO_MIN if self.copyright else C.DURACAO_MIN
        self.dmax = C.COPYRIGHT_DURACAO_MAX if self.copyright else C.DURACAO_MAX
        padrao = E.PADRAO_POR_TIPO.get(self.tipo, "centro")
        self.segs = E.normalizar_spec(c.get("enquadramento"), self.inicio, self.fim, padrao)

    def validar(self, forcar=False):
        avisos = []
        if self.dur < self.dmin:
            avisos.append(f"duração {self.dur:.1f}s < {self.dmin:.0f}s")
        if self.dur > self.dmax:
            avisos.append(f"duração {self.dur:.1f}s > {self.dmax:.0f}s")
        if avisos and not forcar and not (self.info["duracao"] < self.dmin):
            raise SystemExit(f"Corte {self.id} ({self.nome}): " + "; ".join(avisos) + " (use --forcar para ignorar)")
        for a in avisos:
            print(f"  AVISO: {a}")

    def preparar(self):
        modos = {s["modo"] for s in self.segs}
        analise = None
        if modos & {"rosto", "movimento"}:
            t = time.time()
            print(f"  analisando {fmt(self.inicio)}-{fmt(self.fim)} (modos: {', '.join(sorted(modos))})...")
            fps = C.ANALISE_FPS if "rosto" in modos else C.ANALISE_FPS_MOVIMENTO
            analise = analisar(self.video, self.inicio, self.fim, rostos="rosto" in modos, fps=fps)
            print(f"  análise ok ({time.time() - t:.0f}s)")
        self.planos = E.calcular(self.segs, analise, self.info["largura"], self.info["altura"])
        salvar_json(self.trab / f"enquadramento_{self.id:02d}{self.sufixo}.json", self.planos)
        # legendas
        self.blocos = []
        if self.legendas and self.palavras:
            pal = [dict(w) for w in self.palavras]
            if self.idioma != "pt":  # regra: legendas sempre em PT-BR
                pal = T.palavras_traduzidas(carregar_traducao(self))
            pal = T.aplicar_glossario(pal, self.glossario)
            self.blocos = T.blocos_legenda(pal, self.inicio, self.fim)
            for b in self.blocos:
                b["img"] = T.render_legenda(b["texto"])
            salvar_json(self.trab / f"legendas_{self.id:02d}{self.sufixo}.json",
                        [{k: v for k, v in b.items() if k != "img"} for b in self.blocos])
        self.card = T.render_card(self.titulo) if self.titulo else None
        self.titulo_img = self.card["img"] if self.card else None
        # modo "ajustar": centraliza o vídeo no espaço livre acima do texto da base
        if self.blocos:
            reserva = max(b["img"].shape[0] for b in self.blocos)
        elif self.titulo_img is not None:
            reserva = self.titulo_img.shape[0]
        else:
            reserva = 0
        topo = C.SAFE_Y0 + (self.titulo_img.shape[0] + 20 if (self.blocos and self.titulo_img is not None) else 0)
        base = C.SAFE_Y1 - reserva - 30
        alt_video = C.LARGURA * self.info["altura"] / self.info["largura"]
        self.ajustar_yc = (topo + base) / 2 if base - topo >= alt_video * 0.9 else max(C.SAFE_Y0 + alt_video / 2, base - alt_video / 2)

    def sobrepor(self, quadro, t_rel, preview=False, gancho=False):
        # ordem = z-index: vídeo < marca (faixa inferior) < card/legendas < badge < guia de safe area
        if gancho:  # abertura viral em preto e branco
            cinza = cv2.cvtColor(quadro, cv2.COLOR_RGB2GRAY)
            quadro[:] = cv2.cvtColor(cinza, cv2.COLOR_GRAY2RGB)
        _blend(quadro, marca(), 0, C.SAFE_Y1)
        if self.card is not None and not gancho:
            h, w = self.titulo_img.shape[:2]
            m = self.card["margem"]
            x = C.SAFE_CX - w // 2
            if self.blocos:  # card no topo da safe area quando há legendas
                y = C.SAFE_Y0 - m
            else:
                y = C.SAFE_Y1 - h + m
            img = T.quadro_card(self.card, t_rel)
            if img is not None:
                _blend(quadro, img, x, y)
        for b in self.blocos:
            if b["i"] <= t_rel < b["f"]:
                h, w = b["img"].shape[:2]
                _blend(quadro, b["img"], C.SAFE_CX - w // 2, C.SAFE_Y1 - h)
                break
        if gancho:
            _blend(quadro, T.quadro_badge(badge(), t_rel), C.SAFE_X0, C.SAFE_Y0)
        if preview:
            _blend(quadro, overlay_safearea(), 0, 0)
        return quadro


def _fps_saida(info):
    f = info["fps"]
    if f <= 0 or f > C.FPS_MAX:
        return 30.0
    return round(f * 1000) / 1000


def _flash(quadro, intensidade):
    """Transição: mistura o quadro com branco (0 = nada, 1 = branco total)."""
    if intensidade <= 0:
        return quadro
    e = float(min(1.0, intensidade))
    return (quadro.astype(np.float32) * (1 - e) + 255 * e).astype(np.uint8)


def sfx_transicao():
    for ext in (".mp3", ".wav", ".m4a", ".aac", ".ogg"):
        p = C.SFX / f"{C.SFX_TRANSICAO}{ext}"
        if p.exists():
            return p
    return None


def criar_gancho(plano_geral, c, video, info, trab):
    """Corte do gancho (abertura viral) a partir de c["gancho"] = {"inicio", "fim"} (tempos da fonte)."""
    g = c.get("gancho")
    if not g:
        return None
    cg = dict(c, inicio=g["inicio"], fim=g["fim"], titulo=None, reacao_max=g.get("reacao_max", C.REACAO_GANCHO_MAX),
              enquadramento=g.get("enquadramento", c.get("enquadramento")))
    cg.pop("gancho", None)
    gancho = Corte(plano_geral, cg, video, info, trab, sufixo="_gancho")
    if not (C.GANCHO_MIN <= gancho.dur <= C.GANCHO_MAX):
        print(f"  AVISO: gancho com {gancho.dur:.1f}s (recomendado {C.GANCHO_MIN:.0f}-{C.GANCHO_MAX:.0f}s)")
    return gancho


def renderizar_corte(plano_geral, c, rapido=False, preview=False, forcar=False):
    video = resolver_video(plano_geral["video"])
    info = probe(video)
    trab = pasta_trabalho(video)
    corte = Corte(plano_geral, c, video, info, trab)
    gancho = criar_gancho(plano_geral, c, video, info, trab)
    total = corte.dur + (gancho.dur if gancho else 0)
    print(f"\n▶ Corte {corte.id:02d} '{corte.nome}' {fmt(corte.inicio)} → {fmt(corte.fim)} ({corte.dur:.1f}s) tipo={corte.tipo}"
          + (f" + gancho {fmt(gancho.inicio)}-{fmt(gancho.fim)} ({gancho.dur:.1f}s) = {total:.1f}s" if gancho else ""))
    corte.validar(forcar)
    if gancho and total > corte.dmax and not forcar:
        raise SystemExit(f"Corte {corte.id}: gancho + corte = {total:.1f}s > {corte.dmax:.0f}s (encurte o corte ou o gancho)")
    if gancho:
        gancho.preparar()
    corte.preparar()
    fps = _fps_saida(info)
    W, H = info["largura"], info["altura"]
    destino = pasta_saida(video) / f"{corte.id:02d}_{corte.nome}{'_preview' if preview else ''}.mp4"
    partes = ([gancho] if gancho else []) + [corte]

    enc_cmd = ["ffmpeg", "-y", "-v", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{C.LARGURA}x{C.ALTURA}", "-r", str(fps), "-i", "-"]
    if corte.copyright:
        if corte.musica is None:
            raise SystemExit(f"copyright_audio ativo mas nenhuma trilha em {C.SOUND}")
        fo = max(0.0, total - C.MUSICA_FADE_OUT)
        print(f"  áudio com copyright -> trilha: {corte.musica.name}")
        enc_cmd += ["-stream_loop", "-1", "-ss", f"{corte.musica_inicio:.3f}", "-i", str(corte.musica),
                    "-map", "0:v", "-map", "1:a", "-t", f"{total:.3f}",
                    "-af", f"afade=t=in:d={C.MUSICA_FADE_IN},afade=t=out:st={fo:.3f}:d={C.MUSICA_FADE_OUT},{C.LOUDNORM}"]
    elif info["tem_audio"]:
        for p in partes:
            enc_cmd += ["-ss", f"{p.inicio:.3f}", "-t", f"{p.dur:.3f}", "-i", str(video)]
        if gancho:
            ta = C.TRANSICAO_AUDIO
            filtro = (f"[1:a]afade=t=out:st={gancho.dur - ta:.3f}:d={ta}[a1];[2:a]afade=t=in:d={ta}[a2];"
                      f"[a1][a2]concat=n=2:v=0:a=1,{C.LOUDNORM}[voz]")
            sfx = sfx_transicao()
            if sfx:
                atraso = int(max(0.0, gancho.dur - C.SFX_ANTECIPA) * 1000)
                enc_cmd += ["-i", str(sfx)]
                filtro += (f";[3:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={C.SFX_VOLUME},"
                           f"adelay={atraso}|{atraso}[fx];[voz]aformat=sample_rates=48000:channel_layouts=stereo[v2];"
                           f"[v2][fx]amix=inputs=2:duration=first:normalize=0[a]")
                print(f"  som de transição: {sfx.name}")
            else:
                filtro = filtro.replace("[voz]", "[a]")
                print(f"  (sem som de transição: coloque sfx/{C.SFX_TRANSICAO}.mp3 ou rode ./corte sfx)")
            enc_cmd += ["-filter_complex", filtro, "-map", "0:v", "-map", "[a]"]
        else:
            enc_cmd += ["-map", "0:v", "-map", "1:a", "-af", C.LOUDNORM]
    if corte.copyright or info["tem_audio"]:
        enc_cmd += ["-c:a", "aac", "-b:a", C.AUDIO_BITRATE, "-ar", "48000"]
    enc_cmd += ["-c:v", "libx264", "-preset", "veryfast" if rapido else C.PRESET, "-crf", str(C.CRF + (5 if rapido else 0)),
                "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart", "-shortest", str(destino)]
    enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE)
    tam = W * H * 3
    t0 = time.time()
    feitos = 0
    n_total = int(total * fps)
    for parte in partes:
        eh_gancho = parte is gancho
        dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{parte.inicio:.3f}", "-i", str(video),
                                "-t", f"{parte.dur:.3f}", "-vf", f"fps={fps},scale={W}:{H}",
                                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        k = 0
        while True:
            buf = dec.stdout.read(tam)
            if len(buf) < tam:
                break
            frame = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
            t_rel = k / fps
            plano, cx, cy, ch = E.crop_em(parte.planos, parte.inicio + t_rel)
            quadro = compor(frame, plano, cx, cy, ch, parte.ajustar_yc)
            parte.sobrepor(quadro, t_rel, preview, gancho=eh_gancho)
            if eh_gancho:  # flash branco saindo do gancho
                quadro = _flash(quadro, (t_rel - (parte.dur - C.TRANSICAO_SAIDA)) / C.TRANSICAO_SAIDA)
            elif gancho:   # e entrando no corte
                quadro = _flash(quadro, 1 - t_rel / C.TRANSICAO_ENTRADA)
            enc.stdin.write(quadro.tobytes())
            k += 1
            feitos += 1
            if feitos % int(fps * 10) == 0:
                print(f"    {feitos}/{n_total} quadros ({feitos / (time.time() - t0):.0f} fps)", flush=True)
        dec.wait()
    enc.stdin.close()
    enc.wait()
    if enc.returncode != 0:
        raise SystemExit(f"Falha ao codificar {destino}")
    print(f"  ✔ {destino} ({time.time() - t0:.0f}s)")
    return destino, corte


def quadro_teste(plano_geral, c, tempos, preview=True):
    """Gera PNGs de quadros específicos do corte (verificação rápida de enquadramento/legenda)."""
    video = resolver_video(plano_geral["video"])
    info = probe(video)
    trab = pasta_trabalho(video)
    corte = Corte(plano_geral, c, video, info, trab)
    corte.preparar()
    W, H = info["largura"], info["altura"]
    saidas = []
    pasta = trab / "quadros"
    pasta.mkdir(exist_ok=True)
    if not tempos:
        tempos = list(np.linspace(corte.inicio + 0.5, corte.fim - 0.5, 6))
    for t in tempos:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                              "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True, check=True).stdout
        frame = np.frombuffer(raw[:W * H * 3], np.uint8).reshape(H, W, 3)
        plano, cx, cy, ch = E.crop_em(corte.planos, t)
        q = corte.sobrepor(compor(frame, plano, cx, cy, ch, corte.ajustar_yc), t - corte.inicio, preview)
        p = pasta / f"c{corte.id:02d}_{t:08.2f}.jpg"
        cv2.imwrite(str(p), cv2.cvtColor(q, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
        saidas.append(p)
    # folha única para facilitar a visualização
    ims = [cv2.resize(cv2.imread(str(p)), (360, 640)) for p in saidas]
    while len(ims) % 3:
        ims.append(np.zeros_like(ims[0]))
    linhas = [np.hstack(ims[i:i + 3]) for i in range(0, len(ims), 3)]
    folha = pasta / f"c{corte.id:02d}_folha.jpg"
    cv2.imwrite(str(folha), np.vstack(linhas), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return folha, saidas
