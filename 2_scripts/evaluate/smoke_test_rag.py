# -*- coding: utf-8 -*-
"""
端到端冒烟测试：真实调用 DeepSeek API

验证"问一个问题 -> 真拿到推荐答案"这最后一环。
会产生少量 API 费用（3 个问题，每次约 800 token 输出）。

用法：
    python 2_scripts/evaluate/smoke_test_rag.py
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(APP_DIR, "rag"))
sys.path.insert(0, APP_DIR)

import _offline_setup  # noqa: F401  必须早于 sentence_transformers

import re  # noqa: E402

import pandas as pd  # noqa: E402
import requests  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from hybrid_retriever import HybridRetriever  # noqa: E402

BASE_PATH = os.path.abspath(os.path.join(HERE, "..", ".."))
load_dotenv(os.path.join(BASE_PATH, ".env"))

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

QUESTIONS = [
    "深圳南山区500万以下三房",
    "广州天河区300万以下的房子",
    "佛山南海区地铁房",
]

# 与 app.py 的 parse_query 等价的最小实现（只取冒烟测试用得到的条件）
def parse_query(question):
    result = {"city": None, "district": None, "max_price": None, "min_price": None, "layout": None}
    for city in ['深圳', '广州', '东莞', '佛山', '惠州']:
        if city in question:
            result["city"] = city
            break
    for d in ['南山', '福田', '罗湖', '宝安', '龙岗', '龙华', '光明', '坪山', '盐田',
              '天河', '越秀', '海珠', '荔湾', '白云', '黄埔', '番禺', '花都', '南沙',
              '禅城', '南海', '顺德', '三水', '高明', '莞城', '南城', '万江', '虎门', '长安',
              '惠城', '惠阳', '仲恺', '大亚湾']:
        if d in question:
            result["district"] = d + '区'
            break
    m = re.search(r'(\d+)\s*万\s*以下', question)
    if m:
        result["min_price"], result["max_price"] = 0.0, float(m.group(1))
    for kw in ['三房', '两房', '一房', '四房', '五房']:
        if kw in question:
            result["layout"] = kw
            break
    return result


def txt(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    s = str(value).strip()
    return '' if s.lower() == 'nan' else s


def build_context(results):
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(
            "{}. {}（{}{}）{} {}㎡，总价{}万元，单价{}元/㎡".format(
                i, txt(r.get('小区名称')), txt(r.get('城市')), txt(r.get('区域')),
                txt(r.get('户型')), txt(r.get('面积')), txt(r.get('总价')), txt(r.get('单价')))
        )
    return "\n".join(lines)


def call_deepseek(question, context):
    system_prompt = (
        "你是一位专业的房产顾问，根据提供的房源信息给用户推荐合适的房子。\n\n"
        "要求：\n1. 推荐理由要具体，结合用户的需求\n"
        "2. 如果房源信息不足，如实告知用户，不要编造\n"
        "3. 回答要简洁、有条理，分点说明\n\n"
        "当前检索到的房源信息：\n" + context
    )
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": question}],
        "temperature": 0.7,
        "max_tokens": 800,
    }
    headers = {"Authorization": "Bearer " + DEEPSEEK_API_KEY}
    t0 = time.time()
    resp = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"], round(time.time() - t0, 1)


def main():
    if not DEEPSEEK_API_KEY:
        print("!! .env 里没有 DEEPSEEK_API_KEY，无法调用 API")
        return 1

    print("加载检索器...")
    retriever = HybridRetriever()
    print("检索器就绪，CSV 行数 = " + str(len(retriever.df)))
    print()

    ok = 0
    for q in QUESTIONS:
        f = parse_query(q)
        print("=" * 66)
        print("问题: " + q)
        print("抽取条件: " + str({k: v for k, v in f.items() if v is not None}))
        results = retriever.search(
            query=q, top_k=3, city=f["city"], district=f["district"],
            max_price=f["max_price"], min_price=f["min_price"], layout=f["layout"],
        )
        if not results:
            print("  !! 检索为空，跳过 API 调用")
            continue
        context = build_context(results)
        print("检索到 " + str(len(results)) + " 条:")
        for line in context.split("\n"):
            print("  " + line)
        try:
            answer, secs = call_deepseek(q, context)
            print("DeepSeek 回答（耗时 " + str(secs) + "s）:")
            for line in answer.strip().split("\n")[:12]:
                print("  " + line)
            ok += 1
        except Exception as e:
            print("  !! API 调用失败: " + type(e).__name__ + " " + str(e)[:200])
        print()

    print("=" * 66)
    print("冒烟结果: " + str(ok) + "/" + str(len(QUESTIONS)) + " 个问题成功拿到回答")
    return 0 if ok == len(QUESTIONS) else 1


if __name__ == "__main__":
    sys.exit(main())
