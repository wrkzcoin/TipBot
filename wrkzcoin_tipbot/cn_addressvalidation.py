## For random paymentid
import re
import secrets
import sha3
import sys
from binascii import hexlify, unhexlify
import pyed25519

# byte-oriented StringIO was moved to io.BytesIO in py3k
try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO

b = pyed25519.b
q = pyed25519.q
l = pyed25519.l


# CN:
def cn_fast_hash(s):
    return keccak_256(unhexlify(s))


def keccak_256(s):
    # return Keccak().Keccak((len(s)*4, s), 1088, 512, 0x01, 32*8, False).lower()
    k = sha3.keccak_256()
    k.update(s)
    return k.hexdigest()


def sc_reduce(key):
    return int_to_hexstr(hexstr_to_int(key) % l)


def sc_reduce32(key):
    return int_to_hexstr(hexstr_to_int(key) % q)


def public_from_int(i):
    pubkey = ed25519.encodepoint(ed25519.scalarmultbase(i))
    return hexlify(pubkey)


def public_from_secret(sk):
    return public_from_int(hexstr_to_int(sk)).decode('utf-8')


### base58
# MoneroPy - A python toolbox for Monero
# Copyright (C) 2016 The MoneroPy Developers.
#
# MoneroPy is released under the BSD 3-Clause license. Use and redistribution of
# this software is subject to the license terms in the LICENSE file found in the
# top-level directory of this distribution.

__alphabet = [ord(s) for s in '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz']
__b58base = 58
__UINT64MAX = 2 ** 64
__encodedBlockSizes = [0, 2, 3, 5, 6, 7, 9, 10, 11]
__fullBlockSize = 8
__fullEncodedBlockSize = 11


