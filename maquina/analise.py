"""Análise visual de um trecho: rostos (YuNet), atividade da boca (MediaPipe
FaceLandmarker -> jawOpen), cortes de cena e centro de movimento.

O resultado é salvo em cache em trabalho/<video>/analise/ para ser reaproveitado.
"""
import subprocess
from pathlib import Path

import cv2
import numpy as np

from config import ANALISE_ALTURA, ANALISE_FPS, MODELOS
from util import ler_json, pasta_trabalho, probe, salvar_json

_yunet = None
_landmarker = None


def _detector(w, h):
    global _yunet
    if _yunet is None:
        _yunet = cv2.FaceDetectorYN.create(str(MODELOS / "face_detection_yunet_2023mar.onnx"), "", (w, h),
                                           score_threshold=0.6, nms_threshold=0.3, top_k=50)
    _yunet.setInputSize((w, h))
    return _yunet


def _marcador():
    global _landmarker
    if _landmarker is None:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision
        opts = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(MODELOS / "face_landmarker.task")),
            running_mode=vision.RunningMode.IMAGE, num_faces=1,
            output_face_blendshapes=True, min_face_detection_confidence=0.3)
        _landmarker = vision.FaceLandmarker.create_from_options(opts)
    return _landmarker


def _abertura_boca(frame_rgb, box):
    """Retorna jawOpen (0..1) do rosto em `box` ou None."""
    import mediapipe as mp
    x, y, w, h = box
    m = 0.45
    x0, y0 = int(max(0, x - w * m)), int(max(0, y - h * m))
    x1, y1 = int(min(frame_rgb.shape[1], x + w * (1 + m))), int(min(frame_rgb.shape[0], y + h * (1 + m)))
    if x1 - x0 < 20 or y1 - y0 < 20:
        return None
    crop = frame_rgb[y0:y1, x0:x1]
    escala = 256 / max(crop.shape[:2])
    crop = cv2.resize(crop, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)
    img = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(crop))
    r = _marcador().detect(img)
    if not r.face_blendshapes:
        return None
    bs = {c.category_name: c.score for c in r.face_blendshapes[0]}
    return float(bs.get("jawOpen", 0.0) + 0.5 * bs.get("mouthFunnel", 0.0))


VERSAO = 2  # muda quando o formato da análise muda (invalida cache)
FW, FH = 192, 108  # resolução do fluxo óptico


def _fluxo(prev, atual):
    """Movimento próprio dos objetos (fluxo óptico menos o movimento da câmera).
    Ignora faixas de HUD (topo 10% e base 20%: estrelas, minimapa). Retorna (x, y, energia, espalhamento)."""
    flow = cv2.calcOpticalFlowFarneback(prev, atual, None, 0.5, 3, 13, 3, 5, 1.1, 0)
    glob = np.median(flow.reshape(-1, 2), axis=0)
    res = np.linalg.norm(flow - glob, axis=2)
    y0, y1 = int(FH * 0.10), int(FH * 0.80)
    res = res[y0:y1]
    res[res < 1.0] = 0
    e = float(res.sum())
    if e <= 0:
        return 0.5, 0.5, 0.0, 1.0
    col = res.sum(axis=0)
    lin = res.sum(axis=1)
    xs = (np.arange(FW) + 0.5) / FW
    ys = (np.arange(y0, y1) + 0.5) / FH
    mx = float((col * xs).sum() / e)
    my = float((lin * ys).sum() / e)
    esp = float(np.sqrt((col * (xs - mx) ** 2).sum() / e))  # 0 = ação concentrada, ~0.29 = espalhada
    return mx, my, float(res.mean()), esp


