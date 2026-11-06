"""Límite de intentos compartido entre procesos; nunca guarda contraseñas."""
import ipaddress
import unicodedata
from functools import lru_cache
import redis
from django.conf import settings
from django.utils.crypto import salted_hmac

RESERVE = """
local retry = 0
for i,key in ipairs(KEYS) do
    if tonumber(redis.call('GET',key) or '0') >= tonumber(ARGV[i]) then
        retry = math.max(retry,1,redis.call('TTL',key))
    end
end
if retry > 0 then return {0,retry} end
for _,key in ipairs(KEYS) do
    if redis.call('INCR',key) == 1 then redis.call('EXPIRE',key,ARGV[4]) end
end
return {1,0}
"""
SUCCESS = """
redis.call('DEL',KEYS[1],KEYS[2])
local n=tonumber(redis.call('GET',KEYS[3]) or '0')
if n <= 1 then redis.call('DEL',KEYS[3]) else redis.call('DECR',KEYS[3]) end
return 1
"""


@lru_cache(maxsize=4)
def connection(url):
    return redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)


def client_ip(request):
    peer = request.META.get('REMOTE_ADDR', '')
    try:
        address = ipaddress.ip_address(peer)
        trusted = [ipaddress.ip_network(network.strip()) for network in settings.LOGIN_TRUSTED_PROXIES if network.strip()]
        if any(address in network for network in trusted):
            forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')
            if len(forwarded) <= 20:
                for value in reversed(forwarded):
                    address = ipaddress.ip_address(value.strip())
                    if not any(address in network for network in trusted):
                        break
        return str(address)
    except ValueError:
        # No aceptar una cabecera inválida como identidad nueva para evadir el límite.
        return peer or 'unknown'


def reserve(request, username):
    account = unicodedata.normalize('NFKC', username.strip()).casefold()
    ip = client_ip(request)
    def key(value):
        digest = salted_hmac('ivem.login', value, algorithm='sha256').hexdigest()
        return settings.LOGIN_RATE_PREFIX + digest
    keys = [key('pair:' + account + ':' + ip), key('account:' + account), key('ip:' + ip)]
    client = connection(settings.LOGIN_REDIS_URL)
    allowed, retry = client.eval(RESERVE, 3, *keys, settings.LOGIN_PAIR_LIMIT,
                                 settings.LOGIN_ACCOUNT_LIMIT, settings.LOGIN_IP_LIMIT,
                                 settings.LOGIN_RATE_SECONDS)
    return keys, int(retry) if not allowed else 0


def success(keys):
    connection(settings.LOGIN_REDIS_URL).eval(SUCCESS,3,*keys)
