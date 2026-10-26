"""字表：常用字、偏旁部首、基本笔画。

大字表（高频 1000 / 3500）由脚本从语料频率生成后落在 data/charsets.json，
运行时不依赖 wordfreq；内置的小字表直接写在这里。
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE = DATA_DIR / "charsets.json"

# 常用偏旁部首（含常见变形）
RADICALS = (
    "一丨丶丿乙亅二亠人儿入八冂冖冫几凵刀力勹匕匚匸十卜卩厂厶又口囗土士夂夊夕大女子宀寸小尢尸屮山巛工己巾干幺广廴廾弋弓彐彡彳心戈户手支攴文斗斤方无日曰月木欠止歹殳毋比毛氏气水火爪父爻爿片牙牛犬玄玉瓜瓦甘生用田疋疒癶白皮皿目矛矢石示禸禾穴立竹米缶网羊羽老而耒耳聿肉臣自至臼舌舛舟艮色艹虍虫血行衣襾见角言谷豆豕豸贝赤走足身车辛辰辵邑酉釆里金长门阜隶隹雨青非面革韦韭音页风飞食首香马骨高髟鬥鬯鬲鬼鱼鸟卤鹿麦麻黄黍黑黹黾鼎鼓鼠鼻齐齿龙龟龠"
    "氵亻扌讠忄宀艹辶阝纟钅饣礻衤牜灬刂卩冫丬攵⺮"
)

# 基本笔画与结构入门（按笔画由少到多）
STROKES = (
    "一二三十上下工土王干丰于才寸丈大天夫太犬木本末未术禾朱米来"
    "人个介从众今令余余舍命"
    "口日目田由甲申电里且中国回园四西"
    "手毛牛生年午失朱"
    "山水永求"
    "之这叫边过还进"
    "子字学安家宝定"
    "女好如始"
    "刀力办加劲"
    "心必思想"
    "也有他地池"
    "月明有朋友服"
    "火灯点燃"
    "口古右石"
    "小少尔当"
)

BUILTIN: dict[str, dict] = {
    "radicals": {"name": "偏旁部首", "desc": "常用部首与变形，练结构与比例", "chars": RADICALS},
    "strokes": {"name": "笔画入门", "desc": "由简到繁的基础字，配合笔顺练习", "chars": STROKES},
}


def _dedupe(text: str) -> str:
    seen: set[str] = set()
    out = []
    for ch in text:
        if ch.isspace() or ch in seen:
            continue
        seen.add(ch)
        out.append(ch)
    return "".join(out)


def load() -> dict[str, dict]:
    result: dict[str, dict] = dict(BUILTIN)
    if CACHE.exists():
        try:
            extra = json.loads(CACHE.read_text(encoding="utf-8"))
            for key, item in extra.items():
                result[key] = {
                    "name": item.get("name", key),
                    "desc": item.get("desc", ""),
                    "chars": _dedupe(item.get("chars", "")),
                }
        except Exception:
            pass
    for item in result.values():
        item["chars"] = _dedupe(item["chars"])
        item["count"] = len(item["chars"])
    return result


def list_sets() -> list[dict]:
    data = load()
    order = ["freq1000", "freq3500", "radicals", "strokes"]
    keys = [k for k in order if k in data] + [k for k in data if k not in order]
    return [{"id": k, "name": data[k]["name"], "desc": data[k]["desc"], "count": data[k]["count"]}
            for k in keys]


def get(key: str) -> dict | None:
    return load().get(key)
