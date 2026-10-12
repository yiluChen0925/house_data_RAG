# -*- coding: utf-8 -*-
"""
每日增量：解析 HTML -> daily_raw -> 追加进 house_cleaned.csv -> 重建向量库

用法：
    python 2_scripts/crawler/daily_ingest.py --date 20260818
    python 2_scripts/crawler/daily_ingest.py --date 20260818 --no-reindex

追加之后向量库不会自动更新，所以默认重建一次（全量，分钟级）。
"""

import argparse
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(BASE_PATH, "2_scripts", "etl"))
sys.path.insert(0, os.path.join(BASE_PATH, "2_scripts", "rag"))

import _offline_setup  # noqa: F401,E402

RAW_HTML = os.path.join(BASE_PATH, "1_data", "raw_html")
DAILY_RAW = os.path.join(BASE_PATH, "1_data", "daily_raw")


def available_dates():
    """列出 raw_html 下每个源、每个日期目录里有多少 HTML。"""
    result = {}
    if not os.path.isdir(RAW_HTML):
        return result
    for source in sorted(os.listdir(RAW_HTML)):
        source_dir = os.path.join(RAW_HTML, source)
        if not os.path.isdir(source_dir):
            continue
        for date_name in sorted(os.listdir(source_dir)):
            date_dir = os.path.join(source_dir, date_name)
            if os.path.isdir(date_dir):
                count = len([f for f in os.listdir(date_dir) if f.lower().endswith('.html')])
                result.setdefault(source, []).append((date_name, count))
    return result


def parse_html(date_str):
    import html_parser
    import html_parser_ftx

    for module, label in ((html_parser_ftx, "房天下二手房"), (html_parser, "58同城二手房")):
        print("解析 " + label + " ...")
        try:
            df = module.parse_and_save(date_str, base_path=BASE_PATH, verbose=False)
        except Exception as e:
            print("  失败: " + type(e).__name__ + " " + str(e)[:200])
            continue
        print("  " + ("无数据" if df is None else str(len(df)) + " 条"))

    return [os.path.join(DAILY_RAW, f) for f in sorted(os.listdir(DAILY_RAW))
            if f.endswith("_" + date_str + ".csv")] if os.path.isdir(DAILY_RAW) else []


def main(argv=None):
    parser = argparse.ArgumentParser(description="每日增量：解析 HTML -> 追加 -> 重建向量库")
    parser.add_argument("--date", help="处理日期 YYYYMMDD，默认今天")
    parser.add_argument("--no-reindex", action="store_true", help="追加后不重建向量库")
    args = parser.parse_args(argv)

    date_str = args.date or datetime.datetime.now().strftime('%Y%m%d')
    print("日期 " + date_str + "，项目根 " + BASE_PATH)

    files = parse_html(date_str)
    if not files:
        print("没有产出 daily_raw 文件。raw_html 里现有：")
        for source, dates in available_dates().items():
            for date_name, count in dates:
                print("  " + source + "/" + date_name + " : " + str(count) + " 个")
        return 0

    import merge_and_clean_today as today
    today.main(base_path=BASE_PATH, date_str=date_str)

    if args.no_reindex:
        print("跳过向量库重建；此时 house_cleaned.csv 比向量库新，检索会落后。")
    else:
        import runpy
        script = os.path.join(BASE_PATH, "2_scripts", "load_to_chromadb.py")
        print("重建向量库 ...")
        sys.argv = [script]
        runpy.run_path(script, run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
