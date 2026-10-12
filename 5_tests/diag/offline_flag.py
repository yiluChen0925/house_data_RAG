# -*- coding: utf-8 -*-
"""huggingface_hub 离线开关到底怎么才生效。

背景：只写 os.environ["HF_HUB_OFFLINE"]="1" 可能没用——huggingface_hub 在
constants 模块导入时就把值读成常量了。本脚本用子进程把几种顺序都试一遍。

    python 5_tests/diag/offline_flag.py
"""

import os
import subprocess
import sys

CONST = "from huggingface_hub import constants; print(constants.HF_HUB_OFFLINE)"


def run(code, env=None):
    e = dict(os.environ)
    e.pop('HF_HUB_OFFLINE', None)
    e.pop('TRANSFORMERS_OFFLINE', None)
    if env:
        e.update(env)
    r = subprocess.run([sys.executable, '-X', 'utf8', '-c', code],
                       capture_output=True, text=True, env=e)
    return (r.stdout.strip() or r.stderr.strip()[:120])


CASES = [
    ("进程内先设 os.environ，再首次导入 constants",
     "import os; os.environ['HF_HUB_OFFLINE']='1'; " + CONST, None),
    ("进程启动前由外部设环境变量", CONST, {'HF_HUB_OFFLINE': '1'}),
    ("先导入 constants，再设 os.environ",
     "from huggingface_hub import constants; import os; "
     "os.environ['HF_HUB_OFFLINE']='1'; print(constants.HF_HUB_OFFLINE)", None),
    ("冻结后 reload(constants) 能否救回",
     "from huggingface_hub import constants; import os, importlib; "
     "os.environ['HF_HUB_OFFLINE']='1'; importlib.reload(constants); "
     "print(constants.HF_HUB_OFFLINE)", None),
    ("导入 transformers 是否会连带导入 constants",
     "import sys; import transformers; print('huggingface_hub.constants' in sys.modules)", None),
]


def main():
    for label, code, env in CASES:
        print("%-44s -> %s" % (label, run(code, env)))
    print()
    print("外部设置时接受的取值：")
    for v in ['1', 'true', 'TRUE', 'yes', 'on', '0']:
        print("  HF_HUB_OFFLINE=%-5s -> %s" % (v, run(CONST, env={'HF_HUB_OFFLINE': v})))


if __name__ == "__main__":
    main()
