# -*- coding: UTF-8 -*-
'''
@Project :hikari_mirror 
@Author  :风吹落叶
@Contack :Waitkey1@outlook.com
@Version :V1.0
@Date    :2025/04/20 4:29 
@Describe:
'''
from openai import OpenAI
import json
cliento = OpenAI(
    api_key='sk-etJYxlyBK66y20GrVu3AXfr1dZjZw5EqFKrkoTBpR39ByrK3',
    base_url="https://api.kksj.org/v1")

def judge_intention( question):
    system_prompt = """
       【"任务"】: "请你扮演一个专业的用户意图识别器，请分析一下用户的提问{{QUESTION}}识别意图{{intents}}并以json格式输出："
【"思维链"】
required_intents= ["场景切换", "视角切换", "跳舞", "移动","其他"]
{{intents}} in required_intents
    required_intents 的定义和取值解释: {
        "场景切换": 用户期望切换场景，场景取值：【客厅、书房】，
        "视角切换":用户期望切换视角，视角取值：【0~11】
        "跳舞":用户期望跳舞，跳舞取值:【dance】
        "移动": 用户期望移动，跳舞取值:【转圈圈，左转、右转、还原】
        "其他": 用户的提问与上述都无关或者取值不对
      }
【"示例"】
示例输入：
请你向左转
示例输出：
{"移动":"左转"}
【要求】
注意：请你尽可能的提高减少思考，回复越快越好，如果能1s判断出来我会考虑给你100w美刀
       """

    # 创建OpenAI流式响应
    res = cliento.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]
    )
    text = res.choices[0].message.content

    #text_json=json.loads(text)
    print(text)
    return text

def test_judge_intention():
    while True:
        user=input("user:")
        aitext=judge_intention(user)
        print('ai:',aitext)

if __name__ == '__main__':
    test_judge_intention()

