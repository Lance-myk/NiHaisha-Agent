#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中医病症信息提取脚本
从倪海厦人纪系列教材MD文件中提取病症名称、症状、诊断依据和方剂
"""

import os
import re
import json
import sys

# 定义关键文件列表
KEY_FILES = [
    r"C:\Users\Administrator\source\repos\NiHaisha-Agent\md\4伤寒论\24本人纪系列伤寒论上册B5.md",
    r"C:\Users\Administrator\source\repos\NiHaisha-Agent\md\4伤寒论\24本人纪系列伤寒论下册B5.md",
    r"C:\Users\Administrator\source\repos\NiHaisha-Agent\md\4伤寒论\24本人纪系列伤寒论注解B5.md",
    r"C:\Users\Administrator\source\repos\NiHaisha-Agent\md\5金匮要略\24本人纪系列金匮上册B5.md",
    r"C:\Users\Administrator\source\repos\NiHaisha-Agent\md\5金匮要略\24本人纪系列金匮中册B5.md",
    r"C:\Users\Administrator\source\repos\NiHaisha-Agent\md\5金匮要略\24本人纪系列金匮下册B5.md",
    r"C:\Users\Administrator\source\repos\NiHaisha-Agent\md\3黄帝内经\24本人纪系列黄帝内经上册B5.md",
    r"C:\Users\Administrator\source\repos\NiHaisha-Agent\md\3黄帝内经\24本人纪系列黄帝内经中册B5.md",
    r"C:\Users\Administrator\source\repos\NiHaisha-Agent\md\3黄帝内经\24本人纪系列黄帝内经下册B5.md",
]

# 病症分类映射
DISEASE_CATEGORIES = {
    "外感病": [
        "太阳中风", "太阳伤寒", "太阳温病", "温病", "中风", "伤寒", "风温",
        "太阳病", "阳明病", "少阳病", "太阴病", "少阴病", "厥阴病",
        "表证", "表寒", "表热", "寒证", "热证", "寒热往来"
    ],
    "脾胃病": [
        "胃寒", "胃热", "胃胀", "胃痛", "呕吐", "泄泻", "便秘", "下利",
        "腹满", "腹痛", "腹胀", "痞满", "心下痞", "心下满", "心下痛",
        "不食", "不饥", "纳呆", "反胃", "呃逆", "嗳气", "吞酸",
        "脾约", "脾虚", "脾湿", "湿阻", "痰饮", "水饮", "宿食"
    ],
    "肺病": [
        "咳嗽", "咳喘", "气喘", "喘证", "肺痈", "肺痿", "肺胀", "肺痨",
        "痰饮", "痰喘", "痰咳", "痰多", "咯血", "咳血", "胸痛",
        "短气", "少气", "气逆", "气促", "呼吸困难", "胸闷"
    ],
    "心病": [
        "心悸", "心慌", "心痛", "胸痹", "胸满", "胸闷", "心烦", "心下悸",
        "心下痛", "心中痛", "心中悸", "怔忡", "惊悸", "失眠", "不寐",
        "多梦", "健忘", "癫狂", "痫证", "中风", "昏迷", "厥证"
    ],
    "肝病": [
        "肝郁", "肝气郁结", "肝火上炎", "肝阳上亢", "肝风内动",
        "肝血虚", "肝阴虚", "肝阳亢", "肝寒", "肝热",
        "胁痛", "胁胀", "目赤", "目痛", "眩晕", "头痛", "偏头痛"
    ],
    "肾病": [
        "肾虚", "肾阳虚", "肾阴虚", "肾气虚", "肾精不足",
        "水肿", "浮肿", "小便不利", "小便频数", "遗尿", "尿频",
        "尿血", "尿浊", "腰痛", "腰酸", "腰冷", "腰重",
        "遗精", "滑精", "阳痿", "早泄", "不育"
    ],
    "妇科病": [
        "月经不调", "痛经", "闭经", "崩漏", "带下", "带下病",
        "妊娠", "恶阻", "胎动不安", "堕胎", "小产", "难产",
        "产后", "恶露", "乳痈", "乳癖", "不孕", "阴痒"
    ],
    "皮肤病": [
        "疮疡", "痈疽", "疔疮", "丹毒", "湿疹", "癣", "疥", "疮",
        "皮肤瘙痒", "皮肤疹", "麻疹", "风疹", "斑疹", "水痘",
        "瘰疬", "瘿瘤", "白癜风", "牛皮癣", "秃疮"
    ],
    "筋骨病": [
        "痹证", "风湿", "类风湿", "痛风", "痿证", "麻木", "拘挛",
        "腰腿痛", "关节痛", "骨痛", "筋痛", "肌肉痛", "身痛",
        "项强", "背痛", "腰痛", "腿痛", "足痛", "手痛"
    ],
    "其他杂病": [
        "虚劳", "消渴", "黄疸", "积聚", "癥瘕", "瘕块", "肿瘤",
        "汗证", "自汗", "盗汗", "发热", "恶寒", "寒热", "寒热往来",
        "头痛", "眩晕", "耳鸣", "耳聋", "鼻塞", "鼻衄", "牙痛",
        "咽喉痛", "咽痛", "口疮", "口臭", "舌痛", "舌强"
    ]
}

# 方剂名称模式 - 常见经方
COMMON_FORMULAS = [
    "桂枝汤", "麻黄汤", "葛根汤", "小柴胡汤", "大柴胡汤", "柴胡汤",
    "白虎汤", "白虎加人参汤", "承气汤", "大承气汤", "小承气汤", "调胃承气汤",
    "四逆汤", "四逆散", "当归四逆汤", "真武汤", "理中汤", "理中丸",
    "五苓散", "猪苓汤", "泽泻汤", "苓桂术甘汤", "茯苓甘草汤",
    "附子汤", "干姜附子汤", "桂枝附子汤", "甘草附子汤", "白术附子汤",
    "黄连汤", "黄芩汤", "半夏汤", "生姜半夏汤", "甘草干姜汤",
    "芍药甘草汤", "芍药甘草附子汤", "桂枝甘草汤", "桂枝加桂汤",
    "桂枝加葛根汤", "桂枝加附子汤", "桂枝加芍药汤", "桂枝加大黄汤",
    "桂枝去芍药汤", "桂枝去桂加茯苓白术汤",
    "麻黄加术汤", "麻杏石甘汤", "麻黄杏仁甘草石膏汤", "麻黄附子细辛汤",
    "小青龙汤", "大青龙汤", "越婢汤", "越婢加术汤", "桂枝二越婢一汤",
    "桂枝麻黄各半汤", "桂枝二麻黄一汤",
    "抵当汤", "抵当丸", "桃核承气汤", "大黄牡丹汤", "大黄附子汤",
    "十枣汤", "葶苈大枣泻肺汤", "泻心汤", "半夏泻心汤", "生姜泻心汤",
    "甘草泻心汤", "大黄黄连泻心汤", "附子泻心汤",
    "旋覆代赭汤", "橘皮竹茹汤", "吴茱萸汤", "当归生姜羊肉汤",
    "胶艾汤", "温经汤", "胶艾汤", "胶艾四物汤",
    "炙甘草汤", "复脉汤", "麦门冬汤", "竹叶石膏汤", "酸枣仁汤",
    "肾气丸", "八味肾气丸", "桂附八味丸", "六味地黄丸", "知柏地黄丸",
    "乌梅丸", "乌梅汤", "白头翁汤", "桃花汤", "赤石脂汤",
    "茵陈蒿汤", "栀子豉汤", "栀子甘草豉汤", "栀子生姜豉汤",
    "栀子柏皮汤", "栀子厚朴枳实汤", "栀子干姜豉汤",
    "厚朴生姜半夏甘草人参汤", "厚朴七物汤", "厚朴三物汤",
    "半夏厚朴汤", "茯苓桂枝白术甘草汤", "茯苓四逆汤",
    "小建中汤", "大建中汤", "黄芪建中汤", "当归建中汤",
    "当归芍药散", "胶艾汤", "温经汤", "胶艾汤",
    "鳖甲煎丸", "大黄䗪虫丸", "薯蓣丸", "肾气丸", "八味丸",
    "瓜蒌薤白白酒汤", "瓜蒌薤白半夏汤", "枳实薤白桂枝汤",
    "苓桂术甘汤", "泽泻汤", "猪苓汤", "五苓散", "文蛤散",
    "牡蛎汤", "龙骨牡蛎汤", "柴胡加龙骨牡蛎汤", "桂枝加龙骨牡蛎汤",
    "桂苓甘草龙骨牡蛎汤", "桂枝去芍药加蜀漆龙骨牡蛎救逆汤",
    "禹余粮丸", "赤石脂禹余粮汤", "桃花汤",
    "四逆散", "当归四逆汤", "通脉四逆汤", "茯苓四逆汤",
    "人参汤", "理中丸", "附子理中汤", "四君子汤", "四物汤",
    "补中益气汤", "归脾汤", "天王补心丹", "朱砂安神丸",
    "逍遥散", "龙胆泻肝汤", "六味地黄丸", "金匮肾气丸",
    "桂枝茯苓丸", "当归散", "白术散", "胶艾汤", "温经汤",
    "胶艾汤", "胶艾四物汤", "生化汤", "失笑散", "四物汤",
    "完带汤", "易黄汤", "清带汤", "止带方",
    "安胎饮", "泰山磐石散", "寿胎丸", "保产无忧散",
    "生化汤", "产后三方", "下乳方", "通乳方",
    "消渴方", "玉女煎", "白虎加人参汤", "六味地黄丸",
    "肾气丸", "金匮肾气丸", "桂附八味丸", "知柏地黄丸",
    "黄连阿胶汤", "酸枣仁汤", "天王补心丹", "朱砂安神丸",
    "甘麦大枣汤", "百合地黄汤", "百合知母汤", "滑石代赭汤",
    "百合鸡子汤", "百合洗方", "瓜蒌牡蛎散",
    "风引汤", "侯氏黑散", "防己地黄汤", "头风摩散",
    "薯蓣丸", "大黄䗪虫丸", "酸枣汤", "炙甘草汤",
    "鳖甲煎丸", "薯蓣丸", "肾气丸", "八味肾气丸"
]

def classify_disease(disease_name):
    """根据病症名称分类"""
    for category, keywords in DISEASE_CATEGORIES.items():
        for keyword in keywords:
            if keyword in disease_name:
                return category
    return "其他杂病"

def extract_formulas(text):
    """从文本中提取方剂名称"""
    found_formulas = set()
    for formula in COMMON_FORMULAS:
        if formula in text:
            found_formulas.add(formula)
    return list(found_formulas)

def extract_symptoms(text):
    """从文本中提取症状描述"""
    symptoms = []

    # 常见症状关键词
    symptom_keywords = [
        "发热", "恶寒", "恶风", "汗出", "无汗", "头痛", "身痛", "体痛",
        "咳嗽", "咳喘", "气喘", "呕吐", "恶心", "下利", "便秘", "腹痛",
        "腹胀", "腹满", "胸闷", "胸痛", "心悸", "失眠", "多梦",
        "口渴", "口苦", "口干", "口燥", "咽干", "咽痛", "咽喉痛",
        "身重", "身热", "身冷", "畏寒", "怕冷", "怕风",
        "脉浮", "脉沉", "脉数", "脉迟", "脉紧", "脉缓", "脉细", "脉弱",
        "脉大", "脉滑", "脉涩", "脉弦", "脉微", "脉结", "脉代",
        "小便不利", "小便难", "小便数", "小便黄", "小便赤",
        "大便难", "大便溏", "大便干", "大便结", "下利", "泄泻",
        "手足不温", "手足冷", "四肢冷", "四肢厥冷", "四肢微急",
        "烦躁", "躁烦", "心烦", "心下痛", "心下满", "心下痞",
        "项强", "背痛", "腰痛", "腿痛", "关节痛",
        "面色", "舌苔", "舌质", "脉象"
    ]

    for keyword in symptom_keywords:
        if keyword in text:
            symptoms.append(keyword)

    return list(set(symptoms))

def parse_shanghan_treatise(filepath, source_name):
    """解析伤寒论文件"""
    diseases = {}

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return diseases

    # 按条辨分割
    # 匹配类似 "## 一、太阳之为病" 或 "## 一：" 这样的条辨标题
    pattern = r'(?:#{1,3}\s*)?(?:[一二三四五六七八九十百零]+[、：:\s])[^\n]*'

    # 也匹配数字开头的条辨
    pattern2 = r'\n\s*(?:\d+[、：:\s])[^\n]*'

    # 查找所有条辨
    lines = content.split('\n')
    current_disease = None
    current_text = []

    for line in lines:
        line_stripped = line.strip()

        # 检测条辨标题行
        is_tiaobian = False

        # 检查是否是条辨标题
        if line_stripped.startswith('#') and ('太阳' in line_stripped or '阳明' in line_stripped or
                                               '少阳' in line_stripped or '太阴' in line_stripped or
                                               '少阴' in line_stripped or '厥阴' in line_stripped or
                                               '病' in line_stripped or '证' in line_stripped):
            is_tiaobian = True

        # 检查是否是数字开头的条辨
        if re.match(r'^\d+[、：:\s]', line_stripped) or re.match(r'^[一二三四五六七八九十百零]+[、：:\s]', line_stripped):
            is_tiaobian = True

        if is_tiaobian and current_disease:
            # 保存之前的病症
            disease_text = '\n'.join(current_text)
            formulas = extract_formulas(disease_text)
            symptoms = extract_symptoms(disease_text)

            if current_disease not in diseases:
                diseases[current_disease] = {
                    "症状": symptoms,
                    "诊断依据": disease_text[:500] if len(disease_text) > 500 else disease_text,
                    "方剂": formulas,
                    "来源": source_name
                }

            current_text = []
            current_disease = line_stripped
        elif is_tiaobian:
            current_disease = line_stripped
            current_text = []
        elif current_disease:
            current_text.append(line_stripped)

    # 处理最后一个
    if current_disease and current_text:
        disease_text = '\n'.join(current_text)
        formulas = extract_formulas(disease_text)
        symptoms = extract_symptoms(disease_text)

        if current_disease not in diseases:
            diseases[current_disease] = {
                "症状": symptoms,
                "诊断依据": disease_text[:500] if len(disease_text) > 500 else disease_text,
                "方剂": formulas,
                "来源": source_name
            }

    return diseases

def extract_diseases_from_file(filepath, source_name):
    """从单个文件中提取病症信息"""
    diseases = {}

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return diseases

    # 定义病症模式
    # 1. 伤寒论条辨模式: "## 一、太阳之为病..." 或 "## 桂枝汤方"
    # 2. 金匮要略病症模式
    # 3. 黄帝内经病症模式

    # 提取条辨标题和对应内容
    # 匹配条辨编号和标题
    tiaobian_pattern = r'(?:#{1,3}\s*)?([一二三四五六七八九十百零]+)[、：:\s]*([^\n]*)'

    # 也匹配 "XX病"、"XX证" 等模式
    disease_patterns = [
        # 太阳病相关
        r'太阳(中风|伤寒|温病|病)', r'阳明(病|证)', r'少阳(病|证)',
        r'太阴(病|证)', r'少阴(病|证)', r'厥阴(病|证)',
        # 具体病症
        r'(\w+)(?:病|证|症)(?:脉|治|并治)?',
        # 方剂名
        r'(\w+)(?:汤|散|丸)(?:方)?',
    ]

    lines = content.split('\n')
    current_section = None
    current_text = []

    for line in lines:
        line_stripped = line.strip()

        # 检测是否是新的条辨或章节
        is_new_section = False

        # 检查条辨标记
        if re.match(r'^[一二三四五六七八九十百零]+[、：:\s]', line_stripped):
            is_new_section = True
        elif re.match(r'^\d+[、：:\s]', line_stripped):
            is_new_section = True
        elif line_stripped.startswith('#') and len(line_stripped) > 3:
            is_new_section = True

        if is_new_section and current_section:
            # 保存之前的章节
            section_text = '\n'.join(current_text)

            # 提取病症名称
            disease_name = current_section.strip('#').strip()
            if len(disease_name) > 2 and len(disease_name) < 100:
                formulas = extract_formulas(section_text)
                symptoms = extract_symptoms(section_text)

                if disease_name not in diseases and len(symptoms) > 0:
                    diseases[disease_name] = {
                        "症状": symptoms,
                        "诊断依据": section_text[:500] if len(section_text) > 500 else section_text,
                        "方剂": formulas,
                        "来源": source_name
                    }

            current_section = disease_name if is_new_section else None
            current_text = []
        elif is_new_section:
            current_section = line_stripped.strip('#').strip()
            current_text = []
        elif current_section is not None:
            current_text.append(line_stripped)

    # 处理最后一个
    if current_section and current_text:
        section_text = '\n'.join(current_text)
        disease_name = current_section.strip('#').strip()
        if len(disease_name) > 2 and len(disease_name) < 100:
            formulas = extract_formulas(section_text)
            symptoms = extract_symptoms(section_text)

            if disease_name not in diseases and len(symptoms) > 0:
                diseases[disease_name] = {
                    "症状": symptoms,
                    "诊断依据": section_text[:500] if len(section_text) > 500 else section_text,
                    "方剂": formulas,
                    "来源": source_name
                }

    return diseases

def extract_diseases_comprehensive(filepath, source_name):
    """综合提取病症信息"""
    diseases = {}

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return diseases

    lines = content.split('\n')

    # 提取关键病症信息
    # 1. 太阳病系列
    sun_patterns = [
        (r'太阳(中风)', '太阳中风'),
        (r'太阳(伤寒)', '太阳伤寒'),
        (r'太阳(温病)', '太阳温病'),
        (r'名曰[「"]?(风温)[」"]?', '风温'),
    ]

    # 2. 六经病
    liujing_patterns = [
        (r'太阳(病|证)', '太阳病'),
        (r'阳明(病|证)', '阳明病'),
        (r'少阳(病|证)', '少阳病'),
        (r'太阴(病|证)', '太阴病'),
        (r'少阴(病|证)', '少阴病'),
        (r'厥阴(病|证)', '厥阴病'),
    ]

    # 3. 具体症状模式
    symptom_contexts = []

    # 查找 "XX者，XX也" 的诊断句式
    for match in re.finditer(r'([^。，]{3,20})(者[，,])?([^。]{0,30})(名曰[「"]?([^"」]{2,10})[」"]?)?', content):
        context = match.group(0)
        if len(context) > 10:
            symptom_contexts.append(context)

    # 查找 "主之" 的方剂用法
    for match in re.finditer(r'([^。]{5,30})[主之]', content):
        context = match.group(1)
        if len(context) > 5:
            # 提取方剂名
            for formula_match in re.finditer(r'[「"]?(\w{2,8}(?:汤|散|丸))[」"]?', context):
                formula = formula_match.group(1)
                # 提取前面的病症描述
                disease_desc = context[:formula_match.start()]
                if len(disease_desc) > 5:
                    pass  # 记录

    # 基于伤寒论条辨提取
    # 条辨格式通常是: "## 一、太阳之为病，脉浮，头项强痛而恶寒。"
    tiaobian_matches = list(re.finditer(r'(?:#{1,3}\s*)?([一二三四五六七八九十百零]+)[、：:\s]*([^。]*。)?', content))

    for i, match in enumerate(tiaobian_matches):
        tiaobian_num = match.group(1)
        tiaobian_text = match.group(2) if match.group(2) else ""

        if len(tiaobian_text) < 5:
            continue

        # 提取病症名称
        disease_name = None

        # 检查是否是 "XX病" 或 "XX证"
        for dmatch in re.finditer(r'(太阳|阳明|少阳|太阴|少阴|厥阴)(病|证)', tiaobian_text):
            disease_name = dmatch.group(0)
            break

        # 检查 "名曰XX"
        for nmatch in re.finditer(r'名曰[「"]?([^"」]{2,10})[」"]?', tiaobian_text):
            disease_name = nmatch.group(1)
            break

        if disease_name and len(disease_name) > 1:
            # 提取症状
            symptoms = extract_symptoms(tiaobian_text)
            formulas = extract_formulas(tiaobian_text)

            if disease_name not in diseases:
                diseases[disease_name] = {
                    "症状": symptoms,
                    "诊断依据": tiaobian_text,
                    "方剂": formulas,
                    "来源": source_name
                }

    # 基于方剂名提取
    for formula in COMMON_FORMULAS:
        if formula in content:
            # 找到方剂名周围的内容
            for match in re.finditer(r'([^。]{0,100})' + re.escape(formula) + r'([^。]{0,50})', content):
                context = match.group(0)
                # 提取病症描述
                disease_desc = match.group(1).strip()
                if len(disease_desc) > 10:
                    # 尝试提取病症名称
                    for dmatch in re.finditer(r'(\w{2,8}(?:病|证|症))', disease_desc):
                        disease_name = dmatch.group(1)
                        if disease_name not in diseases:
                            symptoms = extract_symptoms(context)
                            diseases[disease_name] = {
                                "症状": symptoms,
                                "诊断依据": context[:300],
                                "方剂": [formula],
                                "来源": source_name
                            }
                        break

    return diseases

def main():
    """主函数"""
    print("开始提取中医病症信息...")
    print(f"处理 {len(KEY_FILES)} 个文件\n")

    all_diseases = {}

    for filepath in KEY_FILES:
        if not os.path.exists(filepath):
            print(f"文件不存在，跳过: {filepath}")
            continue

        source_name = os.path.basename(filepath)
        print(f"正在处理: {source_name}")

        # 使用综合提取方法
        diseases = extract_diseases_comprehensive(filepath, source_name)

        if diseases:
            print(f"  提取到 {len(diseases)} 个病症条目")
            all_diseases.update(diseases)
        else:
            print(f"  未提取到病症信息")

    print(f"\n总共提取到 {len(all_diseases)} 个病症条目")

    # 按分类组织
    categorized = {}
    for disease_name, info in all_diseases.items():
        category = classify_disease(disease_name)
        if category not in categorized:
            categorized[category] = {}
        categorized[category][disease_name] = info

    # 添加统计信息
    result = {
        "_metadata": {
            "total_diseases": len(all_diseases),
            "total_categories": len(categorized),
            "categories": list(categorized.keys()),
            "source_files": len(KEY_FILES)
        },
        "病症分类表": categorized
    }

    # 保存结果
    output_path = r"C:\Users\Administrator\source\repos\NiHaisha-Agent\中医病症分类表.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {output_path}")
    print(f"共 {len(categorized)} 个分类，{len(all_diseases)} 个病症")

    return result

if __name__ == "__main__":
    main()
