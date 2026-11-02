"""Branding changes defaults without renaming runtime contracts or user personas."""
from hermes_cli.default_soul import DEFAULT_SOUL_MD, is_legacy_template_soul
from agent.prompt_builder import DEFAULT_AGENT_IDENTITY


def test_default_identity_is_consistent_between_soul_and_agent():
    assert DEFAULT_SOUL_MD == DEFAULT_AGENT_IDENTITY
    assert "Indra" in DEFAULT_SOUL_MD and "Origo Labs" in DEFAULT_SOUL_MD


def test_exact_previous_default_can_migrate_but_customizations_cannot():
    previous = DEFAULT_SOUL_MD.split(" Describe your available workspace tools", 1)[0].replace("Origo Labs", "CodersbyChance")
    assert is_legacy_template_soul(previous)
    assert is_legacy_template_soul("\ufeff" + previous.replace("â€”", "--") + "\r\n")
    assert not is_legacy_template_soul(previous + " Always speak Hindi.")
    assert not is_legacy_template_soul("You are my assistant built by Origo Labs.")


def test_runtime_home_contract_stays_profile_aware(monkeypatch, tmp_path):
    from hermes_constants import get_hermes_home
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert get_hermes_home() == tmp_path
