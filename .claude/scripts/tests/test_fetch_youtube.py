# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""
Test di fetch_youtube.py. Solo le funzioni pure e la cartella finta in tmp: nessuna chiamata a
YouTube, nessun yt-dlp.

    python3 .claude/scripts/tests/test_fetch_youtube.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import fetch_youtube as fy  # noqa: E402

OK, KO = "[OK ]", "[FAIL]"
results: list[tuple[bool, str]] = []


def check(cond: bool, label: str) -> None:
    results.append((bool(cond), label))
    print(f"  {OK if cond else KO} {label}")


def track(lang: str) -> list[dict]:
    return [{"ext": "vtt", "url": f"u/{lang}.vtt"}, {"ext": "json3", "url": f"u/{lang}.json3"}]


def video(**extra) -> dict:
    base = {"id": "abcdefghijk", "title": "Come curare 3 piante di basilico", "channel": "Mario Rossi",
            "uploader_url": "https://www.youtube.com/@mario", "upload_date": "20300308",
            "duration": 42, "view_count": 1200, "description": "Iscriviti al canale"}
    return {**base, **extra}


# ---------- lista profili ----------
print("lista profili")
listing = """# Profili esempio
> nota: https://www.youtube.com/@nota-da-ignorare
- https://www.youtube.com/@mario.rossi  canale da seguire
- [Canale](https://m.youtube.com/channel/UCabcdefghijklmnopqrstuv) e https://www.youtube.com/@mario.rossi/videos
- https://www.youtube.com/watch?v=abcdefghijk (un video, non un canale)
- https://www.instagram.com/mario
"""
check(fy.channels(listing) == ["https://www.youtube.com/@mario.rossi",
                               "https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv"],
      "canali estratti in ordine, senza doppioni, senza note né video né altri siti")
check(fy.channels("nessun indirizzo qui") == [], "lista senza canali → vuota")

# ---------- id video ----------
print("id video")
check(fy.video_id("https://www.youtube.com/watch?v=abcdefghijk&t=10s") == "abcdefghijk", "watch?v=")
check(fy.video_id("https://www.youtube.com/watch?list=PL1&v=abcdefghijk") == "abcdefghijk", "v= non primo parametro")
check(fy.video_id("https://youtu.be/abcdefghijk?si=x") == "abcdefghijk", "youtu.be")
check(fy.video_id("https://www.youtube.com/shorts/abcdefghijk") == "abcdefghijk", "shorts/")
check(fy.video_id("https://www.youtube.com/@mario") is None, "un canale non è un video")

# ---------- scelta della traccia ----------
print("scelta della traccia")
auto_it = {"it-orig": track("it-orig"), "it": track("it"), "en": track("en")}
check(fy.pick_track(video(language="it", automatic_captions=auto_it)) == ("it", True, "u/it-orig.json3", False),
      "solo automatici → traccia originale, non la traduzione")
check(fy.pick_track(video(language="it", subtitles={"en": track("en"), "it": track("it")},
                          automatic_captions=auto_it)) == ("it", False, "u/it.json3", False),
      "lingua dichiarata + tracce del creator → quella nella lingua parlata")
check(fy.pick_track(video(language="en", subtitles={"en-US": track("en-US")})) == ("en-US", False, "u/en-US.json3", False),
      "en-US vale come en")
check(fy.pick_track(video(language="it", subtitles={"en": track("en")})) is None,
      "lingua dichiarata ma solo una traduzione caricata → niente (non si salva la traduzione)")
check(fy.pick_track(video(automatic_captions={"es-orig": track("es-orig"), "it": track("it")}))
      == ("es", True, "u/es-orig.json3", False),
      "language assente ma traccia -orig presente → lingua dedotta da YouTube, non marcata")
check(fy.pick_track(video(subtitles={"en": track("en")})) == ("en", False, "u/en.json3", False),
      "lingua non dichiarata, una sola traccia del creator → quella")
many = video(subtitles={"ar": track("ar"), "my": track("my"), "en": track("en"), "fr": track("fr")})
check(fy.ambiguous(many) and fy.pick_track(many) is None,
      "lingua non dichiarata e più tracce, nessuna preferenza → niente (mai la prima a caso)")
check(fy.pick_track(many, ["it", "en"]) == ("en", False, "u/en.json3", True),
      "con preferenza it,en → inglese, marcata come dedotta")
check(fy.pick_track(many, ["fr", "it", "en"])[0] == "fr", "la lingua del canale passa davanti a --lingua")
check(fy.pick_track(video(subtitles={"live_chat": track("x")})) is None, "la chat live non è una traccia")
check(fy.pick_track(video()) is None, "nessuna traccia → None")

