"""Loopback-only deterministic provider for native tool/title acceptance.

No external requests, prompt logging, real credentials or executable tools.
"""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json


class Receiver(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        raw=b'{"fixture":"chat-title","ready":true}'
        self.send_response(200);self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_POST(self):
        try:
            length=int(self.headers.get("Content-Length","0"))
            if not 0<length<=2*1024*1024:raise ValueError()
            body=json.loads(self.rfile.read(length))
            model=body["model"];messages=body["messages"]
            tools={tool.get("function",{}).get("name") for tool in body.get("tools",[])}
            marker=any(message.get("role")=="user" and "RENAME_NATIVE_FIXTURE" in str(message.get("content","")) for message in messages)
            tool_result=any(message.get("role")=="tool" for message in messages)
            call=marker and not tool_result and bool({"rename_current_chat","tool_call"}&tools)
            message={"role":"assistant","content":None if call else "Renamed chat to Dockyard Native Plan."}
            if call:
                direct="rename_current_chat" in tools
                name="rename_current_chat" if direct else "tool_call"
                arguments={"title":"Dockyard Native Plan"} if direct else {"name":"rename_current_chat","arguments":{"title":"Dockyard Native Plan"}}
                message["tool_calls"]=[{"id":"native-title-tool","type":"function","function":{"name":name,"arguments":json.dumps(arguments)}}]
            finish="tool_calls" if call else "stop"
            usage={"prompt_tokens":100,"completion_tokens":20,"total_tokens":120}
            common={"id":"native-title-completion","model":model,"created":1}
            if body.get("stream"):
                delta={"role":"assistant"}
                if call:delta["tool_calls"]=[{"index":0,**message["tool_calls"][0]}]
                else:delta["content"]=message["content"]
                chunks=[{**common,"object":"chat.completion.chunk","choices":[{"index":0,"delta":delta,"finish_reason":None}]},
                        {**common,"object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":finish}]},
                        {**common,"object":"chat.completion.chunk","choices":[],"usage":usage}]
                raw=("".join("data: "+json.dumps(chunk)+"\n\n" for chunk in chunks)+"data: [DONE]\n\n").encode();content_type="text/event-stream"
            else:
                raw=json.dumps({**common,"object":"chat.completion","choices":[{"index":0,"message":message,"finish_reason":finish}],"usage":usage}).encode();content_type="application/json"
            self.send_response(200);self.send_header("Content-Type",content_type);self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
        except (ValueError,KeyError,TypeError):
            self.send_error(400,"Invalid fixture request")


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--port",type=int,required=True);args=parser.parse_args()
    if not 1<=args.port<=65535:raise SystemExit("Invalid fixture port")
    ThreadingHTTPServer(("127.0.0.1",args.port),Receiver).serve_forever()
