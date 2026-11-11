"""urls.py - Centralized repository of series URLs and download directories.

Provides fallback static catalog, backward-compatible variables, and dynamic
PostgreSQL integration via db.py.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Any

from media_ids import extract_video_id

# ==============================================================================
# Save Directories (Historical & Default paths)
# ==============================================================================
sbits = os.path.expanduser("~/Videos/seniorBrotherIsTooSteady")
tossave = os.path.expanduser("~/Videos/ThroneOfSeal")
herdingTheGodsSaveLocation = os.path.expanduser("~/Videos/herdingTheGods")
svl = os.path.expanduser("~/Videos/Soulland")
talessaveloc = os.path.expanduser("~/Videos/TalesofDemonsAndGods")
heaveenlyFatedVilliansSavelocation = os.path.expanduser("~/Downloads/HeavenlyFatedVillians")
savelocation = os.path.expanduser("~/Downloads/SwallowedStar")
jadeDynastySavelocation = os.path.expanduser("~/Downloads/JadeDynasty")
coilingDragonSavelocation = os.path.expanduser("~/Downloads/CoilingDragon")
imortalsSavelOcation = os.path.expanduser("~/Videos/WorldOfImmortals")
slaySaveLocale = os.path.expanduser("~/Videos/SlayTheGods")
spiritSwordSaveLocation = os.path.expanduser("~/Videos/SpiritSwords")
aWillEternalSaveLocation = os.path.expanduser("~/Downloads/aWillEternal")

# Default browser cookie configuration (e.g. 'brave', 'chrome', 'firefox', or None)
DEFAULT_BROWSER = "brave"

# ==============================================================================
# Static Series URL Lists (Backward Compatibility)
# ==============================================================================

seniorBrotherIsTooSteadyUrls = [
    "https://www.youtube.com/watch?v=-CCwYkvb9xU",
    # "https://www.youtube.com/watch?v=q-idq_6XubM",
]

throneOfSeal = [
    "https://www.youtube.com/watch?v=KOBqkps2jR8&list=PLAV8AqZgfhJsIqYEXbu_Az6c0GwU-FSqs",
    "https://www.youtube.com/watch?v=SeDS0tOgDxU",
    "https://www.youtube.com/watch?v=_NdEks8ET6I",
    "https://www.youtube.com/watch?v=zYsVItafRMY",
    "https://www.youtube.com/watch?v=1yyUCvMXL7I",
    "https://www.youtube.com/watch?v=tSE2st5Ex-g",
    "https://www.youtube.com/watch?v=hI4YjL56iLo",
    "https://www.youtube.com/watch?v=A_qOUhyukV4",  # 143
    "https://www.youtube.com/watch?v=0uqqovYNq7Q",  # 144
    "https://www.youtube.com/watch?v=Aus1D_KDE58",  # 145
    "https://www.youtube.com/watch?v=Mt2vjaO5yak",  # 146
    "https://www.youtube.com/watch?v=EMr0FwTZMuw",  # 147
    "https://www.youtube.com/watch?v=fApjIE93m7k",  # 148
    "https://www.youtube.com/watch?v=u45CZ-kEx6U",  # 149
    "https://www.youtube.com/watch?v=CTDNgdeuDew",  # 150
]

herdingTheGods = [
    "https://www.youtube.com/watch?v=HzO3lr9mdss",
    "https://youtu.be/HGPNjFuIEJY?si=N-RlcIR6xDUC2zXa",
    "https://www.youtube.com/watch?v=HGPNjFuIEJY&list=PL4cvPACMm-tj2ukmk_yHjUDJmV4bPqpDG&index=8",
    "https://www.youtube.com/watch?v=aZkLsfMUdM8&list=PL4cvPACMm-tj2ukmk_yHjUDJmV4bPqpDG&index=9",
    "https://www.youtube.com/watch?v=JJIoW9_TwfA",
    "https://www.youtube.com/watch?v=OZiESDCMWXk",
    "https://www.youtube.com/watch?v=4KWIWsJxnXo",
    "https://www.youtube.com/watch?v=3r-CK7F71MA",
]

jadDynastyUrls = [
    "https://www.youtube.com/watch?v=nzMpuKicQwk",
    "https://www.youtube.com/watch?v=R2M4Ib1C1aM",
    "https://www.youtube.com/watch?v=I4JHhX7JZEg",
    "https://www.youtube.com/watch?v=gzx-fT_tBhI",
    "https://www.youtube.com/watch?v=gfXsTiOi4PE",
    "https://www.youtube.com/watch?v=JFrOP0zbiTc",
    "https://www.youtube.com/watch?v=kIzZyZ8LCUM",
    "https://www.youtube.com/watch?v=_OR9VIyh3aY",
    "https://www.youtube.com/watch?v=KJMtzkQMeD4",
    "https://www.youtube.com/watch?v=PYWHPuMNAMo",
    "https://www.youtube.com/watch?v=4yRyHOodDCM",
    "https://www.youtube.com/watch?v=vIxIRxsOhbw",
    "https://www.youtube.com/watch?v=4EBoIIQFD1U",
    "https://www.youtube.com/watch?v=pUHaEL2PDME",
    "https://www.youtube.com/watch?v=XwS94VpEUj0",
    "https://www.youtube.com/watch?v=nxFcn6mza_U",
    "https://www.youtube.com/watch?v=YKhqyEojqX8",
    "https://www.youtube.com/watch?v=qAmGBmTMmEo",
    "https://www.youtube.com/watch?v=IMvkCksq_n0",
    "https://www.youtube.com/watch?v=k5r_wBPz7H0",
    "https://www.youtube.com/watch?v=51uLBgDliak",
    "https://www.youtube.com/watch?v=b1Bp2XJaibU",
    "https://www.youtube.com/watch?v=Fr9UpShfqcs",
    "https://www.youtube.com/watch?v=w1ImqTm7WAM",
    "https://www.youtube.com/watch?v=sLv_rwrb3Us",
    "https://www.youtube.com/watch?v=PQ8CNu0rwGw",
    "https://www.youtube.com/watch?v=-Mk534UgiMA",
    "https://www.youtube.com/watch?v=2KW8whccGLA",
    "https://www.youtube.com/watch?v=lEk-31Iffwc",
    "https://www.youtube.com/watch?v=yujUQO-UYos",
    "https://www.youtube.com/watch?v=jpRlLb2Jff0",
    "https://www.youtube.com/watch?v=HbQ8XG-y4vA",
    "https://www.youtube.com/watch?v=2Db65Ru6U-M",
    "https://www.youtube.com/watch?v=haW-7Bz4Ino",
    "https://www.youtube.com/watch?v=B0c6IcKndQA",
    "https://www.youtube.com/watch?v=t6w2dC6x00c",
    "https://www.youtube.com/watch?v=QUFTDV8_ztY",
    "https://www.youtube.com/watch?v=75QXTjBsxG4",
    "https://www.youtube.com/watch?v=jQNzDJGgnKw",
    "https://www.youtube.com/watch?v=rUDBV1LyCcw",
    "https://www.youtube.com/watch?v=LvXFmal2RAU",
    "https://www.youtube.com/watch?v=srxlMyG7Quo",
    "https://www.youtube.com/watch?v=itNK0DbJEJY",
    "https://www.youtube.com/watch?v=9ER7EUGQrHw",
    "https://www.youtube.com/watch?v=ASUgGTMa9OA",
    "https://www.youtube.com/watch?v=7uH4Kyd78ws",
    "https://www.youtube.com/watch?v=Uv1DI2JHDAA",
    "https://www.youtube.com/watch?v=Zx8hzOZx0sA",
    "https://www.youtube.com/watch?v=b1zRca5Mzpg",
    "https://www.youtube.com/watch?v=3p9gHY7k6Xs",
    "https://www.youtube.com/watch?v=edD_aehJxDE",
    "https://www.youtube.com/watch?v=LrFCMIv-PgE",
    "https://www.youtube.com/watch?v=zAQFy07AOCk",
    "https://www.youtube.com/watch?v=rL50Dn8EzTI",
    "https://www.youtube.com/watch?v=uc6HR-QLsaE",
    "https://www.youtube.com/watch?v=FYt8VLzGKek",
    "https://www.youtube.com/watch?v=kudpNT9dOBs",
    "https://www.youtube.com/watch?v=sYY7WwL8fpo",
    "https://www.youtube.com/watch?v=G-DWbMFh96Q",
    "https://www.youtube.com/watch?v=KkVnzq3ItWw",
    "https://www.youtube.com/watch?v=OKKnwtvo7P4",
    "https://www.youtube.com/watch?v=hVkEH4CxEP8",
    "https://www.youtube.com/watch?v=ElXcAQUrvPU",
    "https://www.youtube.com/watch?v=Xnk7m2aRn8I",
    "https://www.youtube.com/watch?v=PmeI5Tq8IsI",
    "https://www.youtube.com/watch?v=dLdI1OiAV5A",
    "https://www.youtube.com/watch?v=fu39MGk71Dc",
    "https://www.youtube.com/watch?v=wDOT2IIjQ0Y",
    "https://www.youtube.com/watch?v=5ftprtW6_9I",
    "https://www.youtube.com/watch?v=61RsnuujmjM",
    "https://www.youtube.com/watch?v=xOyyDxXUA1I",
    "https://www.youtube.com/watch?v=BXQC3CtRwkU",
    "https://www.youtube.com/watch?v=kTTtk0fETgE",
    "https://www.youtube.com/watch?v=ea75_lwgc9Q",
    "https://www.youtube.com/watch?v=jv7WQLiWRm8",
    "https://www.youtube.com/watch?v=vLRLaEwtOhM",
    "https://www.youtube.com/watch?v=Ma4cRNzrXQ8",
    "https://www.youtube.com/watch?v=N9HUwQvgAcc",
    "https://www.youtube.com/watch?v=1cZhIn1HW0s",
    "https://www.youtube.com/watch?v=tL07kApPByc",
]

coilingDragonUrls = [
    "https://www.youtube.com/watch?v=4_LxIZl9o_E",
    "https://www.youtube.com/watch?v=WXkiQJU4ITc",
    "https://www.youtube.com/watch?v=4ybZjfw_MZA",
    "https://www.youtube.com/watch?v=BmEmIYO_SA8",
    "https://www.youtube.com/watch?v=mp8voKsbn14",
    "https://www.youtube.com/watch?v=8i1q8Y932ik",
    "https://www.youtube.com/watch?v=MQF5inrGpT4",
    "https://www.youtube.com/watch?v=F10ckSn7t2U",
    "https://www.youtube.com/watch?v=JkBZWrJ5p3Y",
    "https://www.youtube.com/watch?v=zmFik421q4c",
    "https://www.youtube.com/watch?v=NinDCD-0ZJU",
    "https://www.youtube.com/watch?v=CqSLT5ltFDQ",
    "https://www.youtube.com/watch?v=qHYw9rIaAKQ",
    "https://www.youtube.com/watch?v=4ae2I3yJjR0",
    "https://www.youtube.com/watch?v=Cbi-bBAZ1YI",
    "https://www.youtube.com/watch?v=oLm7nQDvtKI",
    "https://www.youtube.com/watch?v=Wfvd1Kf-3BM",
    "https://www.youtube.com/watch?v=eIYOUPeR-wA",
    "https://www.youtube.com/watch?v=zSNRNHkCgI8",
]

swallowedStarUrls = [
    # "https://youtu.be/hhfPUCtUFXw",
    # "https://www.youtube.com/watch?v=IFrSqcm2KEk",
    # "https://www.youtube.com/watch?v=hhfPUCtUFXw",
    "https://youtube.com/watch?v=MCyKDm6ynXM",
]

soulLandUrls = [
    "https://www.youtube.com/watch?v=AtXBtbvNq2c",
    "https://www.youtube.com/watch?v=b3YvbSpTnVw",
]

slaytheGodsURL = [
    "https://www.youtube.com/watch?v=JSFp9g1r0uw",
]

demonsAndGodsURl = [
    "https://www.youtube.com/watch?v=GsjaaYb8-PA&t=1782s",
]

heaveenlyFatedVilliansUrls = [
    "https://www.youtube.com/watch?v=0c6RUUR66xY",
]

worldOfImortalsUrls = [
    "http://youtube.com/watch?v=0vUdndtILmI&list=PLAV8AqZgfhJuRXcyrqhwNJ-rrFI_58srL&index=45",
]

spiritSwordUrls = [
    "https://www.youtube.com/watch?v=KZu8HkvHzEs&list=PLAV8AqZgfhJvleLOsyu5kzxiAS9QKO2ER&index=18",
]

aWillEternalUrls = [
    "https://www.youtube.com/watch?v=PkAfGiXQK_U",
]

# ==============================================================================
# Series Data Structure & Static Catalog
# ==============================================================================

@dataclass
class Series:
    key: str
    name: str
    save_dir: str
    urls: List[str] = field(default_factory=list)
    description: str = ""
    id: Optional[int] = None

    def get_archive_path(self) -> str:
        return os.path.join(self.save_dir, "downloaded.txt")

    def get_downloaded_ids(self) -> Set[str]:
        archive = self.get_archive_path()
        if not os.path.exists(archive):
            return set()
        ids = set()
        try:
            with open(archive, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.strip().split()
                    if parts:
                        ids.add(parts[-1])
        except Exception:
            pass
        return ids

    def get_stats(self) -> Dict[str, int]:
        downloaded_ids = self.get_downloaded_ids()
        downloaded = 0
        for u in self.urls:
            vid = extract_video_id(u)
            if vid in downloaded_ids:
                downloaded += 1
        total = len(self.urls)
        return {
            "total": total,
            "downloaded": downloaded,
            "pending": max(0, total - downloaded),
        }

    def get_pending_urls(self) -> List[str]:
        downloaded_ids = self.get_downloaded_ids()
        pending = []
        for u in self.urls:
            vid = extract_video_id(u)
            if vid not in downloaded_ids:
                pending.append(u)
        return pending


# Master Static Series Catalog (Fallback)
SERIES_CATALOG: Dict[str, Series] = {
    "senior_brother": Series(
        key="senior_brother",
        name="Senior Brother Is Too Steady",
        save_dir=sbits,
        urls=seniorBrotherIsTooSteadyUrls,
        description="Senior Brother Is Too Steady donghua episodes",
    ),
    "throne_of_seal": Series(
        key="throne_of_seal",
        name="Throne of Seal",
        save_dir=tossave,
        urls=throneOfSeal,
        description="Throne of Seal episodes",
    ),
    "herding_gods": Series(
        key="herding_gods",
        name="Herding The Gods",
        save_dir=herdingTheGodsSaveLocation,
        urls=herdingTheGods,
        description="Herding The Gods episodes",
    ),
    "jade_dynasty": Series(
        key="jade_dynasty",
        name="Jade Dynasty",
        save_dir=jadeDynastySavelocation,
        urls=jadDynastyUrls,
        description="Jade Dynasty episodes",
    ),
    "coiling_dragon": Series(
        key="coiling_dragon",
        name="Coiling Dragon",
        save_dir=coilingDragonSavelocation,
        urls=coilingDragonUrls,
        description="Coiling Dragon episodes",
    ),
    "swallowed_star": Series(
        key="swallowed_star",
        name="Swallowed Star",
        save_dir=savelocation,
        urls=swallowedStarUrls,
        description="Swallowed Star episodes",
    ),
    "soul_land": Series(
        key="soul_land",
        name="Soul Land",
        save_dir=svl,
        urls=soulLandUrls,
        description="Soul Land episodes",
    ),
    "slay_the_gods": Series(
        key="slay_the_gods",
        name="Slay The Gods",
        save_dir=slaySaveLocale,
        urls=slaytheGodsURL,
        description="Slay The Gods episodes",
    ),
    "demons_and_gods": Series(
        key="demons_and_gods",
        name="Tales of Demons and Gods",
        save_dir=talessaveloc,
        urls=demonsAndGodsURl,
        description="Tales of Demons and Gods episodes",
    ),
    "heavenly_fated": Series(
        key="heavenly_fated",
        name="Heavenly Fated Villains",
        save_dir=heaveenlyFatedVilliansSavelocation,
        urls=heaveenlyFatedVilliansUrls,
        description="Heavenly Fated Villains episodes",
    ),
    "world_of_immortals": Series(
        key="world_of_immortals",
        name="World of Immortals",
        save_dir=imortalsSavelOcation,
        urls=worldOfImortalsUrls,
        description="World of Immortals episodes",
    ),
    "spirit_sword": Series(
        key="spirit_sword",
        name="Spirit Sword Sovereign",
        save_dir=spiritSwordSaveLocation,
        urls=spiritSwordUrls,
        description="Spirit Sword Sovereign episodes",
    ),
    "a_will_eternal": Series(
        key="a_will_eternal",
        name="A Will Eternal",
        save_dir=aWillEternalSaveLocation,
        urls=aWillEternalUrls,
        description="A Will Eternal episodes",
    ),
}


# ==============================================================================
# Helper Utilities (With Dynamic PostgreSQL Integration)
# ==============================================================================

def get_all_series() -> List[Series]:
    """Return all configured series from PostgreSQL store if available, else static catalog."""
    try:
        import db
        db_series = db.get_all_series()
        if db_series:
            result = []
            for d in db_series:
                eps = db.get_episodes(d["id"])
                urls = [e["url"] for e in eps]
                result.append(
                    Series(
                        key=d["key"],
                        name=d["name"],
                        save_dir=d["save_dir"],
                        urls=urls,
                        description=d.get("description", "") or "",
                        id=d.get("id"),
                    )
                )
            return result
    except Exception:
        pass
    return list(SERIES_CATALOG.values())


def get_series(query: Any) -> Optional[Series]:
    """Find a series by ID, key, or fuzzy title match from DB or static catalog."""
    try:
        import db
        d = db.get_series(query)
        if d:
            eps = db.get_episodes(d["id"])
            urls = [e["url"] for e in eps]
            return Series(
                key=d["key"],
                name=d["name"],
                save_dir=d["save_dir"],
                urls=urls,
                description=d.get("description", "") or "",
                id=d.get("id"),
            )
    except Exception:
        pass

    q = str(query).strip().lower()
    if q in SERIES_CATALOG:
        return SERIES_CATALOG[q]
    for s in SERIES_CATALOG.values():
        if q == s.name.lower() or q in s.name.lower() or q in s.key:
            return s
    return None


def add_url_to_series(series_key: str, url: str) -> bool:
    """Add a new URL to an existing series in PostgreSQL and in-memory catalog."""
    clean_url = url.strip()
    s = get_series(series_key)
    if not s:
        return False

    try:
        import db
        db_s = db.get_series(series_key)
        if db_s:
            db.add_episode(db_s["id"], clean_url)
    except Exception:
        pass

    if clean_url not in s.urls:
        s.urls.append(clean_url)
    return True
