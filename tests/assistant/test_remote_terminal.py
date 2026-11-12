import subprocess
import sys

from scripts import assistant_chat as terminal


class Response:
    ok=True
    status_code=200
    headers={"content-type":"application/json"}
    def __init__(self,body,status=200):
        self.body=body
        self.status_code=status
    def json(self):
        return self.body


def install_api(monkeypatch,tmp_path):
    monkeypatch.setattr(terminal,"ROOT",tmp_path)
    calls=[]
    def request(method,url,timeout,**kwargs):
        assert timeout==(10,None)
        path=url.split("/api/assistant",1)[1]
        calls.append((method,path))
        if path=="/capabilities":
            return Response({"assistant_enabled":True,"provider_configured":True,
                             "provider":"nvidia","primary_model":"test-model"})
        if (method,path)==("POST","/sessions"):
            return Response({"id":"new-session","messages":[],"runs":[]})
        if (method,path)==("POST","/sessions/new-session/messages"):
            return Response({"id":"run"},202)
        if (method,path)==("GET","/runs/run"):
            return Response({"status":"completed","stage":"complete","result":{
                "answer":"Chưa đủ căn cứ vì kiểm định chưa đạt.","provider":"nvidia","model":"test-model",
                "result":{"result_id":"engine","metrics":{"numerical_detail":42}}}})
        raise AssertionError((method,path))
    monkeypatch.setattr(terminal.requests,"request",request)
    return calls


def test_new_session_ignores_cached_id_and_unicode_check_does_not_infer(monkeypatch,tmp_path):
    calls=install_api(monkeypatch,tmp_path)
    cache=tmp_path/"data/cache/assistant/terminal-session.txt"
    cache.parent.mkdir(parents=True)
    cache.write_text("old-session",encoding="utf-8")
    answers=iter(["/unicode","Mặt Trăng có chiếu sáng và Trái Đất.","/quit"])
    output=[]
    assert terminal.run_remote_console(new_session=True,ask=lambda _:next(answers),say=output.append)==0
    assert cache.read_text()=="new-session"
    assert "Bạn vừa nhập: Mặt Trăng có chiếu sáng và Trái Đất." in output
    assert calls==[("GET","/capabilities"),("POST","/sessions")]


def test_numerical_json_is_only_printed_after_explicit_result_command(monkeypatch,tmp_path):
    install_api(monkeypatch,tmp_path)
    output=[]
    answers=iter(["Giải thích kết quả cho tôi","/result","/quit"])
    def ask(_):
        answer=next(answers)
        if answer=="/result":
            assert any("Kết quả backend đã lưu" in line for line in output)
            assert not any('"numerical_detail"' in line for line in output)
        return answer
    assert terminal.run_remote_console(new_session=True,ask=ask,say=output.append)==0
    assert sum('"numerical_detail"' in line for line in output)==1


def test_vietnamese_console_stream_round_trip_without_api():
    sample="Mặt Trăng – chiếu sáng – Trái Đất – dữ liệu: ă â đ ê ô ơ ư Á Ỳ"
    code="from scripts.assistant_chat import configure_console_utf8; configure_console_utf8(); import sys; sys.stdout.write(sys.stdin.read())"
    response=subprocess.run([sys.executable,"-X","utf8","-c",code],input=sample.encode("utf-8"),capture_output=True,check=True)
    assert response.stdout.decode("utf-8")==sample
