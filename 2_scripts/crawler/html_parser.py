# -*- coding: utf-8 -*-
"""
本地 HTML 房源提取脚本（wuba 版本）
从保存的 58 同城房源页面里提取数据，字段和之前爬虫保持一致
"""

import os
import re
import json
import datetime
from bs4 import BeautifulSoup
import pandas as pd

# ==================== 城市映射 ====================
CITY_MAP = {
    "sz": {"id": "4", "name": "深圳"},
    "dg": {"id": "413", "name": "东莞"},
    "gz": {"id": "3", "name": "广州"},
    "fs": {"id": "222", "name": "佛山"},
    "huizhou": {"id": "722", "name": "惠州"},
}
CITY_NAME_TO_ABBR = {v["name"]: k for k, v in CITY_MAP.items()}

# ==================== 工具函数 ====================
def clean_str(s):
    """去掉字符串里的换行、空格、制表符"""
    if not s:
        return ""
    return str(s).strip().replace("\n", "").replace("\r", "").replace("\t", " ").replace("  ", " ")


def extract_num(s):
    """从字符串里提取第一个数字"""
    if not s:
        return ""
    match = re.search(r'(\d+\.?\d*)', str(s))
    return match.group(1) if match else ""


# ==================== 从页面提取城市 ====================
def parse_city_from_page(soup):
    """尝试从面包屑或标题里找到城市名称"""
    try:
        breadcrumb = soup.find('div', class_=re.compile('breadcrumb'))
        if breadcrumb:
            links = breadcrumb.find_all('a')
            for link in links:
                city_name = clean_str(link.text)
                if city_name in CITY_NAME_TO_ABBR:
                    return city_name
    except:
        pass
    try:
        title = soup.find('title')
        if title:
            for city_name in CITY_NAME_TO_ABBR.keys():
                if city_name in title.text:
                    return city_name
    except:
        pass
    return None


# ==================== 提取核验编码 ====================
def parse_verification_code(soup):
    """房源核验编码，如果有的话"""
    try:
        label = soup.find('span', string=re.compile('房源核验编码'))
        if label:
            code = label.find_next_sibling('span', class_='houseInfo-main-item-name')
            if code:
                return clean_str(code.text)
            parent = label.find_parent('td')
            if parent:
                code = parent.find('span', class_='houseInfo-main-item-name')
                if code:
                    return clean_str(code.text)
    except:
        pass
    return ""


