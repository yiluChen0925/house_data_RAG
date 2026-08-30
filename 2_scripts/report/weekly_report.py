# -*- coding: utf-8 -*-
"""
周报自动生成脚本
统计本周（最近7天）数据，对比上周同期变化，调用 DeepSeek 生成周报，复用 push_report 推送模块
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
BASE_PATH = r"D:\MyProject\house_data_RAG"
CSV_PATH = os.path.join(BASE_PATH, "1_data", "cleaned_data", "house_cleaned.csv")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


def load_data():
    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    if '爬取时间' in df.columns:
        df['爬取时间'] = df['爬取时间'].astype(str).str[:10]
        df['爬取时间'] = pd.to_datetime(df['爬取时间'], errors='coerce')
    return df


def calc_weekly_stats(df):
    """
    统计本周（最近7天）数据
    """
    today = datetime.datetime.now()
    week_start = (today - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    last_week_start = (today - datetime.timedelta(days=14)).strftime('%Y-%m-%d')
    last_week_end = (today - datetime.timedelta(days=8)).strftime('%Y-%m-%d')

    if '爬取时间' not in df.columns:
        return None

    df['爬取日期'] = df['爬取时间'].dt.strftime('%Y-%m-%d')

    df_this_week = df[df['爬取日期'] >= week_start]
    df_last_week = df[(df['爬取日期'] >= last_week_start) & (df['爬取日期'] <= last_week_end)]

    if len(df_this_week) == 0:
        return None

    this_week = {
        '天数': 7,
        '新增房源数': len(df_this_week),
        '平均总价': round(df_this_week['总价'].mean(), 2) if df_this_week['总价'].notna().any() else 0,
        '平均单价': round(df_this_week['单价'].mean(), 2) if df_this_week['单价'].notna().any() else 0,
        '平均面积': round(df_this_week['面积'].mean(), 2) if df_this_week['面积'].notna().any() else 0,
        '最热区域': df_this_week['区域'].value_counts().head(3).to_dict() if '区域' in df_this_week.columns else {},
        '最热户型': df_this_week['户型'].value_counts().head(3).to_dict() if '户型' in df_this_week.columns else {},
        '价格区间': {
            '100万以下': len(df_this_week[df_this_week['总价'] < 100]),
            '100-300万': len(df_this_week[(df_this_week['总价'] >= 100) & (df_this_week['总价'] < 300)]),
            '300-500万': len(df_this_week[(df_this_week['总价'] >= 300) & (df_this_week['总价'] < 500)]),
            '500万以上': len(df_this_week[df_this_week['总价'] >= 500])
        },
        '数据来源分布': df_this_week['数据来源'].value_counts().to_dict() if '数据来源' in df_this_week.columns else {},
    }

    last_week = {
        '新增房源数': len(df_last_week),
        '平均单价': round(df_last_week['单价'].mean(), 2) if len(df_last_week) > 0 and df_last_week[
            '单价'].notna().any() else 0,
        '最热区域': df_last_week['区域'].value_counts().head(1).to_dict() if '区域' in df_last_week.columns else {},
    }

    return {
        'this_week': this_week,
        'last_week': last_week,
        'week_range': f"{week_start} ~ {today.strftime('%Y-%m-%d')}",
        'avg_daily': round(len(df_this_week) / 7, 1),
    }


def generate_weekly_report(stats):
    if stats is None:
        return "本周暂无新增房源数据，暂无周报生成。"

    t = stats['this_week']
    l = stats['last_week']

    prompt = f"""
你是一位专业的房产市场分析师。请根据以下珠三角房产数据生成一份详细的市场周报（400-500字）。

【本周概况】
- 统计周期：{stats['week_range']}
- 本周新增房源：{t['新增房源数']} 套
- 日均新增：{stats['avg_daily']} 套/天
- 本周平均总价：{t['平均总价']} 万元
- 本周平均单价：{t['平均单价']} 元/㎡
- 本周平均面积：{t['平均面积']} ㎡

【同比上周】
- 上周新增房源：{l['新增房源数']} 套
- 上周平均单价：{l['平均单价']} 元/㎡
- 本周 vs 上周新增变化：{t['新增房源数'] - l['新增房源数']} 套
- 本周 vs 上周单价变化：{round(t['平均单价'] - l['平均单价'], 2)} 元/㎡

【区域热度（本周前3）】
{t['最热区域']}

【上周最热区域】
{l['最热区域']}

【户型分布（本周前3）】
{t['最热户型']}

【价格区间分布】
- 100万以下：{t['价格区间']['100万以下']} 套
- 100-300万：{t['价格区间']['100-300万']} 套
- 300-500万：{t['价格区间']['300-500万']} 套
- 500万以上：{t['价格区间']['500万以上']} 套

【数据来源】
{t['数据来源分布']}

请生成一份结构清晰的周报，包含以下部分：
1. 【本周概况】整体市场情况总结
2. 【区域分析】哪些区域活跃，哪些降温
3. 【价格趋势】价格变化分析
4. 【户型观察】什么户型受欢迎
5. 【下周展望】对未来一周的预判

要求：数据驱动、分析客观、语言专业、有洞察力。
"""

    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1200
    }

    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}

    try:
        response = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "生成周报失败: " + str(e)


def main():
    print("开始生成周报 " + datetime.datetime.now().strftime('%Y-%m-%d') + "...")

    df = load_data()
    print("   - 全量数据: " + str(len(df)) + " 条")

    stats = calc_weekly_stats(df)
    if stats is None:
        print("本周没有新数据，不生成周报")
        return

    print("   - 本周新增: " + str(stats['this_week']['新增房源数']) + " 条")
    print("   - 日均新增: " + str(stats['avg_daily']) + " 套/天")

    print("正在生成周报...")
    content = generate_weekly_report(stats)

    push_report(content, "周报")


if __name__ == "__main__":
    main()