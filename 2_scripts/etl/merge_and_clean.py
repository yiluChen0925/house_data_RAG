# -*- coding: utf-8 -*-
"""
房产数据合并与清洗脚本（全量初始合并）
从 raw_data 读取原始数据，清洗后生成 house_cleaned.csv
"""

import pandas as pd
import numpy as np
import glob
import os
from ETL_cleaners import clean_numeric

# ==================== 路径配置 ====================
BASE_PATH = r"D:\MyProject\house_data_RAG"
RAW_FOLDER = os.path.join(BASE_PATH, "1_data", "raw_data")
CLEANED_FOLDER = os.path.join(BASE_PATH, "1_data", "cleaned_data")
OUTPUT_FILE = os.path.join(CLEANED_FOLDER, "house_cleaned.csv")

os.makedirs(RAW_FOLDER, exist_ok=True)
os.makedirs(CLEANED_FOLDER, exist_ok=True)

print("原始数据目录: " + RAW_FOLDER)
print("输出目录: " + CLEANED_FOLDER)

COMMON_FIELDS = ["城市", "区域", "户型", "总价", "面积", "单价", "小区名称", "爬取时间"]


def identify_source(filename):
    name = os.path.basename(filename).lower()
    if "chengjiao" in name:
        return "ftx_chengjiao"
    elif "ershou" in name and "wuba" not in name and "58" not in name:
        return "ftx_ershou"
    elif "wuba" in name or "58" in name:
        return "wuba_ershou"
    elif "xinfang" in name:
        return "ftx_xinfang"
    else:
        return None


def extract_district_from_address(address):
    if pd.isna(address):
        return None
    districts = [
        '南山', '福田', '罗湖', '宝安', '龙岗', '龙华', '光明', '坪山', '盐田',
        '天河', '越秀', '海珠', '荔湾', '白云', '黄埔', '番禺', '花都', '南沙',
        '禅城', '南海', '顺德', '三水', '高明',
        '莞城', '南城', '万江', '虎门', '长安',
        '惠城', '惠阳', '仲恺', '大亚湾'
    ]
    for d in districts:
        if d in str(address):
            return d + '区'
    return None


def read_positional(file, source_type):
    df_raw = pd.read_csv(file, encoding='utf-8-sig', header=None, low_memory=False)
    rows = []
    for _, row in df_raw.iterrows():
        parts = row.tolist()
        while len(parts) < 14:
            parts.append(None)

        crawl_time = parts[1][:10] if len(parts) > 1 and parts[1] else None
        city = parts[3] if len(parts) > 3 else None
        name = parts[5] if len(parts) > 5 else None
        layout = parts[6] if len(parts) > 6 else None
        area = parts[7] if len(parts) > 7 else None
        district_or_addr = parts[10] if len(parts) > 10 else None
        total_price = parts[12] if len(parts) > 12 else None
        unit_price = parts[13] if len(parts) > 13 else None

        if source_type == "ftx_xinfang":
            district = extract_district_from_address(district_or_addr)
        else:
            district = district_or_addr

        rows.append({
            "城市": city,
            "区域": district,
            "户型": layout,
            "总价": total_price,
            "面积": area,
            "单价": unit_price,
            "小区名称": name,
            "爬取时间": crawl_time,
            "数据来源": source_type
        })
    return pd.DataFrame(rows)


def read_ftx_chengjiao(file):
    return read_positional(file, "ftx_chengjiao")


def read_ftx_ershou(file):
    return read_positional(file, "ftx_ershou")


def read_ftx_xinfang(file):
    return read_positional(file, "ftx_xinfang")


def read_wuba_ershou(file):
    return read_positional(file, "wuba_ershou")


def merge_all():
    all_files = glob.glob(os.path.join(RAW_FOLDER, "*.csv"))
    if not all_files:
        raise FileNotFoundError("在 " + RAW_FOLDER + " 下没有找到CSV文件")

    df_list = []
    for file in all_files:
        source = identify_source(file)
        if not source:
            print("跳过未知数据源: " + file)
            continue

        print("读取 " + os.path.basename(file) + " -> " + source)

        if source == "ftx_chengjiao":
            df = read_ftx_chengjiao(file)
        elif source == "ftx_ershou":
            df = read_ftx_ershou(file)
        elif source == "ftx_xinfang":
            df = read_ftx_xinfang(file)
        elif source == "wuba_ershou":
            df = read_wuba_ershou(file)
        else:
            continue

        for col in COMMON_FIELDS:
            if col not in df.columns:
                df[col] = None

        if "数据来源" not in df.columns:
            df["数据来源"] = source

        keep_cols = COMMON_FIELDS + ["数据来源"]
        df = df[keep_cols]
        df_list.append(df)

    if not df_list:
        raise ValueError("没有成功读取任何数据")

    df_all = pd.concat(df_list, ignore_index=True)
    print("合并完成，总数据量: " + str(len(df_all)) + " 条")
    return df_all


def clean_and_fix(df):
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
                df.loc[mask_fix_total, "总价"] = df.loc[mask_fix_total, "单价"] * df.loc[mask_fix_total, "面积"] / 10000
                df.drop(columns=["区域均价"], inplace=True, errors="ignore")

    for col in ["总价", "面积", "单价"]:
        if col in df.columns:
            df[col] = df[col].round(2)

    final_cols = [col for col in COMMON_FIELDS if col in df.columns]
    if "数据来源" in df.columns:
        final_cols.append("数据来源")
    df = df[final_cols]

    print("清洗完成，共 " + str(len(df)) + " 条数据")
    print("   - 有总价: " + str(df['总价'].notna().sum()) + " 条")
    print("   - 有面积: " + str(df['面积'].notna().sum()) + " 条")
    print("   - 有单价: " + str(df['单价'].notna().sum()) + " 条")
    print("   - 有爬取时间: " + str(df['爬取时间'].notna().sum()) + " 条")
    return df


if __name__ == "__main__":
    try:
        df = merge_all()
        df = clean_and_fix(df)
        df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        print("清洗后的数据已保存至: " + OUTPUT_FILE)
        print("\n前5行预览:")
        print(df.head())
    except Exception as e:
        print("执行出错: " + str(e))
        import traceback
        traceback.print_exc()