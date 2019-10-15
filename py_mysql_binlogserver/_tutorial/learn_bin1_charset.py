"""
打印GBK编码表
"""
# GBK编码从0x8140 开始，显示 30 行
for row in [0x8140 + x*16 for x in range(30)]:
    print(hex(row), end=" ")
    # 每行显示16个
    for i in range(16):
        high = row+i >> 8 & 0xff        # 高位
        low = row+i & 0xff              # 低位
        try:
            # 用bytes对象转换成GBK字符
            print(bytes([high, low]).decode("gbk"), end="")
        except:
            print(end=" ")
    print("")
