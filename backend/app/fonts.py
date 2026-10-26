"""字体注册：内置字库 + 系统中文字体，带覆盖度探测与缺字回退。

字体来源有两条：
  bundled  项目自带的 backend/fonts/ 目录，随项目分发
  system   操作系统已安装的字体，只读取路径、不复制文件

启动时扫一遍，结果按 (路径, mtime, 大小) 缓存到 data/fontcache.json，
之后命中缓存只要几十毫秒。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

from PIL import ImageFont

FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_FILE = DATA_DIR / "fontcache.json"
CACHE_VERSION = 3
SUFFIX = {".ttf", ".otf", ".ttc", ".otc"}

# 判定“是中文可用字体”的门槛：对高频 1000 字的覆盖率
MIN_COVERAGE = 0.92

# 字体风格，用于在选择器里给个直观提示（顺序有意义，先匹配到的算数）
STYLE_HINTS = [
    ("行", ("xing", "行楷", "行书")),
    ("楷", ("kai", "楷")),
    ("隶", ("liti", "隶")),
    ("魏", ("xinwei", "魏")),
    ("仿宋", ("fangsong", "仿宋", "fangsong")),
    ("宋", ("song", "宋", "serif", "ming", "mincho", "sung")),
    ("圆", ("yuan", "圆", "rounded")),
    ("黑", ("hei", "黑", "sans", "yahei", "deng", "gothic", "hupo", "caiyun")),
]

# 练字场景的书体优先级：楷、行、隶、魏、仿宋、宋、黑、圆
STYLE_ORDER = {"楷": 0, "行": 1, "隶": 2, "魏": 3, "仿宋": 4, "宋": 5, "黑": 6, "圆": 7}


def _read_sets() -> tuple[str, str]:
    """(判定用的高频 1000 字, 展示用的常用 3500 字)"""
    try:
        data = json.loads((DATA_DIR / "charsets.json").read_text(encoding="utf-8"))
        core = data.get("freq1000", {}).get("chars", "")
        full = data.get("freq3500", {}).get("chars", "") or core
        if len(core) >= 500:
            return core, full
    except Exception:
        pass
    fallback = (
        "的一是了我不人在他有这个上们来到时大地为子中你说生国年着就那和要她出也得里"
        "后自以会家可下而过天去能对小多然于心学么之都好看起发当没成只如事把还用第样"
        "道想作种开美总从无情己面最女但现如前些所同日手又行意动方期它头经长儿回位分"
        "爱老因很给名法间斯知世什两次使身者被高已亲其进此话常与活正感见明问力理尔点"
        "文几定本公特做外孩相西果走将月十实向声车全信重三机工物气每并别真打太新比才"
        "便夫再书部水像眼等体却加电主界门利海受听表德少克代员许稜先口由死安写性马光"
        "白或住难望教命花结乐色更拉东神记处让母父应直字场平报友关放至张认接告入笑内"
        "英军候民岁往何度山觉路带万男边风解叫任金快原吃妈变通师立象数四失满战远格士"
    )
    return fallback, fallback


CORE_SAMPLE, FULL_SAMPLE = _read_sets()


# ---------- 字体目录 ----------
def system_dirs() -> list[Path]:
    if sys.platform.startswith("win"):
        dirs = [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")   # 用户安装的字体
        return dirs
    if sys.platform == "darwin":
        return [Path("/System/Library/Fonts"), Path("/Library/Fonts"),
                Path.home() / "Library" / "Fonts"]
    return [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
            Path.home() / ".fonts", Path.home() / ".local/share/fonts"]


def _candidates(directory: Path, deep: bool) -> list[Path]:
    if not directory.exists():
        return []
    try:
        found = directory.rglob("*") if deep else directory.iterdir()
        return [p for p in found if p.is_file() and p.suffix.lower() in SUFFIX]
    except Exception:
        return []


def _style_tag(name: str, file: str) -> str:
    hay = f"{name} {file}".lower()
    for tag, keys in STYLE_HINTS:
        for key in keys:
            # 加边界，避免 Light 被当成“隶”、Song 被当成“宋”之外的误配
            if re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", hay):
                return tag
    return ""


def _family_name(font, path: Path) -> str:
    """优先中文名（楷体 / 微软雅黑），没有再用英文名或文件名"""
    records: list[tuple[int, str]] = []
    for rec in font["name"].names:
        if rec.nameID != 1:
            continue
        try:
            value = rec.toUnicode().strip()
        except Exception:
            continue
        if value:
            records.append((rec.langID, value))
    # 2052 简中 > 1028 繁中 > 1033 英文
    for lang in (2052, 1028, 1033, 0):
        for lang_id, value in records:
            if lang_id == lang:
                return value
    if records:
        return records[0][1]
    return path.stem


def _probe(path: Path) -> dict | None:
    """读出字体名与常用字覆盖度；不覆盖中文字形的直接返回 None"""
    try:
        from fontTools.ttLib import TTFont

        font = TTFont(str(path), fontNumber=0, lazy=True)
        try:
            cmap = font.getBestCmap()
            core = sum(1 for ch in CORE_SAMPLE if ord(ch) in cmap) / max(1, len(CORE_SAMPLE))
            cover = sum(1 for ch in FULL_SAMPLE if ord(ch) in cmap) / max(1, len(FULL_SAMPLE))
            name = _family_name(font, path)
            glyphs = len(font.getGlyphOrder())
        finally:
            font.close()
    except Exception:
        return None

    if core < MIN_COVERAGE:
        return None
    try:
        ImageFont.truetype(str(path), 24)     # 确认 PIL 真的能加载
    except Exception:
        return None

    # 字体名是纯英文但文件名是中文（本地化残缺的字库），用文件名更好认
    if all(ord(c) < 128 for c in name) and any("\u4e00" <= c <= "\u9fff" for c in path.stem):
        name = path.stem
    return {"name": name, "coverage": round(cover * 100), "ratio": cover, "glyphs": glyphs}


# ---------- 缓存 ----------
_cache: list[dict] | None = None


def _cache_key(path: Path) -> str:
    try:
        st = path.stat()
        return f"{path}|{int(st.st_mtime)}|{st.st_size}"
    except OSError:
        return f"{path}|0|0"


def _load_disk_cache() -> dict:
    try:
        raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        # 探测算法一变，旧缓存就作废，避免百分比算错
        if raw.get("version") == CACHE_VERSION:
            return raw.get("items", {})
    except Exception:
        pass
    return {}


def _save_disk_cache(data: dict) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps({"version": CACHE_VERSION, "items": data}),
                              encoding="utf-8")
    except Exception:
        pass


def _slug(text: str) -> str:
    # 保留中文，否则「吴玉生行楷2.0」会被压成「2-0」
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "-", text.lower()).strip("-") or "font"


def _scan() -> list[dict]:
    disk = _load_disk_cache()
    dirty = False
    items: list[dict] = []
    used_ids: set[str] = set()

    def take_id(candidate: str, bare: bool) -> str:
        base = candidate if bare else f"sys-{_slug(candidate)}"
        font_id, n = base, 2
        while font_id in used_ids:
            font_id, n = f"{base}-{n}", n + 1
        used_ids.add(font_id)
        return font_id

    groups = [(FONT_DIR, "bundled", False), *[(d, "system", True) for d in system_dirs()]]
    seen_names: set[str] = set()

    for directory, source, deep in groups:
        for path in sorted(_candidates(directory, deep)):
            key = _cache_key(path)
            info = disk.get(key)
            if info is None:
                info = _probe(path)
                if info is None:
                    disk[key] = {"skip": True}
                    dirty = True
                    continue
                disk[key] = info
                dirty = True
            elif info.get("skip"):
                continue

            name = info["name"]
            # 同名字体只留一个（Deng / Dengb / Dengl 都叫 DengXian），优先内置
            if source != "bundled" and name in seen_names:
                continue
            seen_names.add(name)

            items.append({
                "id": take_id(path.stem, source == "bundled"),
                "name": name,
                "style": _style_tag(name, path.name),
                "file": path.name,
                "source": source,
                "coverage": round(info["ratio"] * 100),
                "glyphs": info.get("glyphs", 0),
                "path": path,
            })

    if dirty:
        # 只保留仍然存在的文件，避免缓存无限膨胀
        alive = {_cache_key(i["path"]) for i in items}
        _save_disk_cache({k: v for k, v in disk.items() if k in alive})

    # 排序：内置优先 → 练字常用的书体靠前 → 覆盖度 → 名称
    items.sort(key=lambda i: (i["source"] != "bundled", STYLE_ORDER.get(i["style"], 9),
                              -i["coverage"], i["name"]))
    return items


def scan(refresh: bool = False) -> list[dict]:
    global _cache
    if _cache is None or refresh:
        _cache = _scan()
    return _cache


def list_fonts(refresh: bool = False) -> list[dict]:
    """给前端的字体清单，去掉内部路径"""
    return [{k: v for k, v in item.items() if k != "path"} for item in scan(refresh)]


# ---------- 查询 ----------
def get(font_id: str) -> dict | None:
    for item in scan():
        if item["id"] == font_id:
            return item
    return None


def resolve(font_id: str) -> Path:
    """把 id 解析成文件路径；选不到就退回第一个可用字体"""
    item = get(font_id)
    if item:
        return item["path"]
    items = scan()
    if not items:
        raise FileNotFoundError("没有找到任何可用的中文字体，请往 backend/fonts 里放一个 ttf")
    return items[0]["path"]


def chain(font_id: str, limit: int = 3) -> list[Path]:
    """主字体 + 缺字时依次尝试的备用字体。

    顺序：用户选的 → 内置字库 → 覆盖度更高的系统字体。
    """
    primary = resolve(font_id)
    result = [primary]
    ordered = sorted(scan(), key=lambda i: (i["source"] != "bundled", -i["coverage"]))
    for item in ordered:
        if len(result) >= limit:
            break
        if item["path"] in result:
            continue
        result.append(item["path"])
    return result


def missing_in_font(font_id: str, text: str) -> list[str]:
    """只检查该字体本身缺哪些字（不落回退），用于提示"""
    try:
        path = resolve(font_id)
        from fontTools.ttLib import TTFont

        font = TTFont(str(path), fontNumber=0, lazy=True)
        try:
            cmap = font.getBestCmap()
        finally:
            font.close()
    except Exception:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for ch in text:
        if ch in seen or ch.isspace():
            continue
        seen.add(ch)
        if ord(ch) not in cmap:
            out.append(ch)
    return out


# ---------- 上传 ----------
def register(data: bytes, filename: str) -> dict:
    """保存用户上传的字体到内置字库目录"""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUFFIX:
        raise ValueError("只支持 ttf / otf / ttc 字体文件")

    # 同一个文件重复上传就直接复用已有条目，不再堆副本
    digest = hashlib.sha1(data).hexdigest()
    for item in scan():
        if item["source"] != "bundled":
            continue
        try:
            if hashlib.sha1(item["path"].read_bytes()).hexdigest() == digest:
                return {k: v for k, v in item.items() if k != "path"}
        except OSError:
            continue

    stem = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]", "", Path(filename).stem)[:40] or "custom"
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    target = FONT_DIR / f"{stem}{suffix}"
    n = 2
    while target.exists():
        target = FONT_DIR / f"{stem}-{n}{suffix}"
        n += 1
    target.write_bytes(data)
    info = _probe(target)
    if info is None:
        target.unlink(missing_ok=True)
        raise ValueError("这个字体不包含足够的中文字形，无法用于字帖")
    scan(refresh=True)
    item = next((i for i in scan() if i["path"] == target), None)
    if item is None:
        raise ValueError("字体注册失败")
    return {k: v for k, v in item.items() if k != "path"}


def stamp() -> float:
    """缓存时间戳，前端用来判断是否需要刷新列表"""
    return time.time()
