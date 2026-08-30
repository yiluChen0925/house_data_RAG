# -*- coding: utf-8 -*-
"""
数据清洗工具函数
用于房产数据的空值处理、数值提取、日期格式化等
"""

import re
import datetime
import logging
from typing import Optional, Union

logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def is_empty(val: Union[str, int, float, None]) -> bool:
    """判断值是否为空，兼容常见的空值表示形式"""
    empty_keywords = ("", "无", "暂无", "暂无资料", "NaN", "nan", "None", "null", "未知", "价格待定", "待定")
    if val is None:
        return True
    if isinstance(val, (int, float)):
        return False
    val_str = str(val).strip().lower()
    return val_str in empty_keywords


def clean_numeric(
        val: Union[str, int, float, None],
        default: float = 0.0,
        min_limit: Optional[float] = None,
        max_limit: Optional[float] = None
) -> float:
    """
    从字符串中提取第一个数字并转为浮点数
    处理重复拼接的情况，如 3.583.58 → 3.58
    """
    if is_empty(val):
        return default

    if isinstance(val, (int, float)):
        num = float(val)
    else:
        num_str_list = re.findall(r'\d+\.?\d*', str(val))
        if not num_str_list:
            return default
        try:
            num = float(num_str_list[0])
        except:
            return default

    if min_limit is not None:
        num = max(num, min_limit)
    if max_limit is not None:
        num = min(num, max_limit)

    return round(num, 2)


def clean_datetime(
        dt_str: Union[str, int, float, None],
        default: Optional[datetime.datetime] = None
) -> datetime.datetime:
    """
    将各种格式的日期字符串转为 datetime 对象
    支持标准时间、中文日期、带后缀的日期等
    """
    default_dt = default or datetime.datetime.now()

    if is_empty(dt_str):
        return default_dt

    s = str(dt_str).strip()

    # 先尝试解析标准时间格式
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass

    # 去掉一些常见的干扰后缀
    s = re.sub(r'\[.*?\]', '', s)
    s = re.sub(r'(已开盘|开盘|交房|加推|预计|待定|入伙|交楼|咨询售楼处).*', '', s)
    s = re.sub(r'[^\d年月日\s:-]', '', s).strip()

    # 统一分隔符
    s = s.replace('年', '-').replace('月', '-').replace('日', '').replace('.', '-')
    s = re.sub(r'-+', '-', s).strip('-')

    dt_formats = [
        "%Y-%m-%d", "%Y-%m", "%Y",
        "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"
    ]

    for fmt in dt_formats:
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue

    logger.warning(f"日期清洗失败: {dt_str}")
    return default_dt


def clean_plot_ratio(val: Union[str, int, float, None]) -> float:
    """容积率清洗，限制在 0.1 ~ 10.0 范围内"""
    return clean_numeric(val, default=0.0, min_limit=0.1, max_limit=10.0)


def clean_integer(val: Union[str, int, float, None]) -> int:
    """提取第一个数字并转为整数"""
    num = clean_numeric(val, default=0)
    try:
        return int(num)
    except:
        return 0


def clean_percentage(val: Union[str, int, float, None]) -> float:
    """百分比清洗，限制在 0 ~ 100 范围内"""
    return clean_numeric(val, default=0.0, max_limit=100.0)


def clean_area(val: Union[str, int, float, None]) -> float:
    """面积清洗，上限 1 亿平方米"""
    return clean_numeric(val, default=0.0, max_limit=100000000.0)


def clean_price(val: Union[str, int, float, None]) -> float:
    """
    价格清洗，单位统一为万元
    如果原始数据带"万"，直接取数字，否则按万元处理
    """
    if val is None:
        return 0.0
    s = str(val).strip().replace(" ", "")

    num_list = re.findall(r"\d+\.?\d*", s)
    if not num_list:
        return 0.0
    price = float(num_list[0])

    # 统一按万元处理，限制在 0 ~ 9999 万
    final_price = price
    final_price = max(0.0, min(final_price, 9999.0))

    return round(final_price, 2)


def clean_property_fee(val: Union[str, int, float, None]) -> float:
    """物业费清洗"""
    return clean_numeric(val, default=0.0)


def clean_boolean(val: Union[str, int, bool, None]) -> bool:
    """将常见的'是/否'、'有/无'转为布尔值"""
    if is_empty(val):
        return False
    s = str(val).strip().lower()
    return s in ('是', '有', 'true', '1', '对')


def clean_decimal(val: Union[str, int, float, None]) -> float:
    """通用小数清洗"""
    return clean_numeric(val)
