# helpers: source me
A="$HOME/redoubt-artifacts/android-sdk/platform-tools/adb -s emulator-5584"
wait_s(){ timeout "$1" bash -c 'while :; do :; done'; true; }
dump(){ $A shell uiautomator dump /sdcard/u.xml >/dev/null 2>&1; $A shell cat /sdcard/u.xml > "$1.xml"; $A exec-out screencap -p > "$1.png"; grep -o 'text="[^"]*"' "$1.xml" | sort -u | tr '\n' ' '; echo; }
# tap center of first node whose text (or content-desc) matches exactly $1 in dump $2.xml
tapt(){ python3 - "$1" "$2.xml" <<'PY' | { read x y; [ -n "$x" ] && $A shell input tap $x $y && echo "tapped $1 at $x,$y" || echo "NOT FOUND: $1"; }
import re,sys
t,f=sys.argv[1],sys.argv[2]; s=open(f).read()
for m in re.finditer(r'<node [^>]*>',s):
    n=m.group(0)
    tx=re.search(r' text="([^"]*)"',n).group(1); cd=re.search(r'content-desc="([^"]*)"',n).group(1)
    if tx==t or cd==t:
        b=list(map(int,re.findall(r'\d+',re.search(r'bounds="([^"]*)"',n).group(1))))
        print((b[0]+b[2])//2,(b[1]+b[3])//2); break
PY
}
