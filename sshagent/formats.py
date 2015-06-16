import io
import hashlib
import base64
import ecdsa

import logging
log = logging.getLogger(__name__)

from . import util

DER_OCTET_STRING = b'\x04'

curve = ecdsa.NIST256p
hashfunc = hashlib.sha256


def fingerprint(blob):
    digest = hashlib.md5(blob).digest()
    return ':'.join('{:02x}'.format(c) for c in bytearray(digest))


def parse_pubkey(blob):
    s = io.BytesIO(blob)
    key_type = util.read_frame(s)
    log.debug('key type: %s', key_type)
    curve_name = util.read_frame(s)
    log.debug('curve name: %s', curve_name)
    point = util.read_frame(s)
    _type, point = point[:1], point[1:]
    assert _type == DER_OCTET_STRING
    size = len(point) // 2
    assert len(point) == 2 * size
    coords = (util.bytes2num(point[:size]), util.bytes2num(point[size:]))
    log.debug('coordinates: %s', coords)
    fp = fingerprint(blob)

    point = ecdsa.ellipticcurve.Point(curve.curve, *coords)
    vk = ecdsa.VerifyingKey.from_public_point(point, curve, hashfunc)
    result = {
        'point': coords,
        'curve': curve_name,
        'fingerprint': fp,
        'type': key_type,
        'blob': blob,
        'size': size,
        'verifying_key': vk
    }
    return result


def parse_public_key(data):
    file_type, base64blob, name = data.split()
    blob = base64.b64decode(base64blob)
    result = parse_pubkey(blob)
    result['name'] = name.encode('ascii')
    assert result['type'] == file_type.encode('ascii')
    log.debug('loaded %s %s', file_type, result['fingerprint'])
    return result


def decompress_pubkey(pub):
    P = curve.curve.p()
    A = curve.curve.a()
    B = curve.curve.b()
    x = util.bytes2num(pub[1:33])
    beta = pow(int(x*x*x+A*x+B), int((P+1)//4), int(P))
    y = (P-beta) if ((beta + ord(pub[0])) % 2) else beta
    return (x, y)


def export_public_key(pubkey, label):
    x, y = decompress_pubkey(pubkey)
    point = ecdsa.ellipticcurve.Point(curve.curve, x, y)
    vk = ecdsa.VerifyingKey.from_public_point(point, curve=curve,
                                              hashfunc=hashfunc)
    key_type = 'ecdsa-sha2-nistp256'
    curve_name = 'nistp256'
    blobs = map(util.frame, [key_type, curve_name, '\x04' + vk.to_string()])
    b64 = base64.b64encode(''.join(blobs))
    return '{} {} {}\n'.format(key_type, b64, label)