# -*- coding: UTF-8 -*-
'''
@Project :hikari_mirror 
@Author  :风吹落叶
@Contack :Waitkey1@outlook.com
@Version :V1.0
@Date    :2025/04/19 16:36 
@Describe:
'''
import cv2
import numpy as np

# 定义棋盘格的尺寸
size = 140
# 定义标定板尺寸
boardx = size * 10
boardy = size * 10

canvas = np.zeros((boardy, boardx, 1), np.uint8) # 创建画布
for i in range(0, boardx):
    for j in range(0, boardy):
        if (int(i/size) + int(j/size)) % 2 != 0: # 判定是否为奇数格
            canvas[j, i] = 255
cv2.imwrite("./chessboard.png", canvas)