#!/usr/bin/env python3
"""
本機預覽互動地圖（PMTiles 需要 HTTP Range 請求，file:// 或 python -m http.server 無法使用）。
用法：  python3 serve.py        然後開啟 http://localhost:8765/
"""
import os, re, sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs"))


class RangeHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        path = self.translate_path(self.path)
        rng = self.headers.get("Range")
        if os.path.isfile(path) and rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            size = os.path.getsize(path)
            start = int(m.group(1)) if m.group(1) else max(0, size - int(m.group(2)))
            end = int(m.group(2)) if m.group(1) and m.group(2) else size - 1
            end = min(end, size - 1)
            f = open(path, "rb"); f.seek(start)
            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            self._range_len = end - start + 1
            return f
        return super().send_head()

    def copyfile(self, source, outputfile):
        n = getattr(self, "_range_len", None)
        if n is None:
            return super().copyfile(source, outputfile)
        while n > 0:
            chunk = source.read(min(65536, n))
            if not chunk:
                break
            outputfile.write(chunk); n -= len(chunk)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, *a):
        pass


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
print(f"Taiwanwonnerf 地圖預覽： http://localhost:{port}/   (Ctrl+C 結束)")
ThreadingHTTPServer(("127.0.0.1", port), RangeHandler).serve_forever()
