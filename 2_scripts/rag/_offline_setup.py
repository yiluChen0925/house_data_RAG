# -*- coding: utf-8 -*-
"""强制 HuggingFace 离线。import 必须放在 transformers / sentence_transformers 之前。

注意：只在脚本里写 os.environ["HF_HUB_OFFLINE"]="1" 是不够的——
huggingface_hub 在 constants 模块导入时就把这个值读成了常量，chromadb -> tokenizers
这条链可能先把 constants 拉进来，之后环境变量就失效了，模型会去连 huggingface.co。
"""

import os

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def _enforce_offline():
    """constants 已经被导入过的话，重载一次把开关拉回来。"""
    import sys
    if "huggingface_hub.constants" in sys.modules:
        try:
            import importlib
            from huggingface_hub import constants
            if not constants.HF_HUB_OFFLINE:
                importlib.reload(constants)
        except Exception:
            pass


_enforce_offline()
