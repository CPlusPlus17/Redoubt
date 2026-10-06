import http.server, os, re, sys, time
ROOT=sys.argv[1]; PORT=int(sys.argv[2])
http.server.SimpleHTTPRequestHandler.extensions_map.update({".m3u8":"application/vnd.apple.mpegurl",".ts":"video/mp2t",".m4s":"video/iso.segment",".webm":"video/webm",".mp4":"video/mp4",".js":"text/javascript"})
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(s,*a,**k): super().__init__(*a,directory=ROOT,**k)
    def end_headers(s):
        s.send_header("Cache-Control","no-store"); s.send_header("Accept-Ranges","bytes"); super().end_headers()
    def send_head(s):
        rng=s.headers.get("Range"); path=s.translate_path(s.path)
        if not rng or not os.path.isfile(path): return super().send_head()
        m=re.match(r"bytes=(\d*)-(\d*)",rng); size=os.path.getsize(path)
        a=int(m.group(1)) if m.group(1) else size-int(m.group(2)); b=int(m.group(2)) if m.group(1) and m.group(2) else size-1
        b=min(b,size-1); f=open(path,"rb"); f.seek(a)
        s.send_response(206); s.send_header("Content-Type",s.guess_type(path)); s.send_header("Content-Range","bytes %d-%d/%d"%(a,b,size)); s.send_header("Content-Length",str(b-a+1)); s.end_headers()
        import io; data=f.read(b-a+1); f.close(); return io.BytesIO(data)
    def log_message(s,fmt,*a): sys.stderr.write("%.1f %s %s\n"%(time.time(),s.headers.get("Range",""),fmt%a)); sys.stderr.flush()
srv=http.server.ThreadingHTTPServer(("127.0.0.1",PORT),H)
if len(sys.argv)>3:
    import ssl; c=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); c.load_cert_chain(sys.argv[3],sys.argv[4]); srv.socket=c.wrap_socket(srv.socket,server_side=True)
srv.serve_forever()