def analisar(video: Path, inicio: float, fim: float, rostos: bool = True, forcar: bool = False,
             fps: int = ANALISE_FPS) -> dict:
    trab = pasta_trabalho(video) / "analise"
    trab.mkdir(exist_ok=True)
    cache = trab / f"a{VERSAO}_{inicio:.2f}_{fim:.2f}_{int(rostos)}_{fps}.json"
    if cache.exists() and not forcar:
        return ler_json(cache)

    info = probe(video)
    ah = min(ANALISE_ALTURA, info["altura"])
    aw = int(round(info["largura"] * ah / info["altura"] / 2) * 2)
    escala = info["altura"] / ah  # para converter p/ coordenadas da fonte
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{inicio:.3f}", "-i", str(video), "-t", f"{fim - inicio:.3f}",
           "-vf", f"fps={fps},scale={aw}:{ah}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    tam = aw * ah * 3
    amostras = []
    prev_hist = None
    prev_small = None
    k = 0
    while True:
        buf = proc.stdout.read(tam)
        if len(buf) < tam:
            break
        frame = np.frombuffer(buf, np.uint8).reshape(ah, aw, 3)
        t = inicio + k / fps
        k += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        # corte de cena
        hsv = cv2.cvtColor(cv2.resize(frame, (96, 54)), cv2.COLOR_RGB2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        cena = 0.0 if prev_hist is None else float(cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA))
        prev_hist = hist
        # movimento
        small = cv2.resize(gray, (FW, FH), interpolation=cv2.INTER_AREA)
        mov_x, mov_y, mov_e, esp = 0.5, 0.5, 0.0, 1.0
        if prev_small is not None and cena < 0.45:
            mov_x, mov_y, mov_e, esp = _fluxo(prev_small, small)
        prev_small = small
        faces = []
        if rostos:
            _, det = _detector(aw, ah).detect(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            if det is not None:
                for d in det:
                    x, y, w, h, score = float(d[0]), float(d[1]), float(d[2]), float(d[3]), float(d[14])
                    if h < 24:
                        continue
                    jaw = _abertura_boca(frame, (x, y, w, h))
                    faces.append({"x": round(x * escala, 1), "y": round(y * escala, 1),
                                  "w": round(w * escala, 1), "h": round(h * escala, 1),
                                  "s": round(score, 3), "jaw": None if jaw is None else round(jaw, 4)})
        amostras.append({"t": round(t, 3), "cena": round(cena, 4), "mx": round(mov_x, 4), "my": round(mov_y, 4),
                         "me": round(mov_e, 4), "esp": round(esp, 4), "faces": faces})
    proc.wait()
    _rastrear(amostras)
    dados = {"inicio": inicio, "fim": fim, "fps": fps, "largura": info["largura"],
             "altura": info["altura"], "amostras": amostras}
    salvar_json(cache, dados)
    return dados


def _rastrear(amostras):
    """Atribui ids estáveis aos rostos (rastreador guloso por distância)."""
    trilhas = {}  # id -> (cx, cy, h, ultimo_t)
    prox = 0
    for a in amostras:
        usados = set()
        for f in sorted(a["faces"], key=lambda f: -f["h"]):
            cx, cy = f["x"] + f["w"] / 2, f["y"] + f["h"] / 2
            melhor, dmin = None, 1e9
            for tid, (tx, ty, th, tt) in trilhas.items():
                if tid in usados or a["t"] - tt > 2.5:
                    continue
                d = np.hypot(cx - tx, cy - ty) / max(th, f["h"])
                if d < dmin and d < 0.9 and 0.6 < f["h"] / th < 1.6:
                    melhor, dmin = tid, d
            if melhor is None:
                melhor = prox
                prox += 1
            usados.add(melhor)
            trilhas[melhor] = (cx, cy, f["h"], a["t"])
            f["id"] = melhor


def energia_audio(video: Path, passo: float = 0.5) -> np.ndarray:
    """Loudness (dB RMS) do áudio ORIGINAL a cada `passo` s (cache em trabalho/<video>/analise/)."""
    trab = pasta_trabalho(video) / "analise"
    trab.mkdir(exist_ok=True)
    cache = trab / f"audio_rms_{passo}.npy"
    if cache.exists():
        return np.load(cache)
    sr = 8000
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(sr),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    n = int(sr * passo)
    blocos = a[: len(a) // n * n].reshape(-1, n)
    db = 20 * np.log10(np.sqrt((blocos ** 2).mean(axis=1)) + 1e-5)
    np.save(cache, db)
    return db
