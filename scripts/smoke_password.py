from app import check_password, WEB_PASSWORD, PW_MAX_TRIES
from app import _pw_failures

print(f"Password set: {'***' if WEB_PASSWORD else 'empty'}")
print(f"Max tries: {PW_MAX_TRIES}")

ip = "192.168.1.1"

# 5 wrong attempts
for i in range(6):
    err = check_password(ip, {"password": "wrong"})
    print(f"  Attempt {i+1} wrong: {err}")

# correct while locked
err = check_password(ip, {"password": WEB_PASSWORD})
print(f"  Correct while locked: {err}")

# clear and try again
_pw_failures[ip] = []
err = check_password(ip, {"password": WEB_PASSWORD})
print(f"  Correct after clear: {err}")

print("All OK")
