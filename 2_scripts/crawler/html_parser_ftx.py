# -*- coding: utf-8 -*-
"""
本地 HTML 房源提取脚本（ftx 版本）
从保存的房天下房源页面里提取数据，字段和之前爬虫保持一致
"""

import os
import re
import datetime
from lxml import etree
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
    if s is None:
        return ""
    return str(s).strip().replace("\n", "").replace("\r", "").replace("\t", " ").replace("  ", " ")


def extract_num(s):
    if not s:
        return ""
    match = re.search(r'(\d+\.?\d*)', str(s))
    return match.group(1) if match else ""


# ==================== 从页面提取城市 ====================
def parse_city_from_page(html):
    try:
        breadcrumb = html.xpath('//div[contains(@class, "breadcrumb")]//a/text()')
        for text in breadcrumb:
            city_name = clean_str(text)
            if city_name in CITY_NAME_TO_ABBR:
                return city_name
    except:
        pass
    try:
        address_links = html.xpath('//div[@id="address"]/a/text()')
        for text in address_links:
            city_name = clean_str(text)
            if city_name in CITY_NAME_TO_ABBR:
                return city_name
    except:
        pass
    try:
        title = html.xpath('//title/text()')
        if title:
            for city_name in CITY_NAME_TO_ABBR.keys():
                if city_name in title[0]:
                    return city_name
    except:
        pass
    return None


# ==================== 提取核验编码 ====================
def parse_verification_code(html):
    try:
        label = html.xpath('//span[contains(text(), "房源核验编码")]')
        if label:
            code = label[0].xpath('./following-sibling::span[@class="houseInfo-main-item-name"]/text()')
            if code:
                return clean_str(code[0])
            parent = label[0].xpath('./parent::td')
            if parent:
                code = parent[0].xpath('.//span[@class="houseInfo-main-item-name"]/text()')
                if code:
                    return clean_str(code[0])
    except:
        pass
    return ""


# ==================== 提取函数 ====================
def parse_house_core_info(html):
    result = {
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
    }
    try:
        root = html.xpath('//div[@class="tab-cont-right"]')
        if not root:
            return result
        # 总价
        price_num = root[0].xpath('.//div[@class="trl-item price_esf sty1"]/i/text()')
        price_unit = root[0].xpath('.//div[@class="trl-item price_esf sty1"]/text()')
        price_unit = ''.join([t.strip() for t in price_unit if t.strip()])
        if price_num:
            result['total_price'] = clean_str(price_num[0]) + price_unit
        # 标签
        tags = root[0].xpath('.//div[@class="bqian clearfix blue"]/span/text()')
        tags_clean = list(set([clean_str(t) for t in tags if clean_str(t)]))
        result['house_tags'] = '|'.join(tags_clean) if tags_clean else ''
        # 第一行
        box1 = root[0].xpath('.//div[@class="tr-line clearfix"][not(contains(@class,"zf_new_title"))][1]')
        if box1:
            layout = box1[0].xpath('.//div[@class="trl-item1 w146"]/div[@class="tt"]/text()')
            if layout:
                result['house_layout'] = clean_str(layout[0])
            area = box1[0].xpath('.//div[@class="trl-item1 w182"]/div[@class="tt"]/text()')
            if area:
                result['build_area'] = clean_str(area[0])
            price = box1[0].xpath('.//div[@class="trl-item1 w132"]/div[@class="tt"]/text()')
            if price:
                result['unit_price'] = clean_str(price[0])
        # 第二行
        box2 = root[0].xpath('.//div[@class="tr-line clearfix"][not(contains(@class,"zf_new_title"))][2]')
        if box2:
            orientation = box2[0].xpath('.//div[@class="trl-item1 w146"]/div[@class="tt"]/text()')
            if orientation:
                result['house_orientation'] = clean_str(orientation[0])
            floor = box2[0].xpath('.//div[@class="trl-item1 w182"]/div[@class="tt"]/text()')
            if floor:
                result['house_floor'] = clean_str(floor[0])
            floor_note = box2[0].xpath('.//div[@class="trl-item1 w182"]/div[@class="font14"]/text()')
            if floor_note:
                result['floor_note'] = clean_str(floor_note[0]).replace('楼层（', '').replace('）', '')
            decoration = box2[0].xpath('.//div[@class="trl-item1 w132"]/div[@class="tt"]/text()')
            if decoration:
                result['house_decoration'] = clean_str(decoration[0])
        # 小区名
        community = root[0].xpath('.//a[@id="juhexq_A01_01_05"]/text()')
        if community:
            result['community_name'] = clean_str(community[0])
        # 区域
        areas = root[0].xpath('.//div[@id="address"]/a/text()')
        areas_clean = [clean_str(a) for a in areas if clean_str(a)]
        result['house_area'] = ' '.join(areas_clean)
    except Exception:
        pass
    return result


