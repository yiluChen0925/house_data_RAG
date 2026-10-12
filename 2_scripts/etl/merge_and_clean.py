# -*- coding: utf-8 -*-
"""房产数据合并与清洗。

按字段名读取，不按列号。四个源的列序各不相同（成交 16 列 / 二手 44 列 /
新房 54 列 / 58同城 34 列），爬虫解析器产出的又是 47 个具名字段，按列号取会串位——
房天下房源页的"户型"格经常只给朝向，按列号读会把它当成户型。

合并总数应为 15067。如果看到 7512，说明 raw_data 下又变成了同一个成交文件
被复制成四份的老样子。
"""

import glob
import os
import re

import numpy as np
import pandas as pd

try:
    from ETL_cleaners import clean_numeric
except ImportError:  # 允许从其他 cwd 调用
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ETL_cleaners import clean_numeric


# ==================== 路径配置 ====================
DEFAULT_BASE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)

COMMON_FIELDS = ["城市", "区域", "户型", "总价", "面积", "单价", "小区名称", "爬取时间"]
EXTRA_FIELDS = ["朝向"]  # 朝向是独立语义，不混进户型


def get_paths(base_path=None):
    """返回 (raw_folder, cleaned_folder, output_file)。"""
    base = base_path or DEFAULT_BASE_PATH
    raw_folder = os.path.join(base, "1_data", "raw_data")
    cleaned_folder = os.path.join(base, "1_data", "cleaned_data")
    return raw_folder, cleaned_folder, os.path.join(cleaned_folder, "house_cleaned.csv")


# ==================== 数据源识别 ====================
def identify_source(filename):
    """按文件名判断数据源。顺序有讲究：先排除 wuba/58，再判断 ershou。"""
    name = os.path.basename(filename).lower()
    if "chengjiao" in name:
        return "ftx_chengjiao"
    if "wuba" in name or "58" in name:
        return "wuba_ershou"
    if "xinfang" in name or "loupan" in name:
        return "ftx_xinfang"
    if "ershou" in name:
        return "ftx_ershou"
    return None


# ==================== 按字段名取值的工具 ====================
def pick(row, names, default=None):
    """按候选列名依次取值，返回第一个非空值（nan/空串视为空）。"""
    if not names:
        return default
    for name in names:
        if name not in row.index:
            continue
        value = row[name]
        if value is None:
            continue
        if isinstance(value, float) and np.isnan(value):
            continue
        text = str(value).strip()
        if text == "" or text.lower() == "nan":
            continue
        return value
    return default


DISTRICTS = [
    # 长的放前面：匹配逻辑是"片段包含区名"，'大鹏新区' 必须先于 '大鹏' 命中
    '大鹏新区', '坪山', '光明', '盐田',
    '南山', '福田', '罗湖', '宝安', '龙岗', '龙华',
    '天河', '越秀', '海珠', '荔湾', '白云', '黄埔', '番禺', '花都', '南沙', '增城', '从化',
    '禅城', '南海', '顺德', '三水', '高明',
    '莞城', '南城', '万江', '虎门', '长安', '松山湖', '塘厦', '厚街', '常平', '寮步',
    '惠城', '惠阳', '仲恺', '大亚湾', '惠东', '博罗',
]
# 长名优先，避免 '大亚湾' 被 '大亚' 之类短名抢先（当前名单无此问题，防御性排序）
DISTRICTS = sorted(DISTRICTS, key=len, reverse=True)


def extract_district_from_address(address):
    """从地址或区域串里抽区名，抽不到返回 None。

    各源写法很乱：'福田区-八卦岭'、'海珠 赤岗'、'南海大沥'、'大鹏新区坪葵路…'。
    按分隔符切段后逐段匹配区名；整串没有分隔符时（新房地址常见）就在全串里找。
    不做"截断再拼区"，否则会拼出 '东坑东坑区' 这种值。
    """
    if address is None:
        return None
    text = str(address).strip()
    if text == "" or text.lower() == "nan":
        return None

    def hit(segment):
        chunk = segment.strip()
        if not chunk:
            return None
        for d in DISTRICTS:
            if d in chunk:
                return d if d.endswith('区') else d + '区'
        return None

    segments = [s for s in re.split(r'[-—–\s/|,，]', text) if s.strip()]
    if segments:
        # 只在第一段里找：区域字段的区名总在最前面，后面的段是片区/板块
        return hit(segments[0])
    return hit(text)


