"""Gera as imagens de referência da safe area combinada (1080x1920)."""
from PIL import Image, ImageDraw

import config as C
from util import salvar_json

# Zonas seguras de cada rede (polígonos em 1080x1920)
REDES = {
    "YouTube Shorts": {"cor": (255, 60, 60), "rects": [(60, 380, 960, 1540)]},
    "Instagram Reels": {"cor": (225, 80, 255), "rects": [(40, 230, 1036, 960), (40, 960, 880, 1630)]},
    "TikTok": {"cor": (40, 220, 255), "rects": [(60, 130, 940, 1550)]},
}


def gerar():
    pasta = C.ASSETS / "safearea"
    pasta.mkdir(parents=True, exist_ok=True)
    W, H = C.LARGURA, C.ALTURA
    seg = (C.SAFE_X0, C.SAFE_Y0, C.SAFE_X1, C.SAFE_Y1)
    f_tit = __import__("texto").fonte(C.TITULO_FONTE, 46)
    f_txt = __import__("texto").fonte(C.LEGENDA_FONTE, 30)

    # 1) referência
    img = Image.new("RGB", (W, H), (28, 30, 36))
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle(seg, fill=(40, 200, 110, 70), outline=(40, 230, 120), width=6)
    for k, (nome, r) in enumerate(REDES.items()):
        for rc in r["rects"]:
            d.rectangle(rc, outline=r["cor"] + (255,), width=3)
        d.text((60, 1680 + 40 * k), f"■ {nome}", font=f_txt, fill=r["cor"])
    d.text((60, 1680 + 40 * 3), "■ SAFE AREA COMBINADA (usar esta)", font=f_txt, fill=(40, 230, 120))
    d.text((C.SAFE_CX, C.SAFE_Y0 + 40), f"x {C.SAFE_X0}–{C.SAFE_X1}  ·  y {C.SAFE_Y0}–{C.SAFE_Y1}",
           font=f_txt, fill=(255, 255, 255), anchor="mt")
    d.text((C.SAFE_CX, C.SAFE_CY), "CONTEÚDO\nRELEVANTE", font=f_tit, fill=(255, 255, 255), anchor="mm",
           align="center")
    # exemplo de legenda no limite inferior
    from texto import render_legenda
    import numpy as np
    leg = Image.fromarray(render_legenda("Legenda fica aqui no limite inferior"))
    img.paste(leg, (C.SAFE_CX - leg.width // 2, C.SAFE_Y1 - leg.height), leg)
    d.line((0, C.SAFE_Y1, W, C.SAFE_Y1), fill=(255, 220, 0), width=2)
    d.text((W - 20, C.SAFE_Y1 - 40), f"base das legendas/título y={C.SAFE_Y1}", font=f_txt,
           fill=(255, 220, 0), anchor="rt")
    img.save(pasta / "safearea_referencia.png")

    # 2) overlay transparente para previews
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    vermelho = (255, 0, 0, 70)
    d.rectangle((0, 0, W, C.SAFE_Y0), fill=vermelho)
    d.rectangle((0, C.SAFE_Y1, W, H), fill=vermelho)
    d.rectangle((0, C.SAFE_Y0, C.SAFE_X0, C.SAFE_Y1), fill=vermelho)
    d.rectangle((C.SAFE_X1, C.SAFE_Y0, W, C.SAFE_Y1), fill=vermelho)
    d.rectangle(seg, outline=(40, 255, 120, 230), width=4)
    ov.save(pasta / "safearea_overlay.png")

    salvar_json(pasta / "safearea.json", {
        "resolucao": [W, H],
        "safe_area": {"x0": C.SAFE_X0, "y0": C.SAFE_Y0, "x1": C.SAFE_X1, "y1": C.SAFE_Y1},
        "margens": {"topo": C.SAFE_TOPO, "base": C.SAFE_BASE, "esquerda": C.SAFE_ESQ, "direita": C.SAFE_DIR},
        "redes": {k: v["rects"] for k, v in REDES.items()},
    })
    print(f"Gerado em {pasta}")


if __name__ == "__main__":
    gerar()