# ==================== 解析页面上的各种字段 ====================
def parse_basic_info(soup):
    """把页面上能捞的字段都捞一遍"""
    result = {
        'build_year': '',
        'has_elevator': '',
        'property_right': '',
        'listing_time': '',
        'elevator_house_ratio': '',
        'heating_method': '',
        'house_structure': '',
        'mortgage_info': '',
        'floor_height': '',
        'last_transaction': '',
        'core_selling_point': '',
        'owner_mind': '',
        'tax_analysis': '',
        'community_support': '',
        'service_intro': '',
        'house_type_interpretation': '',
        'total_price': '',
        'house_tags': '',
        'house_layout': '',
        'build_area': '',
        'unit_price': '',
        'house_orientation': '',
        'house_floor': '',
        'floor_note': '',
        'house_decoration': '',
        'community_name': '',
        'house_area': '',
        'community_avg_price': '',
        'year_on_year': '',
        'month_on_month': '',
        'property_type': '',
        'property_fee': '',
        'build_type': '',
        'community_build_year': '',
        'green_rate': '',
        'plot_rate': '',
        'car_flow': '',
        'total_buildings': '',
        'total_households': '',
        'property_year': '',
    }
    try:
        # 价格
        price = soup.find('span', class_='maininfo-price-num')
        unit = soup.find('span', class_='maininfo-price-unit')
        if price:
            result['total_price'] = clean_str(price.text) + (clean_str(unit.text) if unit else '')

        # 第一行：户型 + 楼层
        item1 = soup.find('div', class_=re.compile('maininfo-model-item-1'))
        if item1:
            nums = item1.find_all('i', class_=re.compile('maininfo-model-strong-num'))
            units = item1.find_all('span', class_=re.compile('maininfo-model-strong-unit'))
            if nums and units:
                layout_parts = []
                for n, u in zip(nums, units):
                    layout_parts.append(clean_str(n.text) + clean_str(u.text))
                result['house_layout'] = ''.join(layout_parts)
            floor = item1.find('div', class_=re.compile('maininfo-model-weak'))
            if floor:
                result['house_floor'] = clean_str(floor.text)

        # 第二行：面积 + 装修
        item2 = soup.find('div', class_=re.compile('maininfo-model-item-2'))
        if item2:
            area_div = item2.find('div', class_=re.compile('maininfo-model-strong'))
            if area_div:
                result['build_area'] = clean_str(area_div.text)
            deco = item2.find('div', class_=re.compile('maininfo-model-weak'))
            if deco:
                result['house_decoration'] = clean_str(deco.text)

        # 第三行：朝向 + 建成年份
        item3 = soup.find('div', class_=re.compile('maininfo-model-item-3'))
        if item3:
            direction_div = item3.find('div', class_=re.compile('maininfo-model-strong'))
            if direction_div:
                result['house_orientation'] = clean_str(direction_div.text)
            build_div = item3.find('div', class_=re.compile('maininfo-model-weak'))
            if build_div:
                build_text = clean_str(build_div.text)
                year_match = re.search(r'(\d{4})年竣工', build_text)
                if year_match:
                    result['build_year'] = year_match.group(1)

        # 房源标签
        tags_div = soup.find('div', class_=re.compile('maininfo-tags'))
        if tags_div:
            tags = tags_div.find_all('span', class_=re.compile('maininfo-tags-item'))
            result['house_tags'] = '|'.join([clean_str(t.text) for t in tags if clean_str(t.text)])

        # 小区名称
        community_div = soup.find('div', class_=re.compile('maininfo-community-item'))
        if community_div:
            link = community_div.find('a')
            if link:
                result['community_name'] = clean_str(link.text)

        # 区域
        name_span = soup.find('span', class_='maininfo-community-item-name')
        if name_span:
            links = name_span.find_all('a')
            if len(links) >= 1:
                result['house_area'] = clean_str(links[0].text)

        # 小区均价
        p = soup.find('p', string='小区均价')
        if p:
            div = p.find_next_sibling('div')
            if div:
                span = div.find('span', class_='monthchange-money')
                if span:
                    result['community_avg_price'] = clean_str(span.text)

        # 物业费
        p = soup.find('p', string='物业费用')
        if p:
            next_p = p.find_next_sibling('p')
            if next_p:
                result['property_fee'] = clean_str(next_p.text)

        # 容积率
        div = soup.find('div', string=re.compile('容积率'))
        if div:
            next_p = div.find_next_sibling('p')
            if next_p:
                result['plot_rate'] = clean_str(next_p.text)

        # 绿化率
        p = soup.find('p', string='绿化率')
        if p:
            next_p = p.find_next_sibling('p')
            if next_p:
                result['green_rate'] = clean_str(next_p.text)

        # 产权性质
        span = soup.find('span', string='产权性质')
        if span:
            sibling = span.find_next_sibling('span')
            if sibling:
                result['property_right'] = clean_str(sibling.text)
    except Exception:
        pass
    return result