def normalize_district(value):
    """把各源的区域字段统一成 'XX区'。

    各源写法不同：
        - 成交/旧位置化文件：'福田区-八卦岭'、'万江区-万江中心'（区+片区）
        - 58 同城：'黄埔'、'番禺'（没有"区"字）
        - 房天下二手：'花都新区'、'南海大沥'
        - 新房：只有地址，需要从里面抽
    统一成纯区名并丢掉片区——片区在过滤链路里从没被用到，留着只会让同一个区
    出现多种写法，反而增加漏召回。抽不到区名的一律留空（宁缺勿错）。
    """
    return extract_district_from_address(value)


def normalize_datetime(value):
    """把 '17/3/2026 01:13:47'(d/m/Y) 和 '2026-03-17 01:13:47' 统一成 ISO。

    d/m/Y 与 m/d/Y 有歧义：这里按爬虫的惯例（日在前）解析，并校验月份合法。
    """
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return None
    # 已经是 ISO 就打头 19 位
    iso = re.match(r'^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}):(\d{2}))?', text)
    if iso:
        y, m, d, hh, mm, ss = iso.groups()
        return "{}-{}-{} {}:{}:{}".format(y, m, d, hh or "00", mm or "00", ss or "00")
    slash = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}):(\d{2}))?', text)
    if slash:
        a, b, y, hh, mm, ss = slash.groups()
        day, month = int(a), int(b)
        if month > 12 and day <= 12:  # 明显是 m/d 的写法
            day, month = month, day
        try:
            return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                int(y), month, day, int(hh or 0), int(mm or 0), int(ss or 0))
        except ValueError:
            return text
    return text


# ==================== 各数据源的字段映射 ====================
# 每个目标字段给一串候选表头名，按顺序取第一个非空。
# 兼容三种来源：daily_raw/ 的 47 列解析器产物、桌面原始导出、旧的 28 列位置化文件。
SOURCE_FIELD_MAP = {
    "ftx_chengjiao": {
        "城市": ["city_name"],
        "区域": ["district"],
        "户型": ["house_layout"],
        "总价": ["total_price"],
        "面积": ["build_area"],
        "单价": ["unit_price"],
        "小区名称": ["community_name"],
        "爬取时间": ["crawl_time"],
        "朝向": ["orientation", "house_orientation"],
    },
    "ftx_ershou": {
        "城市": ["city_name"],
        # 房天下二手的 house_area 是"行政区+片区"（如 花都新区 / 南海大沥）
        "区域": ["region_name", "district", "house_area"],
        # 注意：房天下房源页的"户型"格子经常只给朝向（南/北/东南），这是源头如此
        "户型": ["house_layout"],
        "总价": ["total_price"],
        "面积": ["build_area"],
        "单价": ["unit_price"],
        "小区名称": ["community_name"],
        "爬取时间": ["crawl_time"],
        "朝向": ["house_orientation"],
    },
    "ftx_xinfang": {
        "城市": ["city_name"],
        # 新房没有区域字段，从 address 里抽
        "区域": ["district", "house_area", "region_name"],
        "户型": ["house_layout", "main_huxing", "huxing_detail"],
        "总价": ["total_price", "total_price_range"],
        "面积": ["build_area"],
        # 新房的 price / unit_price 都是"均价(元/㎡)"，不是总价，见 _postprocess
        "单价": ["unit_price", "price"],
        "小区名称": ["community_name", "loupan_name"],
        "爬取时间": ["crawl_time"],
        "朝向": ["house_orientation", "orientation"],
    },
    "wuba_ershou": {
        "城市": ["city_name"],
        "区域": ["region_name", "district", "house_area"],
        "户型": ["house_layout"],
        "总价": ["total_price"],
        "面积": ["build_area"],
        # 58 同城没有单价列，交给 clean_and_fix 用 总价/面积 推算
        "单价": ["unit_price"],
        "小区名称": ["community_name"],
        "爬取时间": ["crawl_time"],
        "朝向": ["house_orientation"],
    },
}