def hex_to_bin(hex_str):
    if len(hex_str) % 2 != 0:
        return "Hex string has invalid length!"
    return [int(hex_str[i * 2:i * 2 + 2], 16) for i in range(len(hex_str) // 2)]

def bin_to_hex(bin_data):
    return "".join([("0" + hex(int(bin_data[i])).split('x')[1])[-2:] for i in range(len(bin_data))])

def str_to_bin(a):
    return [ord(s) for s in a]

def bin_to_str(bin_data):
    return ''.join([chr(bin_data[i]) for i in range(len(bin_data))])


def _uint8be_to_64(data):
    l_data = len(data)

    if l_data < 1 or l_data > 8:
        return "Invalid input length"

    res = 0
    switch = 9 - l_data
    for i in range(l_data):
        if switch == 1:
            res = res << 8 | data[i]
        elif switch == 2:
            res = res << 8 | data[i]
        elif switch == 3:
            res = res << 8 | data[i]
        elif switch == 4:
            res = res << 8 | data[i]
        elif switch == 5:
            res = res << 8 | data[i]
        elif switch == 6:
            res = res << 8 | data[i]
        elif switch == 7:
            res = res << 8 | data[i]
        elif switch == 8:
            res = res << 8 | data[i]
        else:
            return "Impossible condition"
    return res


def _uint64_to_8be(num, size):
    res = [0] * size;
    if size < 1 or size > 8:
        return "Invalid input length"

    twopow8 = 2 ** 8
    for i in range(size - 1, -1, -1):
        res[i] = num % twopow8
        num = num // twopow8

    return res


def encode_block(data, buf, index):
    l_data = len(data)

    if l_data < 1 or l_data > __fullEncodedBlockSize:
        return "Invalid block length: " + str(l_data)

    num = _uint8be_to_64(data)
    i = __encodedBlockSizes[l_data] - 1

    while num > 0:
        remainder = num % __b58base
        num = num // __b58base
        buf[index + i] = __alphabet[remainder];
        i -= 1

    return buf


def encode(hex):
    '''Encode hexadecimal string as base58 (ex: encoding a Monero address).'''
    data = hex_to_bin(hex)
    l_data = len(data)

    if l_data == 0:
        return ""

    full_block_count = l_data // __fullBlockSize
    last_block_size = l_data % __fullBlockSize
    res_size = full_block_count * __fullEncodedBlockSize + __encodedBlockSizes[last_block_size]

    res = [0] * res_size
    for i in range(res_size):
        res[i] = __alphabet[0]

    for i in range(full_block_count):
        res = encode_block(data[(i * __fullBlockSize):(i * __fullBlockSize + __fullBlockSize)], res,
                           i * __fullEncodedBlockSize)

    if last_block_size > 0:
        res = encode_block(
            data[(full_block_count * __fullBlockSize):(full_block_count * __fullBlockSize + last_block_size)], res,
            full_block_count * __fullEncodedBlockSize)

    return bin_to_str(res)


def decode_block(data, buf, index):
    l_data = len(data)

    if l_data < 1 or l_data > __fullEncodedBlockSize:
        return "Invalid block length: " + l_data

    res_size = __encodedBlockSizes.index(l_data)
    if res_size <= 0:
        return "Invalid block size"

    res_num = 0
    order = 1
    for i in range(l_data - 1, -1, -1):
        digit = __alphabet.index(data[i])
        if digit < 0:
            return "Invalid symbol"

        product = order * digit + res_num
        if product > __UINT64MAX:
            return "Overflow"

        res_num = product
        order = order * __b58base

    if res_size < __fullBlockSize and 2 ** (8 * res_size) <= res_num:
        return "Overflow 2"

    tmp_buf = _uint64_to_8be(res_num, res_size)
    for i in range(len(tmp_buf)):
        buf[i + index] = tmp_buf[i]

    return buf


def decode(enc):
    '''Decode a base58 string (ex: a Monero address) into hexidecimal form.'''
    enc = str_to_bin(enc)
    l_enc = len(enc)

    if l_enc == 0:
        return ""

    full_block_count = l_enc // __fullEncodedBlockSize
    last_block_size = l_enc % __fullEncodedBlockSize
    last_block_decoded_size = __encodedBlockSizes.index(last_block_size)

    if last_block_decoded_size < 0:
        return "Invalid encoded length"

    data_size = full_block_count * __fullBlockSize + last_block_decoded_size

    data = [0] * data_size
    for i in range(full_block_count):
        data = decode_block(enc[(i * __fullEncodedBlockSize):(i * __fullEncodedBlockSize + __fullEncodedBlockSize)],
                            data, i * __fullBlockSize)

    if last_block_size > 0:
        data = decode_block(enc[(full_block_count * __fullEncodedBlockSize):(
                    full_block_count * __fullEncodedBlockSize + last_block_size)], data,
                            full_block_count * __fullBlockSize)

    return bin_to_hex(data)


"""Varint encoder/decoder

varints are a common encoding for variable length integer data, used in
libraries such as sqlite, protobuf, v8, and more.

Here's a quick and dirty module to help avoid reimplementing the same thing
over and over again.
"""

if sys.version > '3':
    def _byte(b):
        return bytes((b,))
else:
    def _byte(b):
        return chr(b)


def varint_encode(number):
    """Pack `number` into varint bytes"""
    buf = b''
    while True:
        towrite = number & 0x7f
        number >>= 7
        if number:
            buf += _byte(towrite | 0x80)
        else:
            buf += _byte(towrite)
            break
    return buf


def hexstr_to_int(h):
    '''Converts a hexidecimal string to an integer.'''
    return int.from_bytes(unhexlify(h), "little")


def int_to_hexstr(i):
    '''Converts an integer to a hexidecimal string.'''
    return hexlify(i.to_bytes(32, "little")).decode("latin-1")

# Validate CN address:
def cn_validate_address(
    wallet_address: str,
    get_prefix: int,
    get_addrlen: int,
    get_prefix_char: str
):
    prefix_hex = varint_encode(get_prefix).hex()
    remain_length = get_addrlen - len(get_prefix_char)
    my_regex = r"" + get_prefix_char + r"[a-zA-Z0-9]" + r"{" + str(remain_length) + ",}"
    if len(wallet_address) != int(get_addrlen):
        return False
    if not re.match(my_regex, wallet_address.strip()):
        return False
    try:
        address_hex = decode(wallet_address)
        if address_hex.startswith(prefix_hex):
            i = len(prefix_hex) - 1
            address_no_prefix = address_hex[i:]
            spend = address_no_prefix[1:65]
            view = address_no_prefix[65:129]
            checksum = address_no_prefix[129:137]
            expectedChecksum = cn_fast_hash(prefix_hex + spend + view)[0:8]
            return checksum == expectedChecksum
    except Exception as e:
        pass
    return False

# Validate address:
def cn_validate_integrated(
    wallet_address: str,
    get_prefix_char: str,
    get_prefix: int,
    get_intaddrlen: int
):
    prefix_hex = varint_encode(get_prefix).hex()
    remain_length = get_intaddrlen - len(get_prefix_char)
    my_regex = r"" + get_prefix_char + r"[a-zA-Z0-9]" + r"{" + str(remain_length) + ",}"
    if len(wallet_address) != int(get_intaddrlen):
        return False
    if not re.match(my_regex, wallet_address.strip()):
        return False
    try:
        address_hex = decode(wallet_address)
        if address_hex.startswith(prefix_hex):
            i = len(prefix_hex) - 1
            address_no_prefix = address_hex[i:]
            integrated_id = address_no_prefix[1:129]
            spend = address_no_prefix[(128 + 1):(128 + 65)]
            view = address_no_prefix[(128 + 65):(128 + 129)]
            checksum = address_no_prefix[(128 + 129):(128 + 137)]
            expectedChecksum = cn_fast_hash(prefix_hex + integrated_id + spend + view)[0:8]
            if checksum == expectedChecksum:
                checksum = cn_fast_hash(prefix_hex + spend + view)
                address_b58 = encode(prefix_hex + spend + view + checksum[0:8])
                result = {}
                result['address'] = str(address_b58)
                result['integrated_id'] = str(hextostr(integrated_id))
                return True
            else:
                return False
    except Exception as e:
        pass
    return False

# make_integrated address:
def cn_make_integrated(wallet_address, get_prefix_char: str, get_prefix: int, get_addrlen: int, integrated_id=None):
    prefix_hex = varint_encode(get_prefix).hex()
    remain_length = get_addrlen - len(get_prefix_char)
    my_regex = r"" + get_prefix_char + r"[a-zA-Z0-9]" + r"{" + str(remain_length) + ",}"
    if integrated_id is None:
        integrated_id = paymentid()
    if len(wallet_address) != get_addrlen:
        return None
    if not re.match(my_regex, wallet_address.strip()):
        return None
    if not re.match(r'[a-zA-Z0-9]{64,}', integrated_id.strip()):
        return None
    try:
        address_hex = decode(wallet_address)
        check_paymentid = integrated_id
        integrated_id = integrated_id.encode('latin-1').hex()
        if (address_hex.startswith(prefix_hex)):
            i = len(prefix_hex) - 1
            address_no_prefix = address_hex[i:]
            spend = address_no_prefix[1:65]
            view = address_no_prefix[65:129]
            expected_checksum = cn_fast_hash(prefix_hex + integrated_id + spend + view)[0:8]
            address = (prefix_hex + integrated_id + spend + view + expected_checksum)
            address = str(encode(address))
            result = {}
            result['address'] = wallet_address
            result['paymentid'] = check_paymentid
            result['integrated_address'] = address
            return result
    except Exception as e:
        pass
    return None


## make random paymentid:
def paymentid(length=None):
    if length is None: length = 32
    return secrets.token_hex(length)


def hextostr(hex_str):
    h2b = hex_to_bin(hex_str)
    res = ''
    for i in h2b:
        res = res + chr(i)
    return res
