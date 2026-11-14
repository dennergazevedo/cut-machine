"""Máquina de Cortes – CLI.  Uso: ./corte <comando> ...   (veja CLAUDE.md)"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as C  # noqa: E402
from util import fmt, ler_json, pasta_saida, pasta_trabalho, probe, resolver_video, salvar_json  # noqa: E402


def cmd_baixar(a):
    saida = C.ENTRADA / "%(title).80s.%(ext)s"
    subprocess.run([sys.executable, "-m", "yt_dlp", "-f", "bv*[height<=2160]+ba/b", "--merge-output-format", "mp4",
                    "-o", str(saida), a.url], check=True)


def cmd_info(a):
    v = resolver_video(a.video)
    i = probe(v)
    print(f"{v.name}: {i['largura']}x{i['altura']} @ {i['fps']:.2f}fps, {fmt(i['duracao'])} ({i['duracao']:.1f}s), "
          f"áudio={'sim' if i['tem_audio'] else 'não'}")
    print(f"pasta de trabalho: {pasta_trabalho(v)}")
    if i["duracao"] > C.VIDEO_LONGO:
        print("Vídeo longo (+5min): gerar vários cortes com as partes interessantes.")


def cmd_transcrever(a):
    from transcrever import transcrever
    transcrever(resolver_video(a.video), None if a.idioma == "auto" else a.idioma, a.forcar)


def cmd_folha(a):
    """Folha de contato (miniaturas com timestamp) para inspecionar o vídeo visualmente."""
    import cv2
    import numpy as np
    v = resolver_video(a.video)
    info = probe(v)
    ini = a.inicio or 0.0
    fim = a.fim or info["duracao"]
    n = a.n
    ts = np.linspace(ini, fim, n + 2)[1:-1] if n > 1 else [ini]
    ims = []
    for t in ts:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(v), "-frames:v", "1",
                              "-vf", "scale=480:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                             capture_output=True).stdout
        im = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if im is None:
            continue
        cv2.putText(im, fmt(t), (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
        cv2.putText(im, fmt(t), (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        ims.append(im)
    h = min(i.shape[0] for i in ims)
    ims = [i[:h] for i in ims]
    col = 4
    while len(ims) % col:
        ims.append(np.zeros_like(ims[0]))
    folha = np.vstack([np.hstack(ims[i:i + col]) for i in range(0, len(ims), col)])
    p = pasta_trabalho(v) / f"folha_{int(ini)}_{int(fim)}.jpg"
    cv2.imwrite(str(p), folha, [cv2.IMWRITE_JPEG_QUALITY, 80])
    print(p)


def cmd_cenas(a):
    """Lista os cortes de cena (útil para trailers e vídeos editados)."""
    from analise import analisar
    v = resolver_video(a.video)
    info = probe(v)
    d = analisar(v, a.inicio or 0.0, a.fim or info["duracao"], rostos=False)
    cortes = [s["t"] for s in d["amostras"] if s["cena"] > C.CENA_LIMIAR]
    linhas = []
    ant = d["inicio"]
    for t in cortes + [d["fim"]]:
        linhas.append(f"{fmt(ant)} -> {fmt(t)} ({t - ant:.1f}s)")
        ant = t
    p = pasta_trabalho(v) / "cenas.txt"
    p.write_text("\n".join(linhas), encoding="utf-8")
    print("\n".join(linhas))
    print(f"\n{len(linhas)} cenas -> {p}")


def cmd_acao(a):
    """Ranking dos momentos de mais ação: barulho do áudio original + movimento próprio dos objetos
    (fluxo óptico sem o movimento da câmera) + ritmo de cortes de cena."""
    import numpy as np
    from analise import analisar, energia_audio
    v = resolver_video(a.video)
    info = probe(v)
    dur = info["duracao"]
    print("analisando movimento do vídeo inteiro (cache após a 1ª vez)...")
    d = analisar(v, 0.0, dur, rostos=False)
    n = int(dur)
    mov = np.zeros(n); cortes = np.zeros(n); cnt = np.zeros(n)
    for s_ in d["amostras"]:
        k = min(n - 1, int(s_["t"]))
        mov[k] += s_["me"]; cnt[k] += 1
        cortes[k] += s_["cena"] > C.CENA_LIMIAR
    mov /= np.maximum(cnt, 1)
    db = energia_audio(v, 0.5)
    db = db[: 2 * n] if len(db) >= 2 * n else np.pad(db, (0, 2 * n - len(db)), constant_values=db.min())
    alto = db.reshape(n, 2).mean(axis=1)
    trans = np.concatenate([[0], np.clip(np.diff(db), 0, None)]).reshape(n, 2).max(axis=1)
    z = lambda x: (x - x.mean()) / (x.std() + 1e-9)
    score = 0.35 * z(alto) + 0.2 * z(trans) + 0.3 * z(mov) + 0.15 * z(cortes)
    score[alto < np.percentile(alto, 5)] -= 1.0  # silêncio/tela preta
    jan = a.janela
    acum = np.convolve(score, np.ones(jan), mode="valid") / jan
    usado = np.zeros(n, bool)
    lim_cena = [s_["t"] for s_ in d["amostras"] if s_["cena"] > C.CENA_LIMIAR]
    linhas = []
    for k in np.argsort(-acum):
        if len(linhas) >= a.top:
            break
        if usado[max(0, k - 3): k + jan + 3].any():
            continue
        ini = float(k)
        perto = [c for c in lim_cena if abs(c - ini) <= 2.0]
        if perto:
            ini = min(perto, key=lambda c: abs(c - ini))
        usado[k: k + jan] = True
        pico = k + int(np.argmax(score[k:k + jan]))
        linhas.append((ini, ini + jan, acum[k], pico, alto[k:k + jan].mean(), mov[k:k + jan].mean()))
    txt = [f"Top {len(linhas)} janelas de {jan}s com mais ação (score médio; pico; áudio dB; movimento)"]
    for i, (ini, fim, sc, pico, al, mv) in enumerate(sorted(linhas, key=lambda l: -l[2]), 1):
        txt.append(f"{i:2d}. {fmt(ini)} -> {fmt(fim)}  ({ini:.1f}-{fim:.1f})  score={sc:+.2f}  pico={fmt(pico)}  "
                   f"audio={al:.1f}dB  mov={mv:.2f}")
    p = pasta_trabalho(v) / "acao.txt"
    p.write_text("\n".join(txt), encoding="utf-8")
    print("\n".join(txt))
    print(f"-> {p}")


def cmd_sfx(a):
    """Gera um efeito sonoro na ElevenLabs (Sound Effects API) e salva em sfx/<nome>.mp3 para reaproveitar.
    Chave: variável ELEVENLABS_API_KEY ou arquivo .env na raiz (ELEVENLABS_API_KEY=...)."""
    import json as _json
    import os
    import urllib.request
    chave = os.environ.get("ELEVENLABS_API_KEY")
    env = C.RAIZ / ".env"
    if not chave and env.exists():
        for linha in env.read_text().splitlines():
            if linha.strip().startswith("ELEVENLABS_API_KEY="):
                chave = linha.split("=", 1)[1].strip().strip('"').strip("'")
    if not chave:
        raise SystemExit("Defina ELEVENLABS_API_KEY (variável de ambiente ou .env na raiz do projeto).")
    corpo = {"text": a.prompt, "prompt_influence": a.influencia}
    if a.duracao:
        corpo["duration_seconds"] = a.duracao
    req = urllib.request.Request("https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_128",
                                 data=_json.dumps(corpo).encode(), method="POST",
                                 headers={"xi-api-key": chave, "Content-Type": "application/json"})
    C.SFX.mkdir(exist_ok=True)
    destino = C.SFX / f"{a.nome}.mp3"
    with urllib.request.urlopen(req, timeout=120) as r:
        destino.write_bytes(r.read())
    (C.SFX / f"{a.nome}.txt").write_text(f"ElevenLabs Sound Effects\nprompt: {a.prompt}\nduracao: {a.duracao}\n",
                                         encoding="utf-8")
    print(f"Salvo: {destino}")


def cmd_plano(a):
    v = resolver_video(a.video)
    p = pasta_trabalho(v) / "plano.json"
    if p.exists() and not a.forcar:
        raise SystemExit(f"Já existe: {p} (use --forcar para sobrescrever)")
    salvar_json(p, {
        "video": v.name,
        "tipo": a.tipo,
        "contexto": "",
        "glossario": {},
        "cortes": [{
            "id": 1, "nome": "exemplo", "inicio": 0, "fim": 60,
            "titulo": None, "enquadramento": None,
            "post": {"titulo": "", "descricao": "", "hashtags": []},
        }],
    })
    print(p)


def _carregar_plano(caminho):
    p = Path(caminho)
    if not p.exists():
        p = pasta_trabalho(resolver_video(caminho)) / "plano.json"
    return p, ler_json(p)


def _selecionar(plano, ids):
    if not ids:
        return plano["cortes"]
    alvo = {int(x) for x in ids.split(",")}
    return [c for c in plano["cortes"] if int(c["id"]) in alvo]


def cmd_quadros(a):
    from render import quadro_teste
    _, plano = _carregar_plano(a.plano)
    for c in _selecionar(plano, a.cortes):
        tempos = [float(x) for x in a.t.split(",")] if a.t else None
        folha, _ = quadro_teste(plano, c, tempos, preview=not a.sem_safearea)
        print(folha)


def cmd_traduzir(a):
    """Exporta as frases dos cortes para tradução PT-BR (vídeos em outro idioma)."""
    from render import Corte, carregar_traducao
    _, plano = _carregar_plano(a.plano)
    v = resolver_video(plano["video"])
    info, trab = probe(v), pasta_trabalho(v)
    for c in _selecionar(plano, a.cortes):
        corte = Corte(plano, c, v, info, trab)
        if corte.idioma == "pt":
            print(f"Corte {corte.id}: vídeo já em português, nada a traduzir.")
            continue
        p, faltando = carregar_traducao(corte, so_exportar=True)
        print(f"Corte {corte.id}: {p} ({faltando} frase(s) sem tradução)")


def cmd_renderizar(a):
    from render import renderizar_corte
    caminho, plano = _carregar_plano(a.plano)
    feitos = []
    for c in _selecionar(plano, a.cortes):
        destino, corte = renderizar_corte(plano, c, rapido=a.rapido, preview=a.preview, forcar=a.forcar)
        feitos.append((c, destino, corte))
    if feitos and not a.preview:
        _escrever_resumo(plano, feitos)


def _escrever_resumo(plano, feitos):
    """Gera saida/<video>/SEO.md: por corte -> nome do arquivo, título otimizado p/ SEO e descrição."""
    v = resolver_video(plano["video"])
    md = pasta_saida(v) / "SEO.md"
    blocos = {}
    if md.exists():  # preserva cortes renderizados anteriormente
        atual = None
        for linha in md.read_text(encoding="utf-8").splitlines(keepends=True):
            if linha.startswith("## "):
                atual = linha
                blocos[atual] = ""
            elif atual:
                blocos[atual] += linha
    sem_seo = []
    for c, destino, corte in feitos:
        post = c.get("post", {})
        for k in [k for k in blocos if k.startswith(f"## {corte.id:02d}_")]:
            del blocos[k]
        if not post.get("titulo") or not post.get("descricao"):
            sem_seo.append(corte.id)
        tags = " ".join(post.get("hashtags", []))
        blocos[f"## {destino.name}\n"] = (
            f"\n**Arquivo:** `{destino.name}`\n\n"
            f"**Título:** {post.get('titulo', '')}\n\n"
            f"**Descrição:**\n\n{post.get('descricao', '')}\n" + (f"\n{tags}\n" if tags else "") + "\n---\n\n")
    texto = f"# SEO – {v.name}\n\n" + "".join(k + blocos[k] for k in sorted(blocos))
    md.write_text(texto, encoding="utf-8")
    print(f"\nSEO: {md}")
    if sem_seo:
        print(f"AVISO: cortes sem post.titulo/post.descricao no plano: {sem_seo}")


def cmd_safearea(a):
    from safearea import gerar
    gerar()


def main():
    ap = argparse.ArgumentParser(prog="corte", description="Máquina de Cortes – vídeos verticais 9:16")
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("baixar", help="baixa vídeo de URL para entrada/")
    s.add_argument("url"); s.set_defaults(f=cmd_baixar)
    s = sp.add_parser("info", help="informações do vídeo")
    s.add_argument("video"); s.set_defaults(f=cmd_info)
    s = sp.add_parser("transcrever", help="transcreve (whisper) -> trabalho/<video>/transcricao.txt")
    s.add_argument("video"); s.add_argument("--idioma", default="auto"); s.add_argument("--forcar", action="store_true")
    s.set_defaults(f=cmd_transcrever)
    s = sp.add_parser("folha", help="folha de miniaturas para ver o vídeo")
    s.add_argument("video"); s.add_argument("--inicio", type=float); s.add_argument("--fim", type=float)
    s.add_argument("--n", type=int, default=16); s.set_defaults(f=cmd_folha)
    s = sp.add_parser("cenas", help="lista cortes de cena")
    s.add_argument("video"); s.add_argument("--inicio", type=float); s.add_argument("--fim", type=float)
    s.set_defaults(f=cmd_cenas)
    s = sp.add_parser("acao", help="ranking dos momentos de mais ação (áudio + movimento + cortes)")
    s.add_argument("video"); s.add_argument("--janela", type=int, default=35); s.add_argument("--top", type=int, default=12)
    s.set_defaults(f=cmd_acao)
    s = sp.add_parser("sfx", help="gera efeito sonoro na ElevenLabs e salva em sfx/")
    s.add_argument("prompt"); s.add_argument("--nome", default="transicao")
    s.add_argument("--duracao", type=float, default=1.2); s.add_argument("--influencia", type=float, default=0.5)
    s.set_defaults(f=cmd_sfx)
    s = sp.add_parser("plano", help="cria plano.json modelo")
    s.add_argument("video"); s.add_argument("--tipo", default="podcast",
                                            choices=["podcast", "entrevista", "jogo", "trailer", "editado", "outro"])
    s.add_argument("--forcar", action="store_true"); s.set_defaults(f=cmd_plano)
    s = sp.add_parser("quadros", help="gera quadros de teste (com safe area) dos cortes")
    s.add_argument("plano"); s.add_argument("--cortes"); s.add_argument("--t", help="tempos absolutos, ex: 12.5,40")
    s.add_argument("--sem-safearea", action="store_true"); s.set_defaults(f=cmd_quadros)
    s = sp.add_parser("traduzir", help="exporta frases p/ tradução PT-BR (vídeo em outro idioma)")
    s.add_argument("plano"); s.add_argument("--cortes"); s.set_defaults(f=cmd_traduzir)
    s = sp.add_parser("renderizar", help="renderiza os cortes do plano")
    s.add_argument("plano"); s.add_argument("--cortes", help="ids, ex: 1,3")
    s.add_argument("--rapido", action="store_true"); s.add_argument("--preview", action="store_true",
                                                                     help="desenha a safe area no vídeo")
    s.add_argument("--forcar", action="store_true", help="ignora validação de duração"); s.set_defaults(f=cmd_renderizar)
    s = sp.add_parser("safearea", help="regenera imagens de referência da safe area")
    s.set_defaults(f=cmd_safearea)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
