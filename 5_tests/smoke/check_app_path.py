# -*- coding: utf-8 -*-
"""走一遍 app.py 的检索路径：结构化过滤 + 混合检索，不调 DeepSeek。

和 hybrid_retriever.py 自带的自测不同，这里会把 parse_query 抽出的条件传进
search()，也就是用户提问时真实的调用方式。

    python 5_tests/smoke/check_app_path.py
"""

import re
import sys

sys.path.insert(0, __file__.rsplit("5_tests", 1)[0] + "5_tests")
import paths  # noqa: E402

paths.offline()
paths.add_paths()

import pandas as pd  # noqa: E402

QUESTIONS = ["深圳南山区500万以下三房", "广州天河区300万以下的房子", "佛山南海区地铁房"]


def load_parse_query():
    """从 app.py 里取出 parse_query，避免执行整个 Streamlit 页面。"""
    src = open(paths.SCRIPTS + '/app.py', encoding='utf-8').read()
    start = src.index('def parse_query(')
    end = src.index('def retrieve_houses(')
    namespace = {'re': re}
    exec(src[start:end], namespace)
    return namespace['parse_query']


def txt(r, key):
    v = r.get(key)
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ''
    s = str(v).strip()
    return '' if s.lower() == 'nan' else s


def main():
    from hybrid_retriever import HybridRetriever

    parse_query = load_parse_query()
    r = HybridRetriever()
    print('CSV %d 行，向量库 %d 条' % (len(r.df), r.collection.count()))

    for q in QUESTIONS:
        f = parse_query(q)
        res = r.search(query=q, top_k=3, city=f['city'], district=f['district'],
                       max_price=f['max_price'], min_price=f['min_price'],
                       layout=f['layout'], min_area=f['min_area'], max_area=f['max_area'])
        print()
        print('%s  ->  %s' % (q, {k: v for k, v in f.items() if v is not None}))
        for i, x in enumerate(res, 1):
            print('  %d. %s（%s%s）%s %s㎡ 总价%s万 [%s]'
                  % (i, txt(x, '小区名称'), txt(x, '城市'), txt(x, '区域'),
                     txt(x, '户型') or '-', txt(x, '面积'), txt(x, '总价'), txt(x, '数据来源')))


if __name__ == "__main__":
    main()
