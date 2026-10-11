from pathlib import Path
import re

p = Path("web/src/locales/config.ts")
t = p.read_text(encoding="utf-8")
t2 = t.replace("|| LanguageAbbreviation.En;", "|| LanguageAbbreviation.Zh;")
if t2 == t:
    raise SystemExit("config pattern not found")
p.write_text(t2, encoding="utf-8")
print("config.ts default language -> Zh")

for name in [".env", ".env.production", ".env.development"]:
    wp = Path("web") / name
    if wp.exists():
        wt = wp.read_text(encoding="utf-8")
        if "VITE_DEFAULT_LANGUAGE_CODE" in wt:
            wt = re.sub(r"^VITE_DEFAULT_LANGUAGE_CODE=.*$", "VITE_DEFAULT_LANGUAGE_CODE=zh-Hans", wt, flags=re.M)
        else:
            wt = wt.rstrip() + "\nVITE_DEFAULT_LANGUAGE_CODE=zh-Hans\n"
        wp.write_text(wt, encoding="utf-8")
        print("updated", wp)
    else:
        wp.write_text("VITE_DEFAULT_LANGUAGE_CODE=zh-Hans\n", encoding="utf-8")
        print("created", wp)

dp = Path("docker/.env")
dt = dp.read_text(encoding="utf-8")

def setk(text, key, value):
    if re.search(rf"^{re.escape(key)}=.*$", text, re.M):
        return re.sub(rf"^{re.escape(key)}=.*$", f"{key}={value}", text, flags=re.M)
    return text + f"\n{key}={value}\n"

for k, v in [
    ("LANG", "zh_CN.UTF-8"),
    ("LANGUAGE", "zh_CN:zh"),
    ("LC_ALL", "zh_CN.UTF-8"),
    ("SVR_WEB_HTTP_PORT", "8088"),
    ("SVR_WEB_HTTPS_PORT", "8443"),
    ("DOC_ENGINE", "elasticsearch"),
    ("DEVICE", "cpu"),
    ("COMPOSE_PROFILES", "elasticsearch,cpu"),
]:
    dt = setk(dt, k, v)
dp.write_text(dt, encoding="utf-8")
print("docker/.env updated")

# force user language Chinese if DB is up later
print("done source defaults")