# ==================== 解析单个 HTML 文件 ====================
def parse_wuba_html_file(file_path, folder_name, file_name):
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, 'lxml')
    now = datetime.datetime.now()

    city_name = parse_city_from_page(soup)
    city_abbr = CITY_NAME_TO_ABBR.get(city_name, "")
    city_id = CITY_MAP.get(city_abbr, {}).get("id", "")
    verification_code = parse_verification_code(soup)
    basic = parse_basic_info(soup)

    result = {
        # 基础信息
        'verification_code': verification_code,
        'crawl_time': now.strftime('%Y-%m-%d %H:%M:%S'),
        'city_abbr': city_abbr,
        'city_id': city_id,
        'city_name': city_name if city_name else "",
        'house_url': f"local://{folder_name}/{file_name}",

        # fydes 那块的字段
        'build_year': basic['build_year'],
        'has_elevator': basic['has_elevator'],
        'property_right': basic['property_right'],
        'listing_time': basic['listing_time'],
        'elevator_house_ratio': basic['elevator_house_ratio'],
        'heating_method': basic['heating_method'],
        'house_structure': basic['house_structure'],
        'mortgage_info': basic['mortgage_info'],
        'floor_height': basic['floor_height'],
        'last_transaction': basic['last_transaction'],

        # 房源描述相关
        'core_selling_point': basic['core_selling_point'],
        'owner_mind': basic['owner_mind'],
        'tax_analysis': basic['tax_analysis'],
        'community_support': basic['community_support'],
        'service_intro': basic['service_intro'],
        'house_type_interpretation': basic['house_type_interpretation'],

        # 房源核心字段
        'total_price': basic['total_price'],
        'house_tags': basic['house_tags'],
        'house_layout': basic['house_layout'],
        'build_area': basic['build_area'],
        'unit_price': basic['unit_price'],
        'house_orientation': basic['house_orientation'],
        'house_floor': basic['house_floor'],
        'floor_note': basic['floor_note'],
        'house_decoration': basic['house_decoration'],
        'community_name': basic['community_name'],
        'house_area': basic['house_area'],

        # 小区信息
        'community_avg_price': basic['community_avg_price'],
        'year_on_year': basic['year_on_year'],
        'month_on_month': basic['month_on_month'],
        'property_type': basic['property_type'],
        'property_fee': basic['property_fee'],
        'build_type': basic['build_type'],
        'community_build_year': basic['community_build_year'],
        'green_rate': basic['green_rate'],
        'plot_rate': basic['plot_rate'],
        'car_flow': basic['car_flow'],
        'total_buildings': basic['total_buildings'],
        'total_households': basic['total_households'],
        'property_year': basic['property_year'],

        # 错误信息，暂时留空
        'error_msg': "",
    }
    return result


# ==================== 批量解析 ====================
def batch_parse_wuba_html(root_path, date_str=None):
    if date_str is None:
        date_str = datetime.datetime.now().strftime('%Y%m%d')
    results = []
    total_files = 0
    print("开始解析 wuba HTML，日期: " + date_str)
    if not os.path.exists(root_path):
        print("根目录不存在: " + root_path)
        return results

    target_folder = "wuba_ershou"
    folder_path = os.path.join(root_path, target_folder)
    if not os.path.exists(folder_path):
        print("目标文件夹不存在: " + folder_path)
        return results

    date_folder_path = os.path.join(folder_path, date_str)
    if not os.path.exists(date_folder_path):
        print("日期文件夹不存在: " + date_folder_path)
        return results

    print("处理: " + target_folder + "/" + date_str)
    try:
        html_files = [f for f in os.listdir(date_folder_path)
                      if f.lower().endswith('.html') and os.path.isfile(os.path.join(date_folder_path, f))]
        if not html_files:
            print("没有找到 HTML 文件")
            return results
        for html_file in html_files:
            file_path = os.path.join(date_folder_path, html_file)
            total_files += 1
            try:
                print("解析: " + html_file)
                data = parse_wuba_html_file(file_path, target_folder, html_file)
                results.append(data)
            except Exception as e:
                print("解析失败 " + html_file + ": " + str(e))
    except Exception as e:
        print("处理日期文件夹失败: " + str(e))

    print("解析完成，共处理 " + str(total_files) + " 个文件，成功 " + str(len(results)) + " 条")
    return results


if __name__ == "__main__":
    ROOT_PATH = r"D:\MyProject\house_data_RAG\1_data\raw_html"
    today = datetime.datetime.now().strftime('%Y%m%d')
    data = batch_parse_wuba_html(ROOT_PATH, today)
    if data:
        df = pd.DataFrame(data)
        print("字段列表: " + str(df.columns.tolist()))
        print("共 " + str(len(df)) + " 条数据")
        print("数据预览:")
        print(df.head())
        output_dir = r"D:\MyProject\house_data_RAG\1_data\daily_raw"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"wuba_ershou_{today}.csv")
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print("已保存到: " + output_path)
    else:
        print("没有解析到任何数据")