# ---------- json3 ----------
print("json3")
events = [
    {"tStartMs": 0, "dDurationMs": 4000, "id": 1},
    {"tStartMs": 80, "segs": [{"utf8": "ciao"}, {"utf8": " a", "tOffsetMs": 200}, {"utf8": " tutti"}]},
    {"tStartMs": 2000, "aAppend": 1, "segs": [{"utf8": "\n"}]},
    {"tStartMs": 16500, "segs": [{"utf8": "seconda\nriga"}]},
]
check(fy.phrases(events) == [(0.08, "ciao a tutti"), (16.5, "seconda riga")],
      "eventi senza testo e di solo a capo scartati, a capo interni → spazi")

# ---------- render ----------
print("render")
info = video(language="it", lang="it", auto=True, guessed=False, like_count=30,
             phrases=[(0.0, "Il basilico vuole luce"), (16.0, "e poca acqua"), (31.0, "iscriviti al canale")])
text = fy.render(info, "shorts", today="2030-03-10")
check("youtube: https://www.youtube.com/watch?v=abcdefghijk" in text, "indirizzo nel frontmatter")
check("formato: short" in text and "pubblicato: 2030-03-08" in text and 'durata: "00:42"' in text,
      "formato, data e durata")
check("visualizzazioni: 1200" in text and "like: 30" in text and "commenti:" not in text,
      "numeri presenti scritti, quelli assenti omessi")
check("**[00:00]** Il basilico vuole luce e poca acqua" in text and "**[00:31]** iscriviti al canale" in text,
      "video corto → blocchi da 15 secondi")
check("lingua_dedotta" not in text and "trascrizione: automatica YouTube" in text, "traccia automatica dichiarata")
check("```text\nIscriviti al canale\n```" in text, "descrizione chiusa in un blocco di testo")
long_info = video(duration=900, lang="en", auto=False, guessed=True, description="a ``` b " + "x" * 2000,
                  phrases=[(0.0, "uno"), (30.0, "due"), (61.0, "tre"), (70.0, "quattro")])
long_text = fy.render(long_info, "videos", today="2030-03-10")
check("**[00:00]** uno due tre" in long_text and "**[01:10]** quattro" in long_text, "video lungo → blocchi da 60 secondi")
check("lingua_dedotta:" in long_text and "sottotitoli caricati dal creator" in long_text, "lingua dedotta dichiarata")
check("a ''' b" in long_text and long_text.count("```") == 2 and "[…]" in long_text,
      "descrizione: i tre apici non rompono il blocco, il taglio è segnalato")
check("\u2014" not in text and "\u2013" not in text, "nessun trattino lungo nel testo generato")
check(fy.is_short(video(media_type="short"), None) and not fy.is_short(video(media_type="video"), None)
      and fy.is_short(video(width=1080, height=1920), None) and not fy.is_short(video(width=1920, height=1080), None),
      "short riconosciuto anche senza scheda (media_type, poi verticale e corto)")

# ---------- cartella: già scaricati, lingua del canale, nome file ----------
print("cartella")
root = Path(tempfile.mkdtemp(prefix="yt-test-"))
check(fy.library(root / "non-esiste") == (set(), {}), "cartella assente → niente, nessun errore")
first = fy.target(root, info)
check(first.name == "2030-03-08-yt-mario-rossi-come-curare-3-piante-di-basilico.md", "nome: data, canale, titolo")
first.write_text(text, encoding="utf-8")
guessed = video(id="ZZZZZZZZZZZ", lang="en", auto=False, guessed=True, phrases=[(0.0, "x")])
second = fy.target(root, guessed)
check(second.name.endswith("-ZZZZZZZZZZZ.md"), "stesso giorno e stesso titolo → non sovrascrive, aggiunge l'id")
second.write_text(fy.render(guessed, None, today="2030-03-10"), encoding="utf-8")
(root / "altra-nota.md").write_text("---\ntipo: nota\n---\nhttps://www.youtube.com/watch?v=AAAAAAAAAAA\n", encoding="utf-8")
ids, langs = fy.library(root)
check(ids == {"abcdefghijk", "ZZZZZZZZZZZ"}, "già scaricati letti dal frontmatter, le altre note non contano")
check(dict(langs) == {"https://www.youtube.com/@mario": {"it": 1}},
      "lingua del canale imparata dai file salvati, le dedotte non fanno testo")

# ---------- cleanup + esito ----------
shutil.rmtree(root, ignore_errors=True)

passed = sum(1 for ok, _ in results if ok)
total = len(results)
print(f"\n{passed}/{total} test passati")
sys.exit(0 if passed == total else 1)
