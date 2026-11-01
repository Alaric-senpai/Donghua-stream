import os
import sys
import time
import yt_dlp

MAX_RETRIES = 3
MAX_HEIGHT = 720
BROWSER = None  # e.g. "brave" to reuse login cookies for private/age-gated videos

# ---- Save locations ---------------------------------------------------------
LOCATIONS = {
    "soulland":          "~/Videos/Soulland",
    "talesofdemons":     "~/Videos/TalesofDemonsAndGods",
    "heavenlyfated":     "~/Downloads/HeavenlyFatedVillians",
    "swallowedstar":     "~/Downloads/SwallowedStar",
    "jadedynasty":       "~/Downloads/JadeDynasty",
    "coilingdragon":     "~/Downloads/CoilingDragon",
    "worldofimmortals":  "~/Videos/WorldOfImmortals",
    "slaythegods":       "~/Videos/SlayTheGods",
    "spiritsword":       "~/Videos/SpiritSword",
}
LOCATIONS = {k: os.path.expanduser(v) for k, v in LOCATIONS.items()}

# ---- Dailymotion IDs or full URLs per series --------------------------------
VIDEOS = {
    "soulland":         [],  # e.g. "x8abc12"
    "talesofdemons":    [],
    "heavenlyfated":    [],
    "swallowedstar":    ["1k39spptg5947949c87","1k39t1miv6bfe1b8a91"],
    "jadedynasty":      [],
    "coilingdragon":    [],
    "worldofimmortals": [],
    "slaythegods":      [],
    "spiritsword":      [],
}


def to_url(item):
    """Accept a bare Dailymotion ID or a full URL."""
    item = item.strip()
    if item.startswith("http"):
        return item
    return f"https://www.dailymotion.com/video/{item}"


def download_series(name):
    save_dir = LOCATIONS[name]
    items = VIDEOS.get(name, [])
    if not items:
        print(f"[{name}] no videos listed, skipping.")
        return

    os.makedirs(save_dir, exist_ok=True)
    opts = {
        "outtmpl": f"{save_dir}/%(title)s [%(id)s].%(ext)s",
        "format": (
            f"bestvideo[height<={MAX_HEIGHT}]+bestaudio"
            f"/best[height<={MAX_HEIGHT}]/best"
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en"],
        "subtitlesformat": "srt",
        "download_archive": os.path.join(save_dir, "downloaded.txt"),
    }
    if BROWSER:
        opts["cookiesfrombrowser"] = (BROWSER,)

    for item in items:
        url = to_url(item)
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"[{name}] {url} (attempt {attempt}/{MAX_RETRIES})")
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                break
            except Exception as e:
                print(f"  failed: {e}")
                if attempt == MAX_RETRIES:
                    print(f"  giving up on {url}")
                else:
                    time.sleep(3 * attempt)


if __name__ == "__main__":
    # Usage: python dm_download.py [series ...]   (no args = all series)
    #        python dm_download.py swallowedstar jadedynasty
    targets = [a.lower() for a in sys.argv[1:]] or list(LOCATIONS)
    unknown = [t for t in targets if t not in LOCATIONS]
    if unknown:
        sys.exit(f"Unknown series: {', '.join(unknown)}\nValid: {', '.join(LOCATIONS)}")
    for t in targets:
        download_series(t)
