import os
os.environ["CUDA_MODULE_LOADING"] = "LAZY"
import cv2
import torch
import numpy as np
from insightface.app import FaceAnalysis
import time
import threading
import requests
import urllib.parse
torch.backends.cudnn.benchmark = True
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
if not torch.cuda.is_available():
    raise RuntimeError("CUDA torch saknas, installera torch cu126")
device = torch.device("cuda:0")
torch.cuda.set_device(0)
frame_count = 0
start_time = time.time()
fps = 0.0
personer_mapp = "personer"
likhetsgräns = 0.20
face_stride = 2
online_tröskel = 0.55
online_cooldown = 60.0
online_min_bredd = 90
online_min_score = 70
facecheck_token = os.environ.get("FKL8u0G8PJjM55PPFkGzAkeUf/eq+5jRTmZqjvmCPm5YD+mag1XpO2/JjCNWyn5bWB1XLuNFrSVA=", "")
facecheck_demo = os.environ.get("FACECHECK_DEMO", "1") == "1"
facecheck_site = "https://facecheck.id"
ansiktsapp = FaceAnalysis(name="buffalo_l", providers=["CUDAExecutionProvider", "CPUExecutionProvider"], allowed_modules=["detection", "recognition"])
ansiktsapp.prepare(ctx_id=0, det_size=(320, 320))
dummy = np.zeros((480, 640, 3), dtype=np.uint8)
ansiktsapp.get(dummy)
def hämta_ansikte(bildsökvag):
    bild = cv2.imread(bildsökvag)
    if bild is None:
        return None
    ansikten = ansiktsapp.get(bild)
    if len(ansikten) == 0:
        return None
    vektor = ansikten[0].embedding.astype(np.float32)
    vektor = vektor / np.linalg.norm(vektor).clip(min=1e-8)
    return vektor
kanda_personer = {}
for filnamn in os.listdir(personer_mapp):
    if not filnamn.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        continue
    bildsokvag = os.path.join(personer_mapp, filnamn)
    namn = os.path.splitext(filnamn)[0]
    ansiktsvektor = hämta_ansikte(bildsokvag)
    if ansiktsvektor is not None:
        kanda_personer[namn] = ansiktsvektor
    else:
        print("fackadd")
kanda_namn = list(kanda_personer.keys())
if len(kanda_namn) > 0:
    staplade = np.stack([kanda_personer[n] for n in kanda_namn], axis=0).astype(np.float32)
    kand_matris = torch.from_numpy(staplade).to(device)
    kand_matris = kand_matris / torch.linalg.norm(kand_matris, dim=1, keepdim=True).clamp_min(1e-8)
else:
    kand_matris = None
def identifiera_ansikte(ansiktsvektor):
    if kand_matris is None or len(kanda_namn) == 0:
        return "Okänd", 0.0
    fraga = torch.from_numpy(np.asarray(ansiktsvektor, dtype=np.float32)).to(device)
    fraga = fraga / torch.linalg.norm(fraga).clamp_min(1e-8)
    likheter = kand_matris @ fraga
    idx = int(torch.argmax(likheter).item())
    basta = float(likheter[idx].item())
    if basta < likhetsgräns:
        return "Okänd", basta
    return kanda_namn[idx], basta
def första_namn_fran_url(url):
    try:
        if not url:
            return ""
        text = urllib.parse.unquote(str(url).strip())
        if not text:
            return ""
        text = text.split("?")[0]
        text = text.split(chr(35))[0]
        lite = text.lower()
        if "wiki" in lite and "/wiki/" in lite:
            delen = lite.split("/wiki/", 1)[1]
            text = delen
        else:
            text = text.rstrip("/")
            if "/" in text:
                text = text.rsplit("/", 1)[1]
        if "." in text:
            text = text.rsplit(".", 1)[0]
        for sep in ("_", "-", "+", "%20", "."):
            text = text.replace(sep, " ")
        delar = [d for d in text.split(" ") if d]
        if not delar:
            return ""
        stopp = ("image", "images", "photo", "photos", "picture", "video", "watch", "profile", "people", "person", "face", "unknown", "default", "avatar", "thumb", "media", "post", "page", "index", "html", "nm", "imdb", "name", "title", "detail", "details")
        for d in delar:
            rent = "".join([c for c in d if c.isalpha()])
            if not rent:
                continue
            if rent.lower() in stopp:
                continue
            if len(rent) < 2 or len(rent) > 25:
                continue
            return rent[:1].upper() + rent[1:].lower()
        return ""
    except Exception:
        return ""
