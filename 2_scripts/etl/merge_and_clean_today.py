# -*- coding: utf-8 -*-
"""
每日增量追加脚本 - 每天运行一次
从 daily_raw 读取今天的新数据，清洗后追加到 house_cleaned.csv
"""

import pandas as pd
import numpy as np
import glob
import os
import datetime
from ETL_cleaners import clean_numeric

# ==================== 路径配置 ====================
BASE_PATH = r"D:\MyProject\house_data_RAG"
DAILY_RAW_FOLDER = os.path.join(BASE_PATH, "1_data", "daily_raw")
CLEANED_FOLDER = os.path.join(BASE_PATH, "1_data", "cleaned_data")
OUTPUT_FILE = os.path.join(CLEANED_FOLDER, "house_cleaned.csv")

os.makedirs(DAILY_RAW_FOLDER, exist_ok=True)
os.makedirs(CLEANED_FOLDER, exist_ok=True)

COMMON_FIELDS = ["城市", "区域", "户型", "总价", "面积", "单价", "小区名称", "爬取时间"]


def clean_and_fix(df):
    """清洗和推算逻辑（与初始脚本一致）"""
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

    return df


def read_daily_raw(file):
    """读取 daily_raw 目录下的 CSV，映射到 COMMON_FIELDS"""
    df = pd.read_csv(file, encoding='utf-8-sig')

    column_mapping = {
        "crawl_time": "爬取时间",
        "community_name": "小区名称",
        "house_layout": "户型",
        "build_area": "面积",
        "total_price": "总价",
        "unit_price": "单价",
        "house_area": "区域",
        "city_name": "城市",
    }
    df = df.rename(columns=column_mapping)

    for col in COMMON_FIELDS:
        if col not in df.columns:
            df[col] = None

    df["数据来源"] = "daily_raw"

    keep_cols = COMMON_FIELDS + ["数据来源"]
    df = df[keep_cols]

    return df


def load_existing_data():
    """加载已有的 house_cleaned.csv"""
    if os.path.exists(OUTPUT_FILE):
        return pd.read_csv(OUTPUT_FILE, encoding='utf-8-sig')
    else:
        print("未找到已存在的 house_cleaned.csv，请先运行 merge_initial.py")
        return pd.DataFrame()


def main():
    today_str = datetime.datetime.now().strftime('%Y%m%d')

    print("开始处理今日数据: " + today_str)

    daily_files = glob.glob(os.path.join(DAILY_RAW_FOLDER, f"*{today_str}*.csv"))
    if not daily_files:
        print("今日没有新数据，无需追加")
        return

    df_new_list = []
    for file in daily_files:
        print("读取: " + os.path.basename(file))
        df = read_daily_raw(file)
        df_new_list.append(df)

    df_new = pd.concat(df_new_list, ignore_index=True)
    print("今日新增: " + str(len(df_new)) + " 条")

    df_new = clean_and_fix(df_new)

    df_existing = load_existing_data()
    if df_existing.empty:
        print("未找到已有数据，建议先运行 merge_initial.py 初始化")
        df_new.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        print("已保存 " + str(len(df_new)) + " 条数据到 " + OUTPUT_FILE)
        return

    if "房源编码" in df_new.columns and "房源编码" in df_existing.columns:
        existing_codes = set(df_existing["房源编码"].dropna())
        df_new = df_new[~df_new["房源编码"].isin(existing_codes)]
        print("去重后保留: " + str(len(df_new)) + " 条新数据")

    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    df_combined.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')

    print("追加完成")
    print("   - 原有数据: " + str(len(df_existing)) + " 条")
    print("   - 今日新增: " + str(len(df_new)) + " 条")
    print("   - 合并后: " + str(len(df_combined)) + " 条")
    print("已保存至: " + OUTPUT_FILE)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("执行出错: " + str(e))
        import traceback
        traceback.print_exc()