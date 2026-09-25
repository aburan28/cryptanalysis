import sys; sys.path.insert(0,'.')
import g5lib as L
z=L.ZGEN
print([i for i in range(131) if L.ftrace(z**i)==1])
