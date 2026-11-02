"""A continued goal re-registers its host project; cached Docker cwd stays remote."""
import os
from types import SimpleNamespace
import pytest
from tools import terminal_tool as tt


def setup_env(monkeypatch,env):
    monkeypatch.setattr(tt,"_active_environments",{"task":env})
    monkeypatch.setattr(tt,"_task_env_overrides",{})
    monkeypatch.setattr(tt,"_session_cwd",{})
    monkeypatch.setattr(tt,"_resolve_container_task_id",lambda sid:sid)


@pytest.mark.parametrize("host",[r"C:\Users\fixture\project","/home/fixture/project"])
def test_repeated_registration_preserves_live_container_cwd(monkeypatch,host):
    env=SimpleNamespace(cwd="/workspace/subdir",_configured_backend_type="docker",_bound_host_workspace=os.path.normcase(os.path.abspath(host)))
    setup_env(monkeypatch,env)
    for _ in range(3):tt.register_task_env_overrides("task",{"cwd":host,"cwd_source":"session"})
    assert env.cwd=="/workspace/subdir"
    assert tt.get_session_cwd("task")==host
    assert not getattr(env,"_workspace_change_pending",False)


def test_arbitrary_host_mount_path_is_not_treated_as_container_cwd(monkeypatch,tmp_path):
    host=str(tmp_path)
    env=SimpleNamespace(cwd="/workspace",_configured_backend_type="docker",_bound_host_workspace=os.path.normcase(os.path.abspath(host)))
    setup_env(monkeypatch,env)
    tt.register_task_env_overrides("task",{"cwd":host,"cwd_source":"session"})
    assert env.cwd=="/workspace"


def test_mount_switch_refuses_execution_until_new_sandbox(monkeypatch,tmp_path):
    from tools.environments.base import BaseEnvironment
    class FixtureEnvironment(BaseEnvironment):
        def _run_bash(self,*a,**kw):pytest.fail("stale workspace must never execute")
        def cleanup(self):pass
    first=tmp_path/"first";second=tmp_path/"second";first.mkdir();second.mkdir()
    env=FixtureEnvironment("/workspace",10)
    env._configured_backend_type="docker";env._bound_host_workspace=os.path.normcase(os.path.abspath(first))
    setup_env(monkeypatch,env)
    tt.register_task_env_overrides("task",{"cwd":str(second),"cwd_source":"session"})
    with pytest.raises(RuntimeError,match="selected project changed"):env.execute("touch /workspace/should-not-exist")


@pytest.mark.parametrize("backend,new_cwd",[("local",r"C:\Users\fixture\new"),("ssh","/home/remote/new"),("docker","/workspace/new")])
def test_usable_backend_paths_still_update(monkeypatch,backend,new_cwd):
    env=SimpleNamespace(cwd="/old",_configured_backend_type=backend)
    setup_env(monkeypatch,env)
    tt.register_task_env_overrides("task",{"cwd":new_cwd})
    assert env.cwd==new_cwd
