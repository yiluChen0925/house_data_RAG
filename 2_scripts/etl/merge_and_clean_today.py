# -*- coding: utf-8 -*-
"""
每日增量追加脚本 - 每天运行一次

从 1_data/daily_raw 读取今天的新数据，清洗后追加到 house_cleaned.csv。

改动要点：
    原来这个脚本自带一份 read_daily_raw()，按字段名映射——方向是对的，但和
    merge_and_clean.py 各写一份，两边的映射会各自漂移（例如 region_name 没被
    映射、户型混朝向的问题只在一边修）。现在统一复用 merge_and_clean 的读取
    与清洗逻辑，只保留"追加 + 去重"这部分增量特有的行为。
"""

import datetime
import glob
import os
import sys

import pandas as pd

# 允许以脚本方式直接运行（python 2_scripts/etl/merge_and_clean_today.py）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from merge_and_clean import (  # noqa: E402
    DEFAULT_BASE_PATH,
    clean_and_fix,
    get_paths,
    identify_source,
    read_source,
)


def get_daily_folder(base_path=None):
    base = base_path or DEFAULT_BASE_PATH
    return os.path.join(base, "1_data", "daily_raw")


def load_existing_data(output_file):
    """加载已有的 house_cleaned.csv。"""
    if os.path.exists(output_file):
        return pd.read_csv(output_file, encoding='utf-8-sig')
    print("未找到已存在的 house_cleaned.csv，本次将直接写入新数据")
    return pd.DataFrame()


def dedupe(df_new, df_existing):
    """有房源编码就按编码去重；否则按 (城市, 小区名称, 户型, 总价) 兜底。"""
    if df_new.empty or df_existing.empty:
        return df_new
    if "房源编码" in df_new.columns and "房源编码" in df_existing.columns:
        existing = set(df_existing["房源编码"].dropna())
        return df_new[~df_new["房源编码"].isin(existing)]
    key_cols = [c for c in ["城市", "小区名称", "户型", "总价"] if c in df_new.columns]
    if not key_cols:
        return df_new
    existing_keys = set(map(tuple, df_existing[key_cols].astype(str).values))
    new_keys = list(map(tuple, df_new[key_cols].astype(str).values))
    return df_new[[k not in existing_keys for k in new_keys]]


def main(base_path=None, date_str=None, verbose=True):
    base = base_path or DEFAULT_BASE_PATH
    daily_folder = get_daily_folder(base)
    _, cleaned_folder, output_file = get_paths(base)
    os.makedirs(daily_folder, exist_ok=True)
    os.makedirs(cleaned_folder, exist_ok=True)

    # date_str 可显式指定（daily_ingest 会传），默认今天
    today_str = date_str or datetime.datetime.now().strftime('%Y%m%d')
    print("开始处理数据日期: " + today_str)
    print("增量目录: " + daily_folder)

    daily_files = sorted(glob.glob(os.path.join(daily_folder, "*" + today_str + "*.csv")))
    if not daily_files:
        print("该日期没有新数据，无需追加")
        return None

    frames = []
    for file in daily_files:
        name = os.path.basename(file)
        source = identify_source(name)
        if not source:
            print("跳过无法识别来源的文件: " + name)
            continue
        print("读取: " + name + " -> " + source)
        frames.append(read_source(file, source))

    if not frames:
        print("该日期文件都无法识别来源，无需追加")
        return None

    df_new = pd.concat(frames, ignore_index=True)
    df_new["数据来源"] = "daily_raw"
    print("该日期新增: " + str(len(df_new)) + " 条")

    df_new = clean_and_fix(df_new, verbose=False)

    df_existing = load_existing_data(output_file)
    df_new = dedupe(df_new, df_existing)
    print("去重后保留: " + str(len(df_new)) + " 条")

    if df_new.empty:
        print("该日期数据已全部存在，无需追加")
        return df_existing

    df_combined = pd.concat([df_existing, df_new], ignore_index=True) if not df_existing.empty else df_new
    df_combined.to_csv(output_file, index=False, encoding='utf-8-sig')

    print("追加完成")
    print("   - 原有数据: " + str(len(df_existing)) + " 条")
    print("   - 新增: " + str(len(df_new)) + " 条")
    print("   - 合并后: " + str(len(df_combined)) + " 条")
    print("已保存至: " + output_file)
    return df_combined


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("执行出错: " + str(e))
        import traceback
        traceback.print_exc()
