# -*- coding: UTF-8 -*-
'''
@Project :ai_hi3 
@Author  :风吹落叶
@Contack :Waitkey1@outlook.com
@Version :V1.0
@Date    :2025/05/22 16:53 
@Describe:
'''
import re
def clean_special_tags(text):
    """
    移除所有<|...|>格式的标签及其内容
    """
    # 优化后的正则表达式（原子组+排除法）
    pattern = r'<\|.*?\|>'
    # 执行替换（保留原始文本换行符）
    return re.sub(pattern, '', text, flags=re.DOTALL)