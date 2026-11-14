"""Transcrição com Whisper (MLX, acelerado no Apple Silicon) com timestamps por palavra."""
import subprocess
from pathlib import Path

from config import TRANSCRICAO_MODELO
from util import fmt, pasta_trabalho, salvar_json, ler_json


def extrair_audio(video: Path, destino: Path):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", str(destino)], check=True)


def transcrever(video: Path, idioma: str | None = None, forcar: bool = False) -> Path:
    import mlx_whisper

    trab = pasta_trabalho(video)
    destino = trab / "transcricao.json"
    if destino.exists() and not forcar:
        print(f"Transcrição já existe: {destino}")
        return destino
    wav = trab / "audio16k.wav"
    extrair_audio(video, wav)
    print(f"Transcrevendo com {TRANSCRICAO_MODELO} (idioma={idioma or 'auto'})...")
    res = mlx_whisper.transcribe(
        str(wav), path_or_hf_repo=TRANSCRICAO_MODELO, word_timestamps=True,
        language=idioma, verbose=False, condition_on_previous_text=False,
        hallucination_silence_threshold=2.0,
    )
    segs = []
    for s in res["segments"]:
        palavras = [{"w": w["word"].strip(), "i": round(w["start"], 3), "f": round(w["end"], 3)}
                    for w in s.get("words", []) if w["word"].strip()]
        if not palavras:
            continue
        segs.append({"i": round(s["start"], 3), "f": round(s["end"], 3), "texto": s["text"].strip(),
                     "palavras": palavras})
    salvar_json(destino, {"idioma": res.get("language"), "segmentos": segs})
    gerar_txt(destino)
    wav.unlink(missing_ok=True)
    return destino


def gerar_txt(json_path: Path):
    """Versão legível (para o Claude ler e escolher os cortes)."""
    d = ler_json(json_path)
    linhas = [f"[{fmt(s['i'])} -> {fmt(s['f'])}] ({s['i']:.1f}-{s['f']:.1f}) {s['texto']}" for s in d["segmentos"]]
    txt = json_path.with_suffix(".txt")
    txt.write_text("\n".join(linhas), encoding="utf-8")
    print(f"Transcrição: {txt} ({len(linhas)} segmentos, idioma={d.get('idioma')})")
    if d.get("idioma") not in (None, "pt"):
        print("ATENÇÃO: vídeo não está em português -> legendas, títulos e textos dos cortes devem ser em PT-BR "
              "(use ./corte traduzir).")
    return txt


def palavras_no_intervalo(trab: Path, inicio: float, fim: float) -> list[dict]:
    p = trab / "transcricao.json"
    if not p.exists():
        return []
    out = []
    for s in ler_json(p)["segmentos"]:
        for w in s["palavras"]:
            if w["f"] > inicio and w["i"] < fim:
                out.append(dict(w))
    return out


def idioma_transcricao(trab: Path) -> str:
    p = trab / "transcricao.json"
    return (ler_json(p).get("idioma") or "pt") if p.exists() else "pt"
