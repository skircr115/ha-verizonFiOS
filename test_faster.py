import re
import time
import json

def orig(value_str: str) -> str:
    result = []
    i = 0
    length = len(value_str)
    while i < length:
        char = value_str[i]
        if char == '"':
            result.append(char)
            i += 1
            while i < length:
                c = value_str[i]
                result.append(c)
                if c == "\\" and i + 1 < length:
                    i += 1
                    result.append(value_str[i])
                elif c == '"':
                    i += 1
                    break
                i += 1
            continue
        if char == "'":
            result.append('"')
            i += 1
            while i < length:
                c = value_str[i]
                if c == "\\" and i + 1 < length:
                    next_c = value_str[i + 1]
                    if next_c == "'":
                        result.append("'")
                        i += 2
                    else:
                        result.append(c)
                        result.append(next_c)
                        i += 2
                    continue
                if c == '"':
                    result.append('\\"')
                    i += 1
                    continue
                if c == "'":
                    result.append('"')
                    i += 1
                    break
                result.append(c)
                i += 1
            continue
        result.append(char)
        i += 1
    return "".join(result)


STRING_REGEX = re.compile(r'("[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')')
INNER_RE = re.compile(r"\\.|\"")


def convert_re_split(value_str: str) -> str:
    parts = STRING_REGEX.split(value_str)
    for i in range(1, len(parts), 2):
        s = parts[i]
        if s[0] == "'":
            inner = s[1:-1]
            if "\\" not in inner and '"' not in inner:
                parts[i] = '"' + inner + '"'
            else:
                def inner_repl(im):
                    t = im.group(0)
                    if t == "\\'": return "'"
                    if t == '"': return '\\"'
                    return t
                parts[i] = '"' + INNER_RE.sub(inner_repl, inner) + '"'
    return "".join(parts)


test_data = r"{'known_devices': [{'mac': 'aa:bb', 'name': 'Device 1'}, {'mac': 'cc:dd', 'name': 'Device 2'}], 'router_name': 'My Router'}" * 100

start = time.time()
for _ in range(100): orig(test_data)
orig_time = time.time() - start


start = time.time()
for _ in range(100): convert_re_split(test_data)
split_time = time.time() - start

print(f"Orig: {orig_time:.4f}s")
print(f"Regex split: {split_time:.4f}s (Speedup: {orig_time/split_time:.2f}x)")

# Test correctness
tests = [
    r"""{"key": "value"}""",
    r"""{'key': 'value'}""",
    r"""{'key': "value"}""",
    r"""{"key": 'value'}""",
    r"""{'key': 'val\'ue'}""",
    r"""{'key': 'val"ue'}""",
    r"""{'key': 'val\"ue'}""",
    r"""{'key': 'escaped \\ here'}""",
    r"""{'key': 'mixed \' \" \\'}""",
]

for t in tests:
    o = orig(t)
    r = convert_re_split(t)
    assert o == r, f"Mismatch for {t}: Orig: {o}, Split: {r}"
