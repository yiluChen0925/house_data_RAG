# -*- coding: utf-8 -*-
"""
轻量级 RAG 评估脚本
用 DeepSeek 对检索结果进行忠实度和相关性打分
"""

import os
import sys
import requests
import json
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# ==================== 配置 ====================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

from rag.hybrid_retriever import HybridRetriever


class SimpleEvaluator:
    def __init__(self):
        self.retriever = HybridRetriever()

    def query_rag(self, question):
        """执行 RAG 检索，返回答案和上下文"""
        results = self.retriever.search(question, top_k=3)
        if not results:
            return "未找到相关房源", ""
        answer_lines = []
        contexts = []
        for r in results:
            answer_lines.append(
                f"{r['小区名称']}（{r['城市']}{r['区域']}）{r['户型']} {r['面积']}㎡，总价{r['总价']}万元"
            )
            contexts.append(f"{r['城市']} {r['区域']} {r['户型']} {r['小区名称']}")
        return "\n".join(answer_lines), " ".join(contexts)

    def evaluate_faithfulness(self, question, answer, context):
        """评估忠实度：答案是否基于上下文，有没有编造"""
        prompt = f"""你是一个评估专家。请判断以下回答是否基于给定的上下文，有没有编造事实。

上下文：{context}
问题：{question}
回答：{answer}

请只输出一个数字（0-100），代表忠实度分数。100分表示完全基于上下文，0分表示完全编造。
分数：
"""
        return self._call_llm(prompt)

    def evaluate_relevancy(self, question, answer):
        """评估答案相关性：回答是否切中问题"""
        prompt = f"""你是一个评估专家。请判断以下回答是否切中了用户的问题。

问题：{question}
回答：{answer}

请只输出一个数字（0-100），代表相关性分数。100分表示完全相关，0分表示完全不相关。
分数：
"""
        return self._call_llm(prompt)

    def _call_llm(self, prompt):
        try:
            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 10
            }
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            response = requests.post(DEEPSEEK_URL, data=data, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
            text = result["choices"][0]["message"]["content"].strip()
            import re
            nums = re.findall(r'\d+', text)
            if nums:
                return min(float(nums[0]) / 100, 1.0)
            return 0.5
        except Exception as e:
            print("调用失败: " + str(e))
            return 0.5

    def run_evaluation(self, questions):
        """运行完整评估"""
        print("开始评估 " + str(len(questions)) + " 个问题...")
        scores_f = []
        scores_r = []

        for i, q in enumerate(questions):
            print("进度: " + str(i+1) + "/" + str(len(questions)))
            answer, context = self.query_rag(q)
            f_score = self.evaluate_faithfulness(q, answer, context)
            r_score = self.evaluate_relevancy(q, answer)
            scores_f.append(f_score)
            scores_r.append(r_score)
            print("  忠实度: " + str(f_score) + ", 相关性: " + str(r_score))

        print("\n" + "=" * 50)
        print("评估结果")
        print("=" * 50)
        print("平均忠实度: " + str(sum(scores_f)/len(scores_f)))
        print("平均答案相关性: " + str(sum(scores_r)/len(scores_r)))
        return {
            "faithfulness": sum(scores_f)/len(scores_f),
            "relevancy": sum(scores_r)/len(scores_r)
        }


if __name__ == "__main__":
    evaluator = SimpleEvaluator()

    test_questions = [
        "深圳南山区三房推荐",
        "广州越秀区500万以下的房源",
        "佛山南海区地铁附近的房子",
        "深圳福田区小区哪个绿化好",
        "广州天河区单价5万以下的房源",
    ]

    evaluator.run_evaluation(test_questions)