# 旧的位置化文件（raw_*.csv，无表头行）的列号 → 字段名
POSITIONAL_COLUMNS = {
    0: "id", 1: "crawl_time", 2: "city_abbr", 3: "city_name", 4: "source_url",
    5: "community_name", 6: "house_layout", 7: "build_area", 8: "orientation",
    9: "floor_info", 10: "district", 11: "deal_date", 12: "total_price",
    13: "unit_price",
}

# 表头探测：出现这些字段名基本可断定首行是表头
HEADER_HINTS = {
    "crawl_time", "city_name", "community_name", "house_layout",
    "build_area", "total_price", "unit_price", "id", "city_abbr",
}


def _extract_area_from_detail(raw_df):
    """从 huxing_detail 里抽面积。

    字段长这样：
        "面积：D户型|结构：4室2厅1厨2卫|建面：106㎡(建面)|状态：待售面积：A户型|..."
    一个楼盘会有多个户型，取其中最大的建面作为该房源的面积，
    并且只在 "建面：" 后面紧跟着数字+m² 时才取（避免把 "面积：3栋一单元02户型" 当成面积）。
    """
    if "huxing_detail" not in raw_df.columns:
        return None
    text = raw_df["huxing_detail"].fillna("").astype(str)
    return text.str.findall(r'建面：(\d+(?:\.\d+)?)').apply(
        lambda values: max((float(v) for v in values), default=None)
        if isinstance(values, (list, tuple, np.ndarray)) else None
    )


def _extract_layout_from_detail(raw_df):
    """从 huxing_detail 里抽主推户型（第一个 "结构：3室2厅1厨1卫"）。"""
    if "huxing_detail" not in raw_df.columns:
        return None
    text = raw_df["huxing_detail"].fillna("").astype(str)
    return text.str.extract(r'结构：(\d室\d厅\d厨\d卫)')[0]


def _layout_from_main_huxing(value):
    """新房 main_huxing 兜底：'三居(3)四居(1)' -> '3室'（取最小居室，即主推的起步户型）。"""
    chinese_num = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7}
    matches = re.findall(r'([一二三四五六七])居\((\d+)\)', str(value))
    if not matches:
        return None
    counts = []
    for cn, num in matches:
        try:
            counts.append(int(num))
        except ValueError:
            counts.append(chinese_num.get(cn, 0))
    counts = [c for c in counts if c > 0]
    if not counts:
        return None
    return str(min(counts)) + "室"


def _layout_from_area(area):
    """按面积粗推户型档位（有损推断，只用于让"几房"过滤能命中）。"""
    try:
        value = float(area)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    if value < 60:
        return "1室"
    if value < 90:
        return "2室"
    if value < 130:
        return "3室"
    if value < 170:
        return "4室"
    return "5室"


def read_source(file, source_type):
    """读取单个数据源文件，返回带统一中文字段的 DataFrame。"""
    # 先按"没有表头"读一小段，判断首行到底是表头还是数据
    probe = pd.read_csv(file, encoding='utf-8-sig', header=None, nrows=3,
                        low_memory=False, on_bad_lines='skip')
    first_row = {str(v).strip() for v in probe.iloc[0].tolist()}
    has_header = len(first_row & HEADER_HINTS) >= 2

    if has_header:
        df = pd.read_csv(file, encoding='utf-8-sig', header=0,
                         low_memory=False, on_bad_lines='skip')
    else:
        # 没有表头的旧位置化文件：按列号补上字段名
        df = pd.read_csv(file, encoding='utf-8-sig', header=None,
                         low_memory=False, on_bad_lines='skip')
        df = df.rename(columns=POSITIONAL_COLUMNS)

    # 只在读取阶段能做的推算：这里还拿得到原始列（huxing_detail / address / main_huxing）
    detail_area = _extract_area_from_detail(df)
    detail_layout = _extract_layout_from_detail(df)

    mapping = SOURCE_FIELD_MAP[source_type]
    rows = []
    for idx, (_, row) in enumerate(df.iterrows()):
        record = {}
        for target, candidates in mapping.items():
            record[target] = pick(row, candidates)

        # 户型兜底：房天下房源页的"户型"格常常只给朝向，真正的户型在 huxing_detail 里
        layout_is_orientation = (
            source_type in ("ftx_ershou", "wuba_ershou")
            and not re.search(r'\d\s*[室居]', str(record.get("户型")))
        )
        if layout_is_orientation:
            fallback = detail_layout.iloc[idx] if detail_layout is not None else None
            if isinstance(fallback, str) and fallback.strip():
                record["户型"] = fallback
            else:
                # 实在没有户型：宁可留空，也不要把"南"当成户型污染检索
                record["户型"] = None

        # 面积兜底：二手房大量缺面积，能抽到就补
        area = clean_numeric(record.get("面积"))
        if area <= 0 and detail_area is not None:
            record["面积"] = detail_area.iloc[idx] if detail_area is not None else None

        # 区域：新房没有区域字段，只有 address
        if source_type == "ftx_xinfang" and not record.get("区域"):
            record["区域"] = extract_district_from_address(pick(row, ["address", "sale_address"]))

        # 新房：主推户型在 huxing_detail 的 "结构：3室2厅1厨1卫" 里，main_huxing 只给
        # "三居(3)四居(1)" 这种粗粒度串（见 _postprocess 里的 fallback）。
        if source_type == "ftx_xinfang":
            record["户型"] = detail_layout.iloc[idx] if detail_layout is not None else None

        # 爬取时间统一成 ISO，避免 d/m/Y 与 Y-m-d 混在一起
        record["爬取时间"] = normalize_datetime(record.get("爬取时间"))
        record["数据来源"] = source_type
        rows.append(record)

    out = pd.DataFrame(rows)
    return _postprocess(out, source_type, df)