def parse_community_info(html):
    result = {
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
        container = html.xpath('//div[@class="cont pt30"]')
        if not container:
            return result

        def extract_field(lab_text):
            xpath = f'.//div[normalize-space(span[@class="lab"]/text())="{lab_text}"]/span[contains(@class,"rcont")]//text()'
            field_raw = container[0].xpath(xpath)
            return clean_str(''.join([t.strip() for t in field_raw if t.strip()]))

        # 参考均价
        avg_num = container[0].xpath(
            './/div[normalize-space(span[@class="lab"]/text())="参考均价"]/span[contains(@class,"rcont")]/i/text()')
        avg_unit = extract_field("参考均价")
        if avg_num:
            avg_unit_clean = avg_unit.replace(clean_str(avg_num[0]), "") if avg_num else ""
            result['community_avg_price'] = clean_str(avg_num[0]) + avg_unit_clean
        result['year_on_year'] = extract_field("同比去年")
        result['month_on_month'] = extract_field("环比上月")
        result['property_type'] = extract_field("物业类型")
        result['property_fee'] = extract_field("物业费用")
        result['build_type'] = extract_field("建筑类型")
        result['community_build_year'] = extract_field("建筑年代")
        result['green_rate'] = extract_field("绿 化 率")
        result['plot_rate'] = extract_field("容 积 率")
        result['car_flow'] = extract_field("人车分流")
        result['total_buildings'] = extract_field("总楼栋数")
        result['total_households'] = extract_field("总 户 数")
        result['property_year'] = ""
    except Exception:
        pass
    return result


def parse_fydes_basic_info(html):
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
    }
    try:
        container = html.xpath('//div[@class="content-item fydes-item"]')
        if not container:
            return result

        def extract_field(lab_text):
            xpath = f'.//span[text()="{lab_text}"]/following-sibling::span[@class="rcont"]/text()'
            field = container[0].xpath(xpath)
            return clean_str(field[0]) if field else ''

        result['build_year'] = extract_field("建筑年代")
        result['has_elevator'] = extract_field("有无电梯")
        result['property_right'] = extract_field("产权性质")
        result['listing_time'] = extract_field("挂牌时间")
        result['elevator_house_ratio'] = extract_field("梯户比例")
        result['heating_method'] = extract_field("供暖方式")
        result['house_structure'] = extract_field("房屋结构")
        result['mortgage_info'] = extract_field("抵押信息")
        result['floor_height'] = extract_field("楼层高度")
        result['last_transaction'] = extract_field("上次交易")
    except Exception:
        pass
    return result


def parse_fy_ms_info(html):
    result = {
        'core_selling_point': '',
        'owner_mind': '',
        'tax_analysis': '',
        'community_support': '',
        'service_intro': '',
        'house_type_interpretation': '',
    }
    try:
        container = html.xpath('//div[@class="fy-ms-list"]')
        if not container:
            return result

        def extract_field(lab_text):
            xpath = f'.//li[.//div[@class="t" and text()="{lab_text}"]]/div[@class="c"]//text()'
            parts = container[0].xpath(xpath)
            return clean_str(''.join(parts)) if parts else ''

        result['core_selling_point'] = extract_field("核心卖点")
        result['owner_mind'] = extract_field("业主心态")
        result['tax_analysis'] = extract_field("税费分析")
        result['community_support'] = extract_field("小区配套")
        result['service_intro'] = extract_field("服务介绍")
        result['house_type_interpretation'] = extract_field("户型解读")
    except Exception:
        pass
    return result