def facecheck_sök(jpg_bytes):
    try:
        if not facecheck_token:
            return []
        headers = {"accept": "application/json", "Authorization": facecheck_token}
        filer = {"images": ("face.jpg", jpg_bytes, "image/jpeg")}
        upp = requests.post(facecheck_site + "/api/upload_pic", headers=headers, files=filer, timeout=30).json()
        if upp.get("error"):
            print(str(upp.get("error")) + " (" + str(upp.get("code")) + ")")
            return []
        id_search = upp.get("id_search")
        if not id_search:
            return []
        nyttolast = {"id_search": id_search, "with_progress": True, "status_only": False, "demo": facecheck_demo}
        for _ in range(60):
            time.sleep(1)
            svar = requests.post(facecheck_site + "/api/search", headers=headers, json=nyttolast, timeout=30).json()
            if svar.get("error"):
                print(str(svar.get("error")) + " (" + str(svar.get("code")) + ")")
                return []
            if svar.get("output"):
                poster = svar.get("output")
                if isinstance(poster, dict):
                    return poster.get("items", [])
                return []
        return []
    except Exception:
        return []
def söka_namn_online(ansiktsbild):
    try:
        if not facecheck_token:
            return ""
        ok, buffert = cv2.imencode(".jpg", ansiktsbild, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok:
            return ""
        poster = facecheck_sök(buffert.tobytes())
        if not poster:
            return ""
        basta = None
        basta_score = -1
        for post in poster:
            try:
                s = int(post.get("score", 0))
            except Exception:
                s = 0
            u = post.get("url", "")
            if s > basta_score and u:
                basta_score = s
                basta = u
        if basta is None or basta_score < online_min_score:
            return ""
        return första_namn_fran_url(basta)
    except Exception:
        return ""
online_las = threading.Lock()
okanda_vektorer = []
okanda_namn = []
okanda_tid = []
okanda_pagar = []
online_samtidiga = [0]
def hitta_okant_spar(vektor):
    norm = float(np.linalg.norm(vektor))
    if norm < 1e-8:
        return -1
    v = (vektor.astype(np.float32) / norm)
    basta_idx = -1
    basta_val = -1.0
    for i, lagrad in enumerate(okanda_vektorer):
        s = float(np.dot(v, lagrad))
        if s > basta_val:
            basta_val = s
            basta_idx = i
    if basta_idx >= 0 and basta_val >= online_tröskel:
        return basta_idx
    okanda_vektorer.append(v)
    okanda_namn.append("")
    okanda_tid.append(0.0)
    okanda_pagar.append(False)
    return len(okanda_vektorer) - 1
def online_uppslag_job(idx, ansiktsbild):
    namn = söka_namn_online(ansiktsbild)
    with online_las:
        okanda_pagar[idx] = False
        online_samtidiga[0] = max(0, online_samtidiga[0] - 1)
        if namn:
            okanda_namn[idx] = namn
        else:
            okanda_tid[idx] = time.time()
def begär_online_namn(idx, ansiktsbild):
    with online_las:
        if idx < 0 or idx >= len(okanda_vektorer):
            return
        if okanda_namn[idx] or okanda_pagar[idx]:
            return
        if (time.time() - okanda_tid[idx]) < online_cooldown:
            return
        if online_samtidiga[0] >= 2:
            return
        if not facecheck_token:
            return
        okanda_pagar[idx] = True
        online_samtidiga[0] += 1
    kopia = ansiktsbild.copy()
    trad = threading.Thread(target=online_uppslag_job, args=(idx, kopia), daemon=True)
    trad.start()
def beskära_ansikte(bild, x1, y1, x2, y2):
    h, b = bild.shape[:2]
    m = 20
    xa = max(0, int(x1) - m)
    ya = max(0, int(y1) - m)
    xb = min(b, int(x2) + m)
    yb = min(h, int(y2) + m)
    if xb <= xa or yb <= ya:
        return None
    return bild[ya:yb, xa:xb]
class SnabbKamera:
    def __init__(self, src=0):
        self.cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 60)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.las = threading.Lock()
        self.ram = None
        self.kor = True
        ok, forsta = self.cap.read()
        if ok:
            self.ram = forsta
        self.trad = threading.Thread(target=self.uppdatera, daemon=True)
        self.trad.start()
    def uppdatera(self):
        while self.kor:
            ok, ny = self.cap.read()
            if not ok:
                time.sleep(0.005)
                continue
            with self.las:
                self.ram = ny
    def read(self):
        with self.las:
            if self.ram is None:
                return False, None
            return True, self.ram.copy()
    def release(self):
        self.kor = False
        try:
            self.cap.release()
        except:
            pass
