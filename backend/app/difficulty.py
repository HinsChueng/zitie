"""离线难度评估与篇目推荐。

只用仓库自带的高频字表和内容库做纯计算：不联网、不需要笔画数据库、
不需要 API Key。难度是「这篇字帖练起来有多吃力」的相对参考值，
不是教材难度认证；指标与权重都在下面写明，便于复算和调整。
"""
from __future__ import annotations

from . import charsets
from .layout import ALL_PUNCT, CJK, normalize

LEVEL_LABELS = ("入门", "基础", "进阶", "熟练", "挑战")

_RANKS: dict[str, int] | None = None
_LIB: list[dict] | None = None


def _rank_map() -> dict[str, int]:
    """字 → 常用字频排名；没进表的字视为超出表长。"""
    global _RANKS
    if _RANKS is None:
        data = charsets.load()
        freq = (data.get("freq3500", {}).get("chars", "")
                or data.get("freq1000", {}).get("chars", ""))
        _RANKS = {ch: i for i, ch in enumerate(freq)}
    return _RANKS


def score_text(text: str, keep_punct: bool = True) -> dict:
    """给一段文本打分，返回 1–5 级难度和可解释的指标。

    十条加分项各 1 分，分数线性映射到 1–5 级。阈值按内置内容库的实际
    指标分布（平均字频排名 300–1500、篇幅 20–50 字）标定，确保 17 篇
    预置篇目能拉开档次；用户粘贴长文时靠篇幅项继续升到 5 级。
    """
    clean = normalize(text, keep_punct, False)
    han = [ch for ch in clean if CJK.match(ch)]
    ranks = _rank_map()
    table_len = max(1, len(ranks))
    n = len(han)

    if n == 0:
        return {"level": 1, "label": LEVEL_LABELS[0], "points": 0, "chars": 0,
                "unique": 0, "rare": 0, "coverage": 100.0, "avg_rank": 0,
                "reasons": ["还没有汉字内容"]}

    rare = sum(1 for ch in han if ch not in ranks)
    rare_ratio = rare / n
    avg_rank = sum(ranks.get(ch, table_len) for ch in han) / n
    unique = len(set(han))

    unique_ratio = unique / n
    points = sum((
        avg_rank > 500,
        avg_rank > 800,
        avg_rank > 1100,
        rare >= 2,
        rare >= 3,
        n > 30,
        n > 40,
        unique_ratio > 0.90,
        n > 120,
        n > 300,
    ))
    level = 1 + min(4, round(points * 4 / 10))
    coverage = round((n - rare) / n * 100, 1)

    reasons = [
        f"正文 {n} 字，含 {unique} 个不同汉字（重复率 {round((1 - unique_ratio) * 100)}%）",
        f"常用字覆盖 {coverage}%（{rare} 字超出常用字表）",
        f"平均字频排名约 {int(avg_rank)}",
    ]
    return {
        "level": level,
        "label": LEVEL_LABELS[level - 1],
        "points": points,
        "chars": n,
        "unique": unique,
        "rare": rare,
        "coverage": coverage,
        "avg_rank": int(avg_rank),
        "reasons": reasons,
    }


def _library_scores() -> list[dict]:
    global _LIB
    if _LIB is None:
        _LIB = []
        for item in charsets.LIBRARY:
            s = score_text(item["text"])
            _LIB.append({"id": item["id"], "title": item["title"],
                         "author": item["author"], "category": item["category"],
                         "era": item.get("era", "古代"),
                         "text": item["text"], "note": item["note"],
                         "level": s["level"], "chars": s["chars"]})
    return _LIB


def analyze(text: str, title: str = "", keep_punct: bool = True) -> dict:
    """当前文本的难度 + 三篇推荐。

    推荐策略：优先同级换篇巩固，再补一篇略高难度作为进阶；
    同级不足时用相邻难度补齐。当前标题相同的篇目不推荐给自己。
    """
    result = score_text(text, keep_punct)
    level = result["level"]
    pool = [x for x in _library_scores()
            if not title or not title.startswith(x["title"])]

    same = [x for x in pool if x["level"] == level]
    harder = [x for x in pool if x["level"] == level + 1]
    easier = [x for x in pool if x["level"] == level - 1]
    rest = [x for x in pool if x["level"] not in (level - 1, level, level + 1)]

    def pick(items: list[dict], reason: str, limit: int) -> list[dict]:
        return [{**x, "reason": reason} for x in items[:limit]]

    picked = pick(same, "难度相近，换一篇巩固", 2)
    picked += pick(harder, "略提难度，往上练一档", 1)
    if len(picked) < 3:
        picked += pick(easier, "回调难度，巩固基本功", 3 - len(picked))
    if len(picked) < 3:
        picked += pick(rest, "换个题材练练", 3 - len(picked))

    result["recommend"] = picked[:3]
    result["library_total"] = len(_library_scores())
    return result


def library_levels() -> list[dict]:
    """给 meta 接口用：每篇预置内容的难度，前端可据此做筛选提示。"""
    return [{"id": x["id"], "level": x["level"], "chars": x["chars"]}
            for x in _library_scores()]
