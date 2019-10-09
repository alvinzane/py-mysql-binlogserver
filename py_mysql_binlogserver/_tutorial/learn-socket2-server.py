import socket


# 创建一个socket对象
s = socket.socket()
# 监听端口
s.bind(('127.0.0.1', 8000))
s.listen(5)

while True:
    conn, addr = s.accept()
    conn.send(bytes('Welcome python socket server.', 'utf8'))
    # 关闭链接
    conn.close()
