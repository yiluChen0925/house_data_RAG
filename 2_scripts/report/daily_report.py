# -*- coding: utf-8 -*-
"""
日报自动生成脚本
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

from push_report import push_report

# ==================== 配置 ====================
BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CSV_PATH = os.path.join(BASE_PATH, "1_data", "cleaned_data", "house_cleaned.csv")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


def load_data():
    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    if '爬取时间' in df.columns:
        df['爬取时间'] = df['爬取时间'].astype(str).str[:10]
        df['爬取时间'] = pd.to_datetime(df['爬取时间'], errors='coerce')
    return df


def calc_today_stats(df, as_of=None):
    today_str = (as_of or datetime.datetime.now()).strftime('%Y-%m-%d')
    if '爬取时间' in df.columns:
        df_today = df[df['爬取时间'].dt.strftime('%Y-%m-%d') == today_str]
    else:
        return None

    if len(df_today) == 0:
        return None

    return {
        '日期': today_str,
        '新增房源数': len(df_today),
        '平均总价': round(df_today['总价'].mean(), 2) if df_today['总价'].notna().any() else 0,
        '平均单价': round(df_today['单价'].mean(), 2) if df_today['单价'].notna().any() else 0,
        '平均面积': round(df_today['面积'].mean(), 2) if df_today['面积'].notna().any() else 0,
        '总价中位数': round(df_today['总价'].median(), 2) if df_today['总价'].notna().any() else 0,
        '最热区域': df_today['区域'].value_counts().head(3).to_dict() if '区域' in df_today.columns else {},
        '最热户型': df_today['户型'].value_counts().head(3).to_dict() if '户型' in df_today.columns else {},
        '价格区间': {
            '100万以下': len(df_today[df_today['总价'] < 100]),
            '100-300万': len(df_today[(df_today['总价'] >= 100) & (df_today['总价'] < 300)]),
            '300-500万': len(df_today[(df_today['总价'] >= 300) & (df_today['总价'] < 500)]),
            '500万以上': len(df_today[df_today['总价'] >= 500])
        },
        '数据来源分布': df_today['数据来源'].value_counts().to_dict() if '数据来源' in df_today.columns else {},
    }


def calc_historical_compare(df, as_of=None):
    now = as_of or datetime.datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    if '爬取时间' not in df.columns:
        return None

    df['爬取日期'] = df['爬取时间'].dt.strftime('%Y-%m-%d')
    df_today = df[df['爬取日期'] == today_str]
    df_yesterday = df[df['爬取日期'] == (now - datetime.timedelta(days=1)).strftime('%Y-%m-%d')]
    df_last_week = df[df['爬取日期'] >= (now - datetime.timedelta(days=7)).strftime('%Y-%m-%d')]

    return {
        '今日均价': round(df_today['单价'].mean(), 2) if len(df_today) > 0 and df_today['单价'].notna().any() else 0,
        '昨日均价': round(df_yesterday['单价'].mean(), 2) if len(df_yesterday) > 0 and df_yesterday[
            '单价'].notna().any() else 0,
        '近7日均价': round(df_last_week['单价'].mean(), 2) if len(df_last_week) > 0 and df_last_week[
            '单价'].notna().any() else 0,
        '历史均价': round(df['单价'].mean(), 2) if df['单价'].notna().any() else 0,
        '今日新增数': len(df_today),
        '昨日新增数': len(df_yesterday),
        '近7日平均新增': round(len(df_last_week) / 7, 0) if len(df_last_week) > 0 else 0,
    }


def generate_report(today_stats, history_stats):
    if today_stats is None:
        return "今日暂无新增房源数据，暂无日报生成。"

    prompt = f"""
你是一位专业的房产市场分析师。请根据以下珠三角房产数据生成一份简洁的市场日报（300-400字）。