kamera = SnabbKamera(0)
frame_idx = 0
cachade = []
with torch.inference_mode():
    while True:
        lyckades, bild = kamera.read()
        if not lyckades or bild is None:
            time.sleep(0.002)
            continue
        frame_count += 1
        frame_idx += 1
        elapsed = time.time() - start_time
        if elapsed >= 1.0:
            fps = frame_count / elapsed
            print(f"FPS: {fps:.2f}")
            frame_count = 0
            start_time = time.time()
        gor_face = (frame_idx % face_stride == 0) or (len(cachade) == 0)
        if gor_face:
            ansikten = ansiktsapp.get(bild)
            nya = []
            for ansikte in ansikten:
                x1, y1, x2, y2 = ansikte.bbox.astype(int)
                namn, likhet = identifiera_ansikte(ansikte.embedding)
                spar = -1
                visningsnamn = namn
                if namn == "Okänd":
                    spar = hitta_okant_spar(np.asarray(ansikte.embedding, dtype=np.float32))
                    with online_las:
                        if spar >= 0 and okanda_namn[spar]:
                            visningsnamn = okanda_namn[spar]
                    if spar >= 0 and (not okanda_namn[spar]):
                        bredd = int(x2) - int(x1)
                        if bredd >= online_min_bredd:
                            utsnitt = beskära_ansikte(bild, int(x1), int(y1), int(x2), int(y2))
                            if utsnitt is not None:
                                begär_online_namn(spar, utsnitt)
                nya.append((int(x1), int(y1), int(x2), int(y2), visningsnamn, float(likhet), spar))
            cachade = nya
        else:
            uppdaterade = []
            for x1, y1, x2, y2, visningsnamn, likhet, spar in cachade:
                if spar is not None and spar >= 0:
                    with online_las:
                        if spar < len(okanda_namn) and okanda_namn[spar]:
                            visningsnamn = okanda_namn[spar]
                uppdaterade.append((x1, y1, x2, y2, visningsnamn, likhet, spar))
            cachade = uppdaterade
        for x1, y1, x2, y2, visningsnamn, likhet, spar in cachade:
            if visningsnamn == "Okänd":
                farg = (0, 0, 255)
                text = f"Okänd ({likhet:.2f})"
            else:
                farg = (0, 255, 0)
                text = f"{visningsnamn} ({likhet:.2f})"
            cv2.rectangle(bild, (x1, y1), (x2, y2), farg, 2)
            cv2.putText(bild, text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, farg, 2)
        cv2.putText(bild, f"FPS: {fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        cv2.imshow("ansiktssatan", bild)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
kamera.release()
cv2.destroyAllWindows()
