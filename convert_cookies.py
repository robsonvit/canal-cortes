import json

json_content = '''[
  {
    "domain": ".youtube.com",
    "expirationDate": 1809708788.419862,
    "hostOnly": false,
    "httpOnly": true,
    "name": "LOGIN_INFO",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "AFmmF2swRQIhAOlhjKgra1j-aAaGtdLLm7tKgrKO95bIgQSoiVfQi4hFAiBzOqepCqYnLW6YnYrCPfOtaxyNhm7pZWZXwsnOpY3Jqg:QUQ3MjNmekk5UHMzclpYTFA3cG5JNnVnTWR4LUJGRjd5eFRpRHp0ZW0yMnVISGFST3NONmVKOW8zNkN3YVZJMlFFWWtqSXR6X3Q3TUdTYUZ6ZlVYQnVYMWRMUVoxU2FBUUhzVXR6Tk9FZmlMSFlmZHV3WGhiaVVyRXNJbWRVU0JDaVBiQTFURnB4S1NQQkVqU0pQdUdybXVnbWFzdVlLdk1R"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791128634.98036,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-BUCKET",
    "path": "/",
    "sameSite": "lax",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "CIMC"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1822060829.162303,
    "hostOnly": false,
    "httpOnly": false,
    "name": "PREF",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "tz=America.Sao_Paulo&f6=40000000&f5=30000&f7=100"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1819733651.872476,
    "hostOnly": false,
    "httpOnly": true,
    "name": "HSID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "ACylOjDsOfI-pa1Kw"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1819733651.872686,
    "hostOnly": false,
    "httpOnly": true,
    "name": "SSID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "AQJ68qC2XWSbdEX0F"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1819733651.872761,
    "hostOnly": false,
    "httpOnly": false,
    "name": "APISID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "jy-_hOGqoVnWk9iA/Aj2QUPgWdphtkm0CF"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1819733651.872842,
    "hostOnly": false,
    "httpOnly": false,
    "name": "SAPISID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "PNdTdxAmMe8-sGCX/ANJwqVzo3nY_itrsb"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1819733651.872914,
    "hostOnly": false,
    "httpOnly": false,
    "name": "__Secure-1PAPISID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "PNdTdxAmMe8-sGCX/ANJwqVzo3nY_itrsb"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1819733651.873015,
    "hostOnly": false,
    "httpOnly": false,
    "name": "__Secure-3PAPISID",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "PNdTdxAmMe8-sGCX/ANJwqVzo3nY_itrsb"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1819733651.873223,
    "hostOnly": false,
    "httpOnly": false,
    "name": "SID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "g.a000AwnuNh34iYYlWvoLw0XucNQaTyVkDy3YFjBHhbR2zooAqJ90rDwXxl7TAnWorEjWRprGHAACgYKAUYSARESFQHGX2MiWHn1b47a6kzO4pivq5PUcRoVAUF8yKoWr8g9vm-wAy4DXNGD425F0076"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1819733651.873274,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-1PSID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "g.a000AwnuNh34iYYlWvoLw0XucNQaTyVkDy3YFjBHhbR2zooAqJ902NtGxPxzyFsKzDVBO7stMgACgYKAfcSARESFQHGX2Mi1-qpgdqwPCcW2X8rINb-wBoVAUF8yKrRvKVGfQYD7dMacMxlqfVk0076"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1819733651.873319,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-3PSID",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "g.a000AwnuNh34iYYlWvoLw0XucNQaTyVkDy3YFjBHhbR2zooAqJ90GBcr8hG96-9m9yVH9jnXxgACgYKAVMSARESFQHGX2Mi2u0gci7FPiAyUv4pNhNxJhoVAUF8yKokX7G3KAL_59AOLzHqsl7m0076"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1818886776.564167,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-1PSIDTS",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "sidts-CjQBXMw41RcyALWKKp_E9lAtiISgbS-UPysI78OP0iEaKm9hPvrlOBErtIAJs3FiGX56gU81EAA"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1818886776.564414,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-3PSIDTS",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "sidts-CjQBXMw41RcyALWKKp_E9lAtiISgbS-UPysI78OP0iEaKm9hPvrlOBErtIAJs3FiGX56gU81EAA"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1787500833,
    "hostOnly": false,
    "httpOnly": false,
    "name": "ST-tladcw",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "session_logininfo=AFmmF2swRQIhAOlhjKgra1j-aAaGtdLLm7tKgrKO95bIgQSoiVfQi4hFAiBzOqepCqYnLW6YnYrCPfOtaxyNhm7pZWZXwsnOpY3Jqg%3AQUQ3MjNmekk5UHMzclpYTFA3cG5JNnVnTWR4LUJGRjd5eFRpRHp0ZW0yMnVISGFST3NONmVKOW8zNkN3YVZJMlFFWWtqSXR6X3Q3TUdTYUZ6ZlVYQnVYMWRMUVoxU2FBUUhzVXR6Tk9FZmlMSFlmZHV3WGhiaVVyRXNJbWRVU0JDaVBiQTFURnB4S1NQQkVqU0pQdUdybXVnbWFzdVlLdk1R"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1787500834,
    "hostOnly": false,
    "httpOnly": false,
    "name": "ST-3opvp5",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "session_logininfo=AFmmF2swRQIhAOlhjKgra1j-aAaGtdLLm7tKgrKO95bIgQSoiVfQi4hFAiBzOqepCqYnLW6YnYrCPfOtaxyNhm7pZWZXwsnOpY3Jqg%3AQUQ3MjNmekk5UHMzclpYTFA3cG5JNnVnTWR4LUJGRjd5eFRpRHp0ZW0yMnVISGFST3NONmVKOW8zNkN3YVZJMlFFWWtqSXR6X3Q3TUdTYUZ6ZlVYQnVYMWRMUVoxU2FBUUhzVXR6Tk9FZmlMSFlmZHV3WGhiaVVyRXNJbWRVU0JDaVBiQTFURnB4S1NQQkVqU0pQdUdybXVnbWFzdVlLdk1R"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1787500834,
    "hostOnly": false,
    "httpOnly": false,
    "name": "ST-xuwub9",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "session_logininfo=AFmmF2swRQIhAOlhjKgra1j-aAaGtdLLm7tKgrKO95bIgQSoiVfQi4hFAiBzOqepCqYnLW6YnYrCPfOtaxyNhm7pZWZXwsnOpY3Jqg%3AQUQ3MjNmekk5UHMzclpYTFA3cG5JNnVnTWR4LUJGRjd5eFRpRHp0ZW0yMnVISGFST3NONmVKOW8zNkN3YVZJMlFFWWtqSXR6X3Q3TUdTYUZ6ZlVYQnVYMWRMUVoxU2FBUUhzVXR6Tk9FZmlMSFlmZHV3WGhiaVVyRXNJbWRVU0JDaVBiQTFURnB4S1NQQkVqU0pQdUdybXVnbWFzdVlLdk1R"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1787500834,
    "hostOnly": false,
    "httpOnly": false,
    "name": "ST-yve142",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "session_logininfo=AFmmF2swRQIhAOlhjKgra1j-aAaGtdLLm7tKgrKO95bIgQSoiVfQi4hFAiBzOqepCqYnLW6YnYrCPfOtaxyNhm7pZWZXwsnOpY3Jqg%3AQUQ3MjNmekk5UHMzclpYTFA3cG5JNnVnTWR4LUJGRjd5eFRpRHp0ZW0yMnVISGFST3NONmVKOW8zNkN3YVZJMlFFWWtqSXR6X3Q3TUdTYUZ6ZlVYQnVYMWRMUVoxU2FBUUhzVXR6Tk9FZmlMSFlmZHV3WGhiaVVyRXNJbWRVU0JDaVBiQTFURnB4S1NQQkVqU0pQdUdybXVnbWFzdVlLdk1R"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1819036830.555598,
    "hostOnly": false,
    "httpOnly": false,
    "name": "SIDCC",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "AKEyXzXIGI8_HQTXKlKQbFj9K4AQsb8YMtojrePVO_7GZt4BNlfpAp0LwXrcXrg7wQVyTFLSMQ"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1819036830.555975,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-1PSIDCC",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "AKEyXzUywLJTMAdanaglac4wQ3gIFFk_5YNSUYB8B0gRMuVPWd1rWVY_KcqLSxiZP4o1yjESQkY"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1819036830.55616,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-3PSIDCC",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "AKEyXzX06ExtH1lKh5tK9Fr_1IvHnv6-ULI4IwCsyMTgNm0PL0qYx8gpv_SLiuXhDiVp6dVPWQ"
  }
]'''

try:
    cookies = json.loads(json_content)
    with open('cookies.txt', 'w', encoding='utf-8') as f:
        f.write('# Netscape HTTP Cookie File\\n')
        f.write('# This file is generated by automatic conversion. Do not edit.\\n\\n')
        
        for c in cookies:
            domain = c.get('domain', '')
            include_subdomains = 'TRUE' if domain.startswith('.') else 'FALSE'
            path = c.get('path', '/')
            secure = 'TRUE' if c.get('secure', False) else 'FALSE'
            expiry = int(c.get('expirationDate', 0))
            name = c.get('name', '')
            value = c.get('value', '')
            
            f.write(f"{domain}\\t{include_subdomains}\\t{path}\\t{secure}\\t{expiry}\\t{name}\\t{value}\\n")
    print('Converted JSON to Netscape format in cookies.txt')
except Exception as e:
    print(f'Error: {e}')
