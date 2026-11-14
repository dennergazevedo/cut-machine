import json
import re
import subprocess
import unicodedata
from fractions import Fraction
from pathlib import Path

from config import ENTRADA, RAIZ, TRABALHO, SAIDA


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:60] or "video"


def resolver_video(nome: str) -> Path:
    """Aceita caminho absoluto/relativo ou nome de arquivo dentro de entrada/."""
    for p in (Path(nome), RAIZ / nome, ENTRADA / nome):
        if p.exists():
            return p.resolve()
    cands = [p for p in ENTRADA.iterdir() if nome.lower() in p.name.lower()]
    if len(cands) == 1:
        return cands[0]
    raise SystemExit(f"Vídeo não encontrado: {nome} (procure em {ENTRADA})")


def pasta_trabalho(video: Path) -> Path:
    p = TRABALHO / slug(video.stem)
    p.mkdir(parents=True, exist_ok=True)
    return p


def pasta_saida(video: Path) -> Path:
    p = SAIDA / slug(video.stem)
    p.mkdir(parents=True, exist_ok=True)
    return p


def probe(video: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(video)],
        capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    fps = float(Fraction(v.get("avg_frame_rate") or v["r_frame_rate"])) if v.get("avg_frame_rate", "0/0") != "0/0" \
        else float(Fraction(v["r_frame_rate"]))
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    if abs(rot) in (90, 270):
        w, h = h, w
    return {
        "largura": w, "altura": h, "fps": fps,
        "duracao": float(d["format"]["duration"]),
        "tem_audio": a is not None,
    }


def fmt(t: float) -> str:
    t = max(0.0, t)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:05.2f}" if h else f"{int(m):02d}:{s:05.2f}"


def parse_tempo(v) -> float:
    """Aceita 123.4, "123.4", "02:03.4", "1:02:03"."""
    if isinstance(v, (int, float)):
        return float(v)
    partes = [float(p) for p in str(v).strip().split(":")]
    t = 0.0
    for p in partes:
        t = t * 60 + p
    return t


def ler_json(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def salvar_json(p: Path, dados):
    Path(p).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