# ==================== 主解析函数 ====================
def parse_ftx_html_file(file_path, folder_name, file_name):
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    html = etree.HTML(html_content)
    now = datetime.datetime.now()

    city_name = parse_city_from_page(html)
    city_abbr = CITY_NAME_TO_ABBR.get(city_name, "")
    city_id = CITY_MAP.get(city_abbr, {}).get("id", "")

    core = parse_house_core_info(html)
    community = parse_community_info(html)
    fydes = parse_fydes_basic_info(html)
    ms = parse_fy_ms_info(html)
    verification_code = parse_verification_code(html)

    result = {
        # 基础字段
        'verification_code': verification_code,
        'crawl_time': now.strftime('%Y-%m-%d %H:%M:%S'),
        'city_abbr': city_abbr,
        'city_id': city_id,
        'city_name': city_name if city_name else "",
        'house_url': f"local://{folder_name}/{file_name}",

        # fydes 基本信息
        'build_year': fydes['build_year'],
        'has_elevator': fydes['has_elevator'],
        'property_right': fydes['property_right'],
        'listing_time': fydes['listing_time'],
        'elevator_house_ratio': fydes['elevator_house_ratio'],
        'heating_method': fydes['heating_method'],
        'house_structure': fydes['house_structure'],
        'mortgage_info': fydes['mortgage_info'],
        'floor_height': fydes['floor_height'],
        'last_transaction': fydes['last_transaction'],

        # 房源描述
        'core_selling_point': ms['core_selling_point'],
        'owner_mind': ms['owner_mind'],
        'tax_analysis': ms['tax_analysis'],
        'community_support': ms['community_support'],
        'service_intro': ms['service_intro'],
        'house_type_interpretation': ms['house_type_interpretation'],

        # 房源核心信息
        'total_price': core['total_price'],
        'house_tags': core['house_tags'],
        'house_layout': core['house_layout'],
        'build_area': core['build_area'],
        'unit_price': core['unit_price'],
        'house_orientation': core['house_orientation'],
        'house_floor': core['house_floor'],
        'floor_note': core['floor_note'],
        'house_decoration': core['house_decoration'],
        'community_name': core['community_name'],
        'house_area': core['house_area'],

        # 小区信息
        'community_avg_price': community['community_avg_price'],
        'year_on_year': community['year_on_year'],
        'month_on_month': community['month_on_month'],
        'property_type': community['property_type'],
        'property_fee': community['property_fee'],
        'build_type': community['build_type'],
        'community_build_year': community['community_build_year'],
        'green_rate': community['green_rate'],
        'plot_rate': community['plot_rate'],
        'car_flow': community['car_flow'],
        'total_buildings': community['total_buildings'],
        'total_households': community['total_households'],
        'property_year': community['property_year'],

        'error_msg': "",
    }
    return result


# ==================== 批量处理 ====================
def batch_parse_ftx_html(root_path, date_str=None):
    if date_str is None:
        date_str = datetime.datetime.now().strftime('%Y%m%d')
    results = []
    total_files = 0
    print("开始解析 ftx HTML，日期: " + date_str)
    if not os.path.exists(root_path):
        print("根目录不存在: " + root_path)
        return results

    target_folder = "ftx_ershou"
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
                data = parse_ftx_html_file(file_path, target_folder, html_file)
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
    data = batch_parse_ftx_html(ROOT_PATH, today)
    if data:
        df = pd.DataFrame(data)
        print("字段列表: " + str(df.columns.tolist()))
        print("共 " + str(len(df)) + " 条数据")
        print("数据预览:")
        print(df.head())
        output_dir = r"D:\MyProject\house_data_RAG\1_data\daily_raw"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"ftx_ershou_{today}.csv")
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print("已保存到: " + output_path)
    else:
        print("没有解析到任何数据")