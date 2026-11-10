"""并行分段下载（HTTP Range），断点续传。用法: python pdownload.py URL OUT [parts]
只发送最普通的请求头，不带任何个人信息。"""
import os, sys, threading, time, requests

def head_size(url):
    r = requests.head(url, allow_redirects=True, timeout=60)
    return int(r.headers["Content-Length"])

def fetch_part(url, out, i, start, end):
    part = f"{out}.part{i}"
    while True:
        have = os.path.getsize(part) if os.path.exists(part) else 0
        if start + have > end:
            return
        try:
            with requests.get(url, headers={"Range": f"bytes={start+have}-{end}"}, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(part, "ab") as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
        except Exception as e:  # 重试
            print(f"part{i} retry: {e}", flush=True); time.sleep(5)

def main():
    url, out = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 16
    size = head_size(url)
    step = size // n + 1
    ts = []
    for i in range(n):
        s, e = i * step, min(size - 1, (i + 1) * step - 1)
        t = threading.Thread(target=fetch_part, args=(url, out, i, s, e), daemon=True); t.start(); ts.append(t)
    t0 = time.time()
    while any(t.is_alive() for t in ts):
        time.sleep(30)
        got = sum(os.path.getsize(f"{out}.part{i}") for i in range(n) if os.path.exists(f"{out}.part{i}"))
        print(f"{got/1e6:.1f}/{size/1e6:.1f} MB  {got/1e3/(time.time()-t0):.0f} kB/s", flush=True)
    with open(out, "wb") as f:
        for i in range(n):
            with open(f"{out}.part{i}", "rb") as p:
                f.write(p.read())
    assert os.path.getsize(out) == size, "size mismatch"
    for i in range(n): os.remove(f"{out}.part{i}")
    print("done", out, size)

if __name__ == "__main__":
    main()
