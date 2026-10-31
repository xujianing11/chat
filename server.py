"""Static application and server-side OpenAI-compatible model gateway."""
import http.server
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent

class Handler(http.server.BaseHTTPRequestHandler):
    def send_json(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/health':
            return self.send_json(200, {'ok': True, 'ai_configured': all(os.environ.get(k) for k in ('MODEL_API_KEY', 'MODEL_NAME', 'MODEL_BASE_URL'))})
        files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path not in files:
            return self.send_json(404, {'error': '未找到资源'})
        filename, mime = files[path]
        body = (ROOT / filename).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != '/api/ai':
            return self.send_json(404, {'error': '未找到接口'})
        # Only accept same-origin browser requests; this local development server has no login.
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            return self.send_json(403, {'error': '不允许跨站请求'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.send_json(415, {'error': '需要 JSON 请求'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 100000:
                return self.send_json(413, {'error': '输入过长或为空'})
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError()
            text = data.get('text')
            mode = data.get('mode')
            if not isinstance(text, str) or not text.strip() or mode not in ('summary', 'write'):
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            return self.send_json(400, {'error': '请提供有效文本和操作类型'})
        key, model, base = (os.environ.get(k) for k in ('MODEL_API_KEY', 'MODEL_NAME', 'MODEL_BASE_URL'))
        if not all((key, model, base)):
            return self.send_json(503, {'error': '请在服务端配置 MODEL_API_KEY、MODEL_NAME 和 MODEL_BASE_URL'})
        if urlsplit(base).scheme != 'https':
            return self.send_json(503, {'error': '模型服务地址必须使用 HTTPS'})
        instruction = ('根据用户提供的文献内容，用中文整理研究问题、方法、主要结论与局限。只依据输入，缺失信息明确标注，不编造。' if mode == 'summary' else '你是中文学术写作助手。根据用户的草稿或要求提供改写或写作建议。保留事实和引用，不编造文献、数据或结论；不足之处明确标注。')
        payload = json.dumps({'model': model, 'messages': [{'role': 'system', 'content': instruction}, {'role': 'user', 'content': text}], 'stream': False}).encode()
        request = urllib.request.Request(base.rstrip('/') + '/chat/completions', data=payload, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                result = json.load(response)['choices'][0]['message']['content']
            if not isinstance(result, str):
                raise ValueError()
            return self.send_json(200, {'text': result})
        except urllib.error.HTTPError as exc:
            return self.send_json(502, {'error': f'模型服务返回 HTTP {exc.code}，请检查配置及服务权限'})
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError, IndexError, TypeError):
            return self.send_json(502, {'error': '模型请求失败或响应格式不兼容，请检查模型服务与网络'})

if __name__ == '__main__':
    server = http.server.ThreadingHTTPServer((os.environ.get('HOST', '127.0.0.1'), int(os.environ.get('PORT', '8000'))), Handler)
    print(f'文笺服务已启动，端口 {server.server_port}', flush=True)
    server.serve_forever()
