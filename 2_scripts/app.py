# -*- coding: utf-8 -*-
"""
珠三角房产智能问答系统 - 带多轮对话记忆 + 混合检索 + 结构化过滤
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag"))
import _offline_setup  # noqa: F401  必须早于 hybrid_retriever/sentence_transformers

import streamlit as st
import chromadb
import requests
import json
import re
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "all-MiniLM-L6-v2"
BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CHROMA_PATH = os.path.join(BASE_PATH, "1_data", "chroma_db")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

from hybrid_retriever import HybridRetriever


@st.cache_resource
def load_retriever():
    return HybridRetriever()


retriever = load_retriever()


def parse_query(question):
    """
    从自然语言问题中提取结构化过滤条件
    返回 dict: {city, district, max_price, min_price, layout, min_area, max_area}
    """
    result = {
        'city': None,
        'district': None,
        'max_price': None,
        'min_price': None,
        'layout': None,
        'min_area': None,
        'max_area': None
    }

    cities = ['深圳', '广州', '东莞', '佛山', '惠州']
    for city in cities:
        if city in question:
            result['city'] = city
            break

    districts = ['南山', '福田', '罗湖', '宝安', '龙岗', '龙华', '光明', '坪山', '盐田',
                 '天河', '越秀', '海珠', '荔湾', '白云', '黄埔', '番禺', '花都', '南沙',
                 '禅城', '南海', '顺德', '三水', '高明',
                 '莞城', '南城', '万江', '虎门', '长安',
                 '惠城', '惠阳', '仲恺', '大亚湾']
    for d in districts:
        if d in question:
            result['district'] = d + '区'
            break

    price_patterns = [
        (r'(\d+)\s*[-~到]\s*(\d+)\s*万', lambda m: (float(m.group(1)), float(m.group(2)))),
        (r'(\d+)\s*万\s*以下', lambda m: (0, float(m.group(1)))),
        (r'(\d+)\s*万\s*以上', lambda m: (float(m.group(1)), float('inf'))),
        (r'总价\s*(\d+)\s*万', lambda m: (float(m.group(1)), float(m.group(1)))),
        (r'(\d+)\s*万', lambda m: (float(m.group(1)), float(m.group(1))))
    ]
    for pattern, handler in price_patterns:
        match = re.search(pattern, question)
        if match:
            min_p, max_p = handler(match)
            if min_p is not None:
                result['min_price'] = min_p
            if max_p is not None and max_p != float('inf'):
                result['max_price'] = max_p
            break

    layout_keywords = ['三房', '两房', '一房', '四房', '五房', '一室', '两室', '三室', '四室', '五室']
    for kw in layout_keywords:
        if kw in question:
            result['layout'] = kw
            break

    area_match = re.search(r'(\d+)\s*[-~到]\s*(\d+)\s*平', question)
    if area_match:
        result['min_area'] = float(area_match.group(1))
        result['max_area'] = float(area_match.group(2))
    else:
        area_match = re.search(r'(\d+)\s*平\s*以上', question)
        if area_match:
            result['min_area'] = float(area_match.group(1))
        else:
            area_match = re.search(r'(\d+)\s*平', question)
            if area_match:
                result['min_area'] = float(area_match.group(1))
                result['max_area'] = float(area_match.group(1))

    return result


def retrieve_houses(question, n_results=5):
    filters = parse_query(question)

    results = retriever.search(
        query=question,
        top_k=n_results,
        city=filters['city'],
        district=filters['district'],
        max_price=filters['max_price'],
        min_price=filters['min_price'],
        layout=filters['layout'],
        min_area=filters['min_area'],
        max_area=filters['max_area']
    )

    if results:
        context_lines = []
        for i, r in enumerate(results, 1):
            # 空字段读回来是 NaN，直接拼进 prompt 会变成字面的 "nan"
            def txt(key):
                v = r.get(key)
                if v is None:
                    return ''
                if isinstance(v, float) and pd.isna(v):
                    return ''
                s = str(v).strip()
                return '' if s.lower() == 'nan' else s
            line = (
                f"{i}. {txt('小区名称')}（{txt('城市')}{txt('区域')}）"
                f"{txt('户型')} {txt('面积')}㎡，"
                f"总价{txt('总价')}万元，单价{txt('单价')}元/㎡"
            )
            context_lines.append(line)
        return "\n".join(context_lines), results, filters
    return None, None, filters


def call_deepseek_with_history(messages, context):
    system_prompt = f"""你是一位专业的房产顾问，根据提供的房源信息给用户推荐合适的房子。

要求：
1. 推荐理由要具体，结合用户的需求
2. 如果房源信息不足，如实告知用户，不要编造
3. 回答要简洁、有条理，分点说明
4. 结合对话历史，理解用户的上下文（例如"那个小区"指代什么）

当前检索到的房源信息：
{context}
"""

    full_messages = [
        {"role": "system", "content": system_prompt}
    ] + messages

    payload = {
        "model": "deepseek-chat",
        "messages": full_messages,
        "temperature": 0.7,
        "max_tokens": 800
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }

    try:
        response = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return "调用 DeepSeek 出错: " + str(e)


st.set_page_config(page_title="珠三角房产智能问答", layout="wide")
st.title("珠三角房产智能问答系统（带记忆 + 混合检索 + 结构化过滤）")
st.markdown("支持多轮对话 | 混合检索（BM25 + 向量 + RRF融合）| 结构化过滤（城市/区域/价格/户型）")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

question = st.chat_input("请输入你的问题（如：深圳南山区500万以下三房）")

if question:
    with st.chat_message("user"):
        st.markdown(question)
    st.session_state.messages.append({"role": "user", "content": question})

    with st.spinner("正在检索房源..."):
        context, metadatas, filters = retrieve_houses(question)

    filter_info = []
    if filters['city']:
        filter_info.append("城市：" + filters['city'])
    if filters['district']:
        filter_info.append("区域：" + filters['district'])
    if filters['max_price'] is not None:
        filter_info.append("总价 <= " + str(filters['max_price']) + "万")
    if filters['min_price'] is not None and filters['min_price'] > 0:
        filter_info.append("总价 >= " + str(filters['min_price']) + "万")
    if filters['layout']:
        filter_info.append("户型：" + filters['layout'])

    with st.spinner("AI 正在分析推荐..."):
        if context:
            answer = call_deepseek_with_history(st.session_state.messages, context)
        else:
            answer = "没有找到匹配的房源，请换一种描述试试。"

    with st.chat_message("assistant"):
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})

    if context and metadatas:
        expander_title = "检索到的房源"
        if filter_info:
            expander_title = expander_title + "（" + "，".join(filter_info) + "）"
        with st.expander(expander_title):
            for meta in metadatas:
                disp = {k: ('' if (v is None or (isinstance(v, float) and pd.isna(v))
                                    or str(v).strip().lower() == 'nan') else str(v))
                        for k, v in meta.items()}
                st.write("**" + disp.get('小区名称', '') + "**（" + disp.get('城市', '') + disp.get('区域', '') + "）")
                st.write("   " + disp.get('户型', '') + " " + disp.get('面积', '0') + "㎡ | 总价" + disp.get('总价', '0') + "万元")

with st.sidebar:
    st.markdown("### 控制面板")
    if st.button("清空对话历史", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    st.markdown("**对话轮数：** " + str(len(st.session_state.messages) // 2))
    st.divider()
    st.markdown("### 试试这样问")
    st.markdown("""
    1. 深圳南山区三房推荐
    2. 广州天河区500万以下
    3. 那个小区物业费多少？
    """)