def _postprocess(df, source_type, raw_df):
    """处理各源特有的坑：单位为"元/㎡"的均价、缺面积、户型混朝向等。"""
    if source_type == "ftx_xinfang":
        # 新房的 price/unit_price 都是均价（元/㎡）。没有总价就用 单价*面积 反推，
        # 绝不能把 37000 直接当成"37000 万"。
        if "总价" in df.columns:
            df["总价"] = np.nan
        # 户型兜底：huxing_detail 抽不到时，用 main_huxing "三居(3)四居(1)" -> "3室"
        if "户型" in df.columns and "main_huxing" in raw_df.columns:
            missing_layout = df["户型"].isna() | df["户型"].astype(str).str.strip().isin(["", "nan", "暂无"])
            df.loc[missing_layout, "户型"] = raw_df.loc[missing_layout, "main_huxing"].apply(_layout_from_main_huxing)
        # 最后一道：新房只有总价+均价，可由 总价*10000/单价 得到面积，再按面积推户型档位。
        # 这是有损推断，仅用于让"几房"这类粗过滤能命中，精确户型仍以 huxing_detail 为准。
        if "户型" in df.columns:
            area = pd.to_numeric(df["面积"], errors="coerce")
            total = pd.to_numeric(df["总价"], errors="coerce")
            unit = pd.to_numeric(df["单价"], errors="coerce")
            implied = (total * 10000 / unit).where(unit > 0)
            area = area.where(area > 0, implied)
            guess = area.apply(_layout_from_area)
            missing_layout = df["户型"].isna() | df["户型"].astype(str).str.strip().isin(["", "nan", "暂无"])
            df.loc[missing_layout, "户型"] = guess[missing_layout]

    # 各源的 huxing_detail 都再兜一道面积
    if source_type in ("ftx_ershou", "wuba_ershou", "ftx_xinfang"):
        detail_area = _extract_area_from_detail(raw_df)
        if detail_area is not None:
            current = pd.to_numeric(df["面积"], errors="coerce").fillna(0)
            df.loc[current == 0, "面积"] = detail_area[current == 0]

    if source_type in ("ftx_chengjiao", "ftx_ershou", "wuba_ershou", "ftx_xinfang"):
        # 区域统一成 "XX区"（各源写法不同，见 normalize_district 的说明）
        df["区域"] = [normalize_district(v) for v in df["区域"]]

    return df


