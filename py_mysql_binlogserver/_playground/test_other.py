from _md5 import md5

print(md5("select @@version_comment limit 1".encode()).hexdigest())