【今日新增数据】
- 日期：{today_stats['日期']}
- 新增房源：{today_stats['新增房源数']} 套
- 平均总价：{today_stats['平均总价']} 万元
- 平均单价：{today_stats['平均单价']} 元/㎡
- 平均面积：{today_stats['平均面积']} ㎡
- 总价中位数：{today_stats['总价中位数']} 万元

【区域热度（新增房源最多）】
{today_stats['最热区域']}

【户型分布（新增最多）】
{today_stats['最热户型']}

【价格区间分布】
- 100万以下：{today_stats['价格区间']['100万以下']} 套
- 100-300万：{today_stats['价格区间']['100-300万']} 套
- 300-500万：{today_stats['价格区间']['300-500万']} 套
- 500万以上：{today_stats['价格区间']['500万以上']} 套

【数据来源】
{today_stats['数据来源分布']}

【历史对比】
- 今日均价：{history_stats['今日均价']} 元/㎡
- 昨日均价：{history_stats['昨日均价']} 元/㎡（变化：{round(history_stats['今日均价'] - history_stats['昨日均价'], 2)} 元/㎡）
- 近7日均价：{history_stats['近7日均价']} 元/㎡
- 历史均价：{history_stats['历史均价']} 元/㎡
- 今日新增：{history_stats['今日新增数']} 套
- 昨日新增：{history_stats['昨日新增数']} 套
- 近7日平均新增：{history_stats['近7日平均新增']} 套/天

请生成一份结构清晰的日报，包含以下部分：
1. 【今日概况】一句话总结今日市场
2. 【区域亮点】哪个区域最活跃
3. 【价格分析】价格趋势和特点
4. 【一句话点评】对未来市场的简评

要求：语言简洁、数据准确、分析客观，不要编造数据。
"""

    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 800
    }

    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}

    try:
        response = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "生成报告失败: " + str(e)


def _parse_as_of(text):
    """把 YYYY-MM-DD 或 YYYYMMDD 解析成 datetime；不传就用当前时间。"""
    if not text:
        return None
    text = text.strip()
    for fmt in ('%Y-%m-%d', '%Y%m%d'):
        try:
            return datetime.datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError("无法解析日期: " + text + "（应为 YYYY-MM-DD 或 YYYYMMDD）")


def save_report(content, as_of):
    """把报表写到 1_data/reports/日报_YYYYMMDD.md（原来只推不存，现在补上落盘）。"""
    reports_dir = os.path.join(BASE_PATH, "1_data", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    path = os.path.join(reports_dir, "日报_" + as_of.strftime('%Y%m%d') + ".md")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return path


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="生成房产市场日报")
    parser.add_argument("--as-of", dest="as_of",
                        help="把'今天'当成指定日期来统计（YYYY-MM-DD 或 YYYYMMDD），用于回溯测试")
    parser.add_argument("--dry-run", action="store_true", help="只生成并保存文件，不推送钉钉/邮件")
    args = parser.parse_args(argv)

    as_of_dt = _parse_as_of(args.as_of)
    now = as_of_dt or datetime.datetime.now()
    print("开始生成日报 " + now.strftime('%Y-%m-%d') + ("（--as-of 指定）" if as_of_dt else "") + "...")

    df = load_data()
    print("   - 全量数据: " + str(len(df)) + " 条")

    today_stats = calc_today_stats(df, as_of=as_of_dt)
    if today_stats is None:
        print("该日期没有新数据，不生成日报。提示：可用 --as-of 指定有数据的日期。")
        return 0

    print("   - 当日新增: " + str(today_stats['新增房源数']) + " 条")

    history_stats = calc_historical_compare(df, as_of=as_of_dt)

    print("正在生成报告（调用 DeepSeek）...")
    content = generate_report(today_stats, history_stats)

    path = save_report(content, now)
    print("   - 已保存: " + path + "（" + str(len(content)) + " 字符）")

    if args.dry_run:
        print("   - --dry-run：跳过推送")
        return 0

    push_report(content, "日报")
    return 0


if __name__ == "__main__":
    sys.exit(main())