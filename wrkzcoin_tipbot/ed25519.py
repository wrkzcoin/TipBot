# The reference Ed25519 software is in the public domain.
#     Source: https://ed25519.cr.yp.to/python/ed25519.py
#     Date accessed: 2 Nov. 2016
#
# Additions at bottom are based on Shen Noether's ed25519.py in MiniNero.
#     Source: https://github.com/monero-project/mininero/blob/master/ed25519.py
#     Most recent commit: bda9d2c33d1baeb4fefccfcc16105b131535cdf1
#     Date accessed: 2 Nov. 2016
#
# Additions and changes made to the original sources are released as specified
# in 'LICENSE' document distributed with this software.

import hashlib
import operator as _oper
import sys as _sys

# Set up byte handling for Python 2 or 3
if _sys.version_info.major == 2:
    int2byte = chr
    range = xrange

    def indexbytes(buf, i):
        return ord(buf[i])

    def intlist2bytes(l):
        return b"".join(chr(c) for c in l)
else:
    indexbytes = _oper.getitem
    intlist2bytes = bytes
    int2byte = _oper.methodcaller("to_bytes", 1, "big")

b = 256
q = 2**255 - 19
l = 2**252 + 27742317777372353535851937790883648493

def H(m):
    return hashlib.sha512(m).digest()

def expmod(b, e, m):
    if e == 0: return 1
    t = expmod(b, e//2, m)**2 % m
    if e & 1: t = (t*b) % m
    return t

def inv(x):
  return expmod(x, q-2, q)

d = -121665 * inv(121666)
I = expmod(2, (q-1)//4, q)

def xrecover(y):
    xx = (y*y-1) * inv(d*y*y+1)
    x = expmod(xx, (q+3)//8, q)
    if (x*x - xx) % q != 0: x = (x*I) % q
    if x % 2 != 0: x = q-x
    return x

By = 4 * inv(5)
Bx = xrecover(By)
B = [Bx%q, By%q]

def edwards(P, Q):
    x1 = P[0]
    y1 = P[1]
    x2 = Q[0]
    y2 = Q[1]
    x3 = (x1*y2+x2*y1) * inv(1+d*x1*x2*y1*y2)
    y3 = (y1*y2+x1*x2) * inv(1-d*x1*x2*y1*y2)
    return [x3%q, y3%q]

def scalarmult(P, e):
    if e == 0: return [0, 1]
    Q = scalarmult(P, e//2)
    Q = edwards(Q, Q)
    if e & 1: Q = edwards(Q, P)
    return Q

def encodeint(y):
    bits = [(y >> i) & 1 for i in range(b)]
    return b''.join([int2byte(sum([bits[i*8 + j] << j for j in range(8)])) for i in range(b//8)])

def encodepoint(P):
    x = P[0]
    y = P[1]
    bits = [(y >> i) & 1 for i in range(b-1)] + [x & 1]
    return b''.join([int2byte(sum([bits[i * 8 + j] << j for j in range(8)])) for i in range(b//8)])

def bit(h, i):
    return (indexbytes(h, i//8) >> (i%8)) & 1

def publickey(sk):
    h = H(sk)
    a = 2**(b-2) + sum(2**i * bit(h, i) for i in range(3, b-2))
    A = scalarmult(B, a)
    return encodepoint(A)

def Hint(m):
    h = H(m)
    return sum(2**i * bit(h, i) for i in range(2*b))

def signature(m, sk, pk):
    h = H(sk)
    a = 2**(b-2) + sum(2**i * bit(h, i) for i in range(3, b-2))
    r = Hint(intlist2bytes([indexbytes(h, j) for j in range(b//8, b//4)]) + m)
    R = scalarmult(B, r)
    S = (r + Hint(encodepoint(R)+pk+m) * a) % l
    return encodepoint(R) + encodeint(S)

def isoncurve(P):
    x = P[0]
    y = P[1]
    return (-x*x + y*y - 1 - d*x*x*y*y) % q == 0

def decodeint(s):
    return sum(2**i * bit(s, i) for i in range(0, b))

def decodepoint(s):
    y = sum(2**i * bit(s, i) for i in range(0, b-1))
    x = xrecover(y)
    if x & 1 != bit(s, b-1): x = q - x
    P = [x, y]
    if not isoncurve(P): raise Exception("decoding point that is not on curve")
    return P

def checkvalid(s, m, pk):
    if len(s) != b//4: raise Exception("signature length is wrong")
    if len(pk) != b//8: raise Exception("public-key length is wrong")
    R = decodepoint(s[0:b//8])
    A = decodepoint(pk)
    S = decodeint(s[b//8:b//4])
    h = Hint(encodepoint(R) + pk + m)
    if scalarmult(B, S) != edwards(R, scalarmult(A, h)):
        raise Exception("signature does not pass verification")

# ----------

# Copyright (c) 2014-2016, The Monero Project
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are
# permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of
#    conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list
#    of conditions and the following disclaimer in the documentation and/or other
#    materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be
#    used to endorse or promote products derived from this software without specific
#    prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL
# THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF
# THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

def radix255(x):
    x = x % q
    if x + x > q: x -= q
    x = [x, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    bits = [26, 25, 26, 25, 26, 25, 26, 25, 26, 25]
    for i in range(9):
        carry = (x[i] + 2**(bits[i]-1)) // (2**bits[i])
        x[i] -= carry * 2**bits[i]
        x[i + 1] += carry
    result = ",".join(str(xi) for xi in x)
    return result

def theD():
    return d

def computeA():
    return 2 * ((1-d)%q) * inv((1+d)%q) % q

def sqroot(xx):
    x = expmod(xx, (q+3)//8, q)
    if (x*x - xx) % q != 0:
        x = (x*I) % q
    if (x*x - xx) % q != 0:
        print("no square root!")
    return x

def edwards_Minus(P, Q):
    x1 = P[0]
    y1 = P[1]
    x2 = (-Q[0]) % q
    y2 = Q[1]
    x3 = (x1*y2+x2*y1) * inv(1+d*x1*x2*y1*y2)
    y3 = (y1*y2+x1*x2) * inv(1-d*x1*x2*y1*y2)
    return [x3%q, y3%q]

def scalarmultbase(e):
    if e == 0: return [0, 1]
    Q = scalarmult(B, e//2)
    Q = edwards(Q, Q)
    if e & 1: Q = edwards(Q, B)
    return Q

def decodepointcheck(s):
    y = sum(2**i * bit(s, i) for i in range(0, b-1))
    x = xrecover(y)
    if x & 1 != bit(s, b-1): x = q - x
    P = [x, y]
    if not isoncurve(P):
        quit()
        raise Exception("decoding point that is not on curve")
    return P