# ==================== 合并 ====================
def merge_all(raw_folder, verbose=True):
    all_files = sorted(glob.glob(os.path.join(raw_folder, "*.csv")))
    if not all_files:
        raise FileNotFoundError("在 " + raw_folder + " 下没有找到CSV文件")

    df_list = []
    skipped = []
    for file in all_files:
        source = identify_source(file)
        if not source:
            skipped.append(os.path.basename(file))
            continue
        if verbose:
            print("读取 " + os.path.basename(file) + " -> " + source)
        df = read_source(file, source)
        missing = [c for c in COMMON_FIELDS + EXTRA_FIELDS if c not in df.columns]
        for col in missing:
            df[col] = None
        df_list.append(df[COMMON_FIELDS + EXTRA_FIELDS + ["数据来源"]])

    if skipped and verbose:
        print("跳过未知数据源: " + ", ".join(skipped))
    if not df_list:
        raise ValueError("没有成功读取任何数据")

    df_all = pd.concat(df_list, ignore_index=True)
    if verbose:
        print("合并完成，总数据量: " + str(len(df_all)) + " 条")
        print("各来源行数:")
        for source, count in df_all["数据来源"].value_counts().items():
            print("   - " + str(source) + ": " + str(count))
    return df_all


# ==================== 清洗 ====================
def clean_and_fix(df, verbose=True):
    if verbose:
        print("开始清洗与推算...")

    for field in ["总价", "面积", "单价"]:
        if field in df.columns:
            df[field] = df[field].apply(clean_numeric)
        else:
            df[field] = np.nan

    mask = (df["总价"] > 0) & (df["面积"] > 0) & (pd.isna(df["单价"]) | (df["单价"] == 0))
    df.loc[mask, "单价"] = df.loc[mask, "总价"] * 10000 / df.loc[mask, "面积"]

    mask = (df["单价"] > 0) & (df["面积"] > 0) & (pd.isna(df["总价"]) | (df["总价"] == 0))
    df.loc[mask, "总价"] = df.loc[mask, "单价"] * df.loc[mask, "面积"] / 10000

    mask = (df["总价"] > 0) & (df["单价"] > 0) & (pd.isna(df["面积"]) | (df["面积"] == 0))
    df.loc[mask, "面积"] = df.loc[mask, "总价"] * 10000 / df.loc[mask, "单价"]

    if "区域" in df.columns and df["区域"].notna().any():
        valid = df[df["区域"].notna() & (df["单价"] > 0)]
        if not valid.empty:
            df_region_avg = valid.groupby(["城市", "区域"])["单价"].median().reset_index()
            df_region_avg.rename(columns={"单价": "区域均价"}, inplace=True)
            df = pd.merge(df, df_region_avg, on=["城市", "区域"], how="left")

            if "区域均价" in df.columns:
                mask_anomaly = (
                    (df["单价"] > 0) &
                    (df["区域均价"] > 0) &
                    (np.abs(df["单价"] - df["区域均价"]) / df["区域均价"] > 0.5)
                )
                df.loc[mask_anomaly, "单价"] = df.loc[mask_anomaly, "区域均价"]
                mask_fix_total = mask_anomaly & (df["面积"] > 0)
                df.loc[mask_fix_total, "总价"] = (
                    df.loc[mask_fix_total, "单价"] * df.loc[mask_fix_total, "面积"] / 10000
                )
                df.drop(columns=["区域均价"], inplace=True, errors="ignore")

    for col in ["总价", "面积", "单价"]:
        if col in df.columns:
            df[col] = df[col].round(2)

    final_cols = [col for col in COMMON_FIELDS if col in df.columns]
    final_cols += [col for col in EXTRA_FIELDS if col in df.columns]
    if "数据来源" in df.columns:
        final_cols.append("数据来源")
    df = df[final_cols]

    if verbose:
        print("清洗完成，共 " + str(len(df)) + " 条数据")
        print("   - 有总价: " + str(df['总价'].notna().sum()) + " 条")
        print("   - 有面积: " + str(df['面积'].notna().sum()) + " 条")
        print("   - 有单价: " + str(df['单价'].notna().sum()) + " 条")
        print("   - 有爬取时间: " + str(df['爬取时间'].notna().sum()) + " 条")
    return df


def run(base_path=None, verbose=True):
    raw_folder, cleaned_folder, output_file = get_paths(base_path)
    os.makedirs(raw_folder, exist_ok=True)
    os.makedirs(cleaned_folder, exist_ok=True)
    if verbose:
        print("原始数据目录: " + raw_folder)
        print("输出目录: " + cleaned_folder)
    df = merge_all(raw_folder, verbose=verbose)
    df = clean_and_fix(df, verbose=verbose)
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    if verbose:
        print("清洗后的数据已保存至: " + output_file)
        print("\n前5行预览:")
        print(df.head())
    return df, output_file


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print("执行出错: " + str(e))
        import traceback
        traceback.print_exc()
