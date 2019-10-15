import socket

# 创建一个socket对象
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# 建立连接
s.connect(("192.168.1.101", 3306))
# 接收数据
buf = s.recv(10240)
print(type(buf))    #
# 发关数据
s.send(b'hello')
