"""字表与内容库：常用字、偏旁部首、基本笔画，以及可直接开练的诗文。

大字表（高频 1000 / 3500）由脚本从语料频率生成后落在 data/charsets.json，
运行时不依赖 wordfreq；内置的小字表与内容库直接写在这里，零外部依赖。
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

# 分级字表按高频字表切片 + 笔画入门字生成，是「按难度分组的练习字表」，
# 不是任何版本教材的生字表原表；desc 里如实写明，避免拿去当课本配套用。
GRADE_NOTE = "按字频与笔画由简到繁切分，非教材生字表原表"


def _graded_sets(base: dict[str, dict]) -> dict[str, dict]:
    freq = (base.get("freq3500", {}).get("chars", "")
            or base.get("freq1000", {}).get("chars", ""))
    if not freq:
        return {}
    starter = _dedupe(STROKES + freq)
    g1 = starter[:100]
    used = set(g1)
    g2 = "".join(ch for ch in freq if ch not in used)[:300]
    used.update(g2)
    g3 = "".join(ch for ch in freq if ch not in used)[:500]
    return {
        "grade1": {"name": "分级字表 · 启蒙 100 字", "desc": GRADE_NOTE,
                   "chars": g1, "count": len(g1)},
        "grade2": {"name": "分级字表 · 基础 300 字", "desc": GRADE_NOTE,
                   "chars": g2, "count": len(g2)},
        "grade3": {"name": "分级字表 · 进阶 500 字", "desc": GRADE_NOTE,
                   "chars": g3, "count": len(g3)},
    }

# ---------------------------------------------------------------------------
# 内容库：选一篇就能开练，不用自己找文本、不用手工敲标题。
#
# 一级按时代分「古代 / 现代」，二级按体裁细分类别；每篇都是节选，
# 篇幅控制在两三行字帖之内，标点保留，交给版式引擎统一处理。
#
# 版权口径：古代部分为公有领域典籍；现代部分只收作者逝世满 50 年、
# 依中国著作权法已进入公有领域的作者。丰子恺（1975 年逝世）自 2026 年起
# 进入公有领域。仍在保护期内的叶圣陶、冰心、巴金、沈从文、艾青等一律不收。
# 节选文本供临写用，正式引用请核对原书版本。
# ---------------------------------------------------------------------------
_RAW_LIBRARY: tuple[dict, ...] = (
    # ---------- 古代 · 先秦史传 ----------
    {"id": "zuo_kezhuan", "category": "先秦史传", "title": "左传 · 郑伯克段于鄢（节选）", "author": "左丘明",
     "note": "史传开篇 · 叙事句", "text": "初，郑武公娶于申，曰武姜。生庄公及共叔段。庄公寤生，惊姜氏，故名曰寤生，遂恶之。爱共叔段，欲立之。"},
    {"id": "zuo_caogui", "category": "先秦史传", "title": "左传 · 曹刿论战（节选）", "author": "左丘明",
     "note": "名篇 · 对话句", "text": "十年春，齐师伐我。公将战，曹刿请见。其乡人曰：肉食者谋之，又何间焉？刿曰：肉食者鄙，未能远谋。"},
    {"id": "zuo_zhuzhiwu", "category": "先秦史传", "title": "左传 · 烛之武退秦师（节选）", "author": "左丘明",
     "note": "外交辞令 · 长句", "text": "晋侯、秦伯围郑，以其无礼于晋，且贰于楚也。晋军函陵，秦军氾南。佚之狐言于郑伯曰：国危矣，若使烛之武见秦君，师必退。"},
    {"id": "zhanguo_zouji", "category": "先秦史传", "title": "战国策 · 邹忌讽齐王纳谏（节选）", "author": "",
     "note": "设喻说理 · 问句", "text": "邹忌修八尺有余，而形貌昳丽。朝服衣冠，窥镜，谓其妻曰：我孰与城北徐公美？其妻曰：君美甚，徐公何能及君也？"},
    # ---------- 古代 · 史记 ----------
    {"id": "shiji_xiangyu", "category": "史记", "title": "史记 · 项羽本纪（节选）", "author": "司马迁",
     "note": "列传笔法 · 人物起笔", "text": "项籍者，下相人也，字羽。初起时，年二十四。其季父项梁，梁父即楚将项燕，为秦将王翦所戮者也。项氏世世为楚将。"},
    {"id": "shiji_chenshe", "category": "史记", "title": "史记 · 陈涉世家（节选）", "author": "司马迁",
     "note": "名篇 · 少时立志", "text": "陈胜者，阳城人也，字涉。吴广者，阳夏人也，字叔。陈涉少时，尝与人佣耕，辍耕之垄上，怅恨久之，曰：苟富贵，无相忘。"},
    {"id": "shiji_lianpo", "category": "史记", "title": "史记 · 廉颇蔺相如列传（节选）", "author": "司马迁",
     "note": "合传开篇 · 句式整齐", "text": "廉颇者，赵之良将也。赵惠文王十六年，廉颇为赵将伐齐，大破之，取阳晋，拜为上卿，以勇气闻于诸侯。蔺相如者，赵人也。"},
    {"id": "shiji_liguang", "category": "史记", "title": "史记 · 李将军列传（节选）", "author": "司马迁",
     "note": "太史公曰 · 名句", "text": "传曰：其身正，不令而行；其身不正，虽令不从。其李将军之谓也？余睹李将军悛悛如鄙人，口不能道辞。及死之日，天下知与不知，皆为尽哀。"},
    {"id": "shiji_baorenan", "category": "史记", "title": "司马迁 · 报任安书（节选）", "author": "司马迁",
     "note": "载于《汉书》· 千古名句", "text": "人固有一死，或重于泰山，或轻于鸿毛，用之所趋异也。亦欲以究天人之际，通古今之变，成一家之言。"},
    # ---------- 古代 · 诸子散文 ----------
    {"id": "zhuzi_lunyu", "category": "诸子散文", "title": "论语（节选）", "author": "",
     "note": "文言短句", "text": "学而时习之，不亦说乎？有朋自远方来，不亦乐乎？学而不思则罔，思而不学则殆。三人行，必有我师焉。"},
    {"id": "zhuzi_mengzi", "category": "诸子散文", "title": "孟子 · 生于忧患（节选）", "author": "孟轲",
     "note": "排比长句", "text": "故天将降大任于是人也，必先苦其心志，劳其筋骨，饿其体肤，空乏其身，行拂乱其所为，所以动心忍性，曾益其所不能。"},
    {"id": "zhuzi_zhuangzi", "category": "诸子散文", "title": "庄子 · 逍遥游（节选）", "author": "庄周",
     "note": "想象奇崛 · 重复句式", "text": "北冥有鱼，其名为鲲。鲲之大，不知其几千里也；化而为鸟，其名为鹏。鹏之背，不知其几千里也；怒而飞，其翼若垂天之云。"},
    {"id": "zhuzi_laozi", "category": "诸子散文", "title": "老子 · 上善若水（节选）", "author": "",
     "note": "短句 · 适合初学", "text": "上善若水。水善利万物而不争，处众人之所恶，故几于道。居善地，心善渊，与善仁，言善信，正善治，事善能，动善时。"},
    {"id": "zhuzi_xunzi", "category": "诸子散文", "title": "荀子 · 劝学（节选）", "author": "荀况",
     "note": "比喻连用", "text": "君子曰：学不可以已。青，取之于蓝，而青于蓝；冰，水为之，而寒于水。木直中绳，輮以为轮，其曲中规。"},
    {"id": "zhuzi_sunzi", "category": "诸子散文", "title": "孙子兵法 · 始计（节选）", "author": "孙武",
     "note": "四字格为主", "text": "兵者，国之大事，死生之地，存亡之道，不可不察也。故经之以五事，校之以计，而索其情：一曰道，二曰天，三曰地，四曰将，五曰法。"},
    # ---------- 古代 · 古文名篇 ----------
    {"id": "guwen_loushiming", "category": "古文名篇", "title": "陋室铭（节选）", "author": "刘禹锡",
     "note": "骈句 · 对仗工整", "text": "山不在高，有仙则名。水不在深，有龙则灵。斯是陋室，惟吾德馨。苔痕上阶绿，草色入帘青。谈笑有鸿儒，往来无白丁。"},
    {"id": "guwen_chushibiao", "category": "古文名篇", "title": "出师表（节选）", "author": "诸葛亮",
     "note": "表文 · 自述身世", "text": "臣本布衣，躬耕于南阳，苟全性命于乱世，不求闻达于诸侯。先帝不以臣卑鄙，猥自枉屈，三顾臣于草庐之中。"},
    {"id": "guwen_taohuayuan", "category": "古文名篇", "title": "桃花源记（节选）", "author": "陶渊明",
     "note": "写景名段 · 四字句多", "text": "晋太元中，武陵人捕鱼为业。缘溪行，忘路之远近。忽逢桃花林，夹岸数百步，中无杂树，芳草鲜美，落英缤纷。"},
    {"id": "guwen_tengwangge", "category": "古文名篇", "title": "滕王阁序（节选）", "author": "王勃",
     "note": "骈文名句", "text": "落霞与孤鹜齐飞，秋水共长天一色。渔舟唱晚，响穷彭蠡之滨；雁阵惊寒，声断衡阳之浦。"},
    {"id": "guwen_yueyanglou", "category": "古文名篇", "title": "岳阳楼记（节选）", "author": "范仲淹",
     "note": "长篇 · 名句收束", "text": "不以物喜，不以己悲；居庙堂之高则忧其民，处江湖之远则忧其君。是进亦忧，退亦忧。然则何时而乐耶？其必曰：先天下之忧而忧，后天下之乐而乐乎。"},
    {"id": "guwen_ailian", "category": "古文名篇", "title": "爱莲说（节选）", "author": "周敦颐",
     "note": "托物言志", "text": "予独爱莲之出淤泥而不染，濯清涟而不妖，中通外直，不蔓不枝，香远益清，亭亭净植，可远观而不可亵玩焉。"},
    {"id": "guwen_chibifu", "category": "古文名篇", "title": "赤壁赋（节选）", "author": "苏轼",
     "note": "赋体 · 对偶句", "text": "寄蜉蝣于天地，渺沧海之一粟。哀吾生之须臾，羡长江之无穷。挟飞仙以遨游，抱明月而长终。知不可乎骤得，托遗响于悲风。"},
    # ---------- 古代 · 唐诗 / 宋词 / 蒙学 / 成语 ----------
    {"id": "tang_jingyesi", "category": "唐诗", "title": "静夜思", "author": "李白",
     "note": "五言绝句 · 20 字", "text": "床前明月光，疑是地上霜。举头望明月，低头思故乡。"},
    {"id": "tang_chunxiao", "category": "唐诗", "title": "春晓", "author": "孟浩然",
     "note": "五言绝句 · 20 字", "text": "春眠不觉晓，处处闻啼鸟。夜来风雨声，花落知多少。"},
    {"id": "tang_dengguanquelou", "category": "唐诗", "title": "登鹳雀楼", "author": "王之涣",
     "note": "五言绝句 · 20 字", "text": "白日依山尽，黄河入海流。欲穷千里目，更上一层楼。"},
    {"id": "tang_wanglushan", "category": "唐诗", "title": "望庐山瀑布", "author": "李白",
     "note": "七言绝句 · 28 字", "text": "日照香炉生紫烟，遥看瀑布挂前川。飞流直下三千尺，疑是银河落九天。"},
    {"id": "tang_jueju", "category": "唐诗", "title": "绝句", "author": "杜甫",
     "note": "七言绝句 · 28 字", "text": "两个黄鹂鸣翠柳，一行白鹭上青天。窗含西岭千秋雪，门泊东吴万里船。"},
    {"id": "tang_jiangxue", "category": "唐诗", "title": "江雪", "author": "柳宗元",
     "note": "五言绝句 · 20 字", "text": "千山鸟飞绝，万径人踪灭。孤舟蓑笠翁，独钓寒江雪。"},
    {"id": "tang_minnong", "category": "唐诗", "title": "悯农", "author": "李绅",
     "note": "五言绝句 · 20 字", "text": "锄禾日当午，汗滴禾下土。谁知盘中餐，粒粒皆辛苦。"},
    {"id": "song_rumengling", "category": "宋词", "title": "如梦令", "author": "李清照",
     "note": "小令 · 长短句断行练习", "text": "昨夜雨疏风骤，浓睡不消残酒。试问卷帘人，却道海棠依旧。知否，知否？应是绿肥红瘦。"},
    {"id": "song_bosuanzi", "category": "宋词", "title": "卜算子", "author": "李之仪",
     "note": "上下阕 · 重复字多", "text": "我住长江头，君住长江尾。日日思君不见君，共饮长江水。此水几时休，此恨何时已。只愿君心似我心，定不负相思意。"},
    {"id": "song_huanxisha", "category": "宋词", "title": "浣溪沙", "author": "晏殊",
     "note": "小令 · 对仗句", "text": "一曲新词酒一杯，去年天气旧亭台。夕阳西下几时回？无可奈何花落去，似曾相识燕归来。小园香径独徘徊。"},
    {"id": "meng_sanzijing", "category": "蒙学", "title": "三字经（节选）", "author": "",
     "note": "三字句 · 适合初学", "text": "人之初，性本善。性相近，习相远。苟不教，性乃迁。教之道，贵以专。昔孟母，择邻处。子不学，断机杼。"},
    {"id": "meng_qianziwen", "category": "蒙学", "title": "千字文（节选）", "author": "",
     "note": "四字句 · 字不重复", "text": "天地玄黄，宇宙洪荒。日月盈昃，辰宿列张。寒来暑往，秋收冬藏。闰余成岁，律吕调阳。"},
    {"id": "meng_dizigui", "category": "蒙学", "title": "弟子规（节选）", "author": "",
     "note": "三字句 · 结构整齐", "text": "弟子规，圣人训。首孝悌，次谨信。泛爱众，而亲仁。有余力，则学文。"},
    {"id": "idiom_common", "category": "成语", "title": "常用成语（一）", "author": "",
     "note": "四字格 · 连续临写", "text": "一心一意三思而行四面八方五光十色六神无主七上八下九牛一毛十全十美百发百中千军万马万象更新日新月异"},
    {"id": "idiom_effort", "category": "成语", "title": "勤学成语（二）", "author": "",
     "note": "四字格 · 连续临写", "text": "业精于勤循序渐进持之以恒温故知新融会贯通举一反三学以致用厚积薄发精益求精水滴石穿"},
    # ---------- 现代 · 散文 ----------
    {"id": "modern_congcong", "category": "现代散文", "title": "匆匆（节选）", "author": "朱自清",
     "note": "1930 年代白话 · 排比句", "text": "燕子去了，有再来的时候；杨柳枯了，有再青的时候；桃花谢了，有再开的时候。但是，聪明的，你告诉我，我们的日子为什么一去不复返呢？"},
    {"id": "modern_beiying", "category": "现代散文", "title": "背影（节选）", "author": "朱自清",
     "note": "动作描写 · 名段", "text": "我看见他戴着黑布小帽，穿着黑布大马褂，深青布棉袍，蹒跚地走到铁道边，慢慢探身下去，尚不大难。"},
    {"id": "modern_hetang", "category": "现代散文", "title": "荷塘月色（节选）", "author": "朱自清",
     "note": "写景 · 叠词多", "text": "曲曲折折的荷塘上面，弥望的是田田的叶子。叶子出水很高，像亭亭的舞女的裙。层层的叶子中间，零星地点缀着些白花。"},
    {"id": "modern_qiuye", "category": "现代散文", "title": "秋夜（节选）", "author": "鲁迅",
     "note": "《野草》开篇 · 短句", "text": "在我的后园，可以看见墙外有两株树，一株是枣树，还有一株也是枣树。这上面的夜的天空，奇怪而高，我生平没有见过这样奇怪而高的天空。"},
    {"id": "modern_baicaoyuan", "category": "现代散文", "title": "从百草园到三味书屋（节选）", "author": "鲁迅",
     "note": "不必说句式 · 名段", "text": "不必说碧绿的菜畦，光滑的石井栏，高大的皂荚树，紫红的桑椹；也不必说鸣蝉在树叶里长吟，肥胖的黄蜂伏在菜花上。"},
    {"id": "modern_jinan", "category": "现代散文", "title": "济南的冬天（节选）", "author": "老舍",
     "note": "口语化白话 · 温润", "text": "设若单单是有阳光，那也算不了出奇。请闭上眼睛想：一个老城，有山有水，全在天底下晒着阳光，暖和安适地睡着，只等春风来把它们唤醒。"},
    {"id": "modern_lahuasheng", "category": "现代散文", "title": "落花生（节选）", "author": "许地山",
     "note": "借物说理 · 短篇", "text": "花生的好处很多，有一样最可贵：它的果实埋在地里，不像桃子、石榴、苹果那样，把鲜红嫩绿的果实高高地挂在枝头上。"},
    {"id": "modern_gudou", "category": "现代散文", "title": "故都的秋（节选）", "author": "郁达夫",
     "note": "开篇 · 长短语交错", "text": "秋天，无论在什么地方的秋天，总是好的；可是啊，北国的秋，却特别地来得清，来得静，来得悲凉。我的不远千里，要从杭州赶上青岛。"},
    {"id": "modern_hulanhe", "category": "现代散文", "title": "呼兰河传（节选）", "author": "萧红",
     "note": "北方风物 · 白描", "text": "严冬一封锁了大地的时候，则大地满地裂着口。从南到北，从东到西，几尺长的，一丈长的，还有好几丈长的，它们毫无方向地，便随时随地只要严冬一到，大地就裂开口了。"},
    # ---------- 现代 · 诗歌 ----------
    {"id": "modern_zaibie", "category": "现代诗歌", "title": "再别康桥（节选）", "author": "徐志摩",
     "note": "新格律诗 · 反复句", "text": "轻轻的我走了，正如我轻轻的来；我轻轻的招手，作别西天的云彩。那河畔的金柳，是夕阳中的新娘；波光里的艳影，在我的心头荡漾。"},
    {"id": "modern_sishui", "category": "现代诗歌", "title": "死水（节选）", "author": "闻一多",
     "note": "三美主张 · 整齐句", "text": "这是一沟绝望的死水，清风吹不起半点漪沦！不如多扔些破铜烂铁，爽性泼你的剩菜残羹。也许铜的要绿成翡翠，铁罐上锈出几瓣桃花。"},
    {"id": "modern_yuxiang", "category": "现代诗歌", "title": "雨巷（节选）", "author": "戴望舒",
     "note": "象征派 · 长句", "text": "撑着油纸伞，独自彷徨在悠长、悠长又寂寥的雨巷，我希望逢着一个丁香一样地结着愁怨的姑娘。她是有丁香一样的颜色，丁香一样的芬芳。"},
    {"id": "modern_buxiangta", "category": "现代诗歌", "title": "教我如何不想她（节选）", "author": "刘半农",
     "note": "早期白话诗 · 短句", "text": "天上飘着些微云，地上吹着些微风。啊！微风吹动了我头发，教我如何不想她？月光恋爱着海洋，海洋恋爱着月光。"},
    # ---------- 现代 · 杂文 ----------
    {"id": "modern_tici", "category": "现代杂文", "title": "野草 · 题辞（节选）", "author": "鲁迅",
     "note": "箴言式短句", "text": "当我沉默着的时候，我觉得充实；我将开口，同时感到空虚。过去的生命已经死亡。我对于这死亡有大欢喜，因为我借此知道它曾经存活。"},
    {"id": "modern_chabuduo", "category": "现代杂文", "title": "差不多先生传（节选）", "author": "胡适",
     "note": "白话议论 · 反讽", "text": "你知道中国最有名的人是谁？提起此人，人人皆晓，处处闻名。他姓差，名不多，是各省各县各村人氏。你一定见过他，一定听过别人谈起他。"},
)

# 一级时代 → 二级体裁；前端据此做「全部 / 古代 / 现代」筛选
ERA_OF_CATEGORY: dict[str, str] = {
    "先秦史传": "古代", "史记": "古代", "诸子散文": "古代", "古文名篇": "古代",
    "唐诗": "古代", "宋词": "古代", "蒙学": "古代", "成语": "古代",
    "现代散文": "现代", "现代诗歌": "现代", "现代杂文": "现代",
}
LIBRARY_CATEGORIES = tuple(ERA_OF_CATEGORY)

# 给每篇补上时代字段，避免逐条重复书写
LIBRARY: tuple[dict, ...] = tuple(
    {**p, "era": ERA_OF_CATEGORY.get(p["category"], "古代")} for p in _RAW_LIBRARY
)


def list_library() -> list[dict]:
    """按体裁分组，并给组和篇目都挂上时代，供前端做两级筛选"""
    groups = []
    for cat in LIBRARY_CATEGORIES:
        era = ERA_OF_CATEGORY.get(cat, "古代")
        items = [
            {"id": p["id"], "title": p["title"], "author": p["author"],
             "note": p["note"], "text": p["text"], "count": len(p["text"]),
             "era": p["era"]}
            for p in LIBRARY if p["category"] == cat
        ]
        if items:
            groups.append({"id": cat, "name": cat, "era": era, "items": items})
    return groups


def get_passage(key: str) -> dict | None:
    return next((p for p in LIBRARY if p["id"] == key), None)


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
    result.update(_graded_sets(result))
    return result


def list_sets() -> list[dict]:
    data = load()
    order = ["freq1000", "freq3500", "grade1", "grade2", "grade3", "radicals", "strokes"]
    keys = [k for k in order if k in data] + [k for k in data if k not in order]
    return [{"id": k, "name": data[k]["name"], "desc": data[k]["desc"], "count": data[k]["count"]}
            for k in keys]


def get(key: str) -> dict | None:
    return load().get(key)
