#!/usr/bin/env python3
"""시니어 사연 채널 실측 — 조회수 중앙값·최고·길이를 직접 잰다.

방법: yt-dlp 로 채널의 최근 영상 목록(메타데이터만)을 받아 계산한다.
영상을 내려받지 않고 목록만 본다. 요청 사이에 쉰다.
"""
import json, statistics, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

YTDLP = "/tmp/ytm/bin/yt-dlp"
OUT = Path("/tmp/measure")
OUT.mkdir(exist_ok=True)
N = 50          # 채널마다 최근 몇 편을 볼 것인가
PAUSE = 4       # 요청 사이 쉬는 시간(초)

# (표시 이름, 채널 주소 또는 검색어, 탭)
TARGETS = [
    ("훈작가의 숏드라마",   "https://www.youtube.com/@hoonjak", "shorts"),
    ("훈작가의 숏드라마",   "https://www.youtube.com/@hoonjak", "videos"),
    ("심쿵 숏드라마",       "https://www.youtube.com/@PlayLume", "shorts"),
    ("심쿵 숏드라마",       "https://www.youtube.com/@PlayLume", "videos"),
    ("스토리관",            "https://www.youtube.com/@agh3456", "shorts"),
    ("와우사연",            "search:와우사연 실화사연", "videos"),
    ("인생드라마 한편",      "search:인생드라마 한편", "videos"),
    ("시간이 멈춘 정거장",   "search:시간이 멈춘 정거장 사연", "videos"),
    ("우리인생",            "search:우리인생 사연 라디오", "videos"),
    ("이야기 좋아",          "search:이야기 좋아 사연", "shorts"),
]


def run(args, timeout=180):
    try:
        r = subprocess.run([YTDLP, *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.stdout
    except subprocess.TimeoutExpired:
        return ""


def resolve(term):
    """검색어로 채널 주소를 찾는다. 이름이 가장 잘 맞는 것을 고른다."""
    name = term.split(":", 1)[1]
    out = run(["--flat-playlist", "--playlist-end", "5", "--socket-timeout", "20",
               "--print", "%(channel)s\t%(channel_url)s", f"ytsearch5:{name}"])
    best = None
    for line in out.strip().splitlines():
        if "\t" not in line:
            continue
        ch, url = line.split("\t", 1)
        key = name.split()[0]
        if key and key in ch:
            best = (ch, url.strip())
            break
        if best is None:
            best = (ch, url.strip())
    return best


def fetch(url, tab):
    out = run(["--flat-playlist", "--playlist-end", str(N), "--socket-timeout", "20",
               "--print", "%(id)s\t%(view_count)s\t%(duration)s\t%(title)s",
               f"{url}/{tab}"])
    rows = []
    for line in out.strip().splitlines():
        p = line.split("\t")
        if len(p) < 4:
            continue
        try:
            views = int(p[1])
        except ValueError:
            continue
        try:
            dur = int(float(p[2]))
        except ValueError:
            dur = None
        rows.append({"id": p[0], "views": views, "sec": dur, "title": p[3][:70]})
    return rows


results = []
for label, target, tab in TARGETS:
    url = target
    channel_name = label
    if target.startswith("search:"):
        found = resolve(target)
        if not found:
            print(f"  {label} ({tab}) — 채널을 찾지 못함", flush=True)
            continue
        channel_name, url = found
        time.sleep(PAUSE)
    rows = fetch(url, tab)
    if not rows:
        print(f"  {label} ({tab}) — 영상 목록 없음", flush=True)
        time.sleep(PAUSE)
        continue
    views = sorted(r["views"] for r in rows)
    secs = [r["sec"] for r in rows if r["sec"]]
    rec = {
        "표시이름": label,
        "채널": channel_name,
        "주소": url,
        "탭": tab,
        "편수": len(rows),
        "조회_중앙": int(statistics.median(views)),
        "조회_최고": max(views),
        "조회_최저": min(views),
        "백만이상": sum(1 for v in views if v >= 1_000_000),
        "길이_중앙초": int(statistics.median(secs)) if secs else None,
        "raw": rows,
    }
    results.append(rec)
    print(f"  {label:18s} {tab:6s} n={rec['편수']:3d} "
          f"중앙 {rec['조회_중앙']:>9,} 최고 {rec['조회_최고']:>10,} "
          f"1M+ {rec['백만이상']:2d} 길이 {rec['길이_중앙초']}s", flush=True)
    time.sleep(PAUSE)

stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
(OUT / "결과.json").write_text(
    json.dumps({"측정시각": stamp, "표본": N, "채널": results},
               ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n측정 시각: {stamp}")
print(f"저장: {OUT/'결과.json'}  ({len(results)}개 채널·탭)")
