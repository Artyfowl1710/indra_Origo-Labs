"""Seed synthetic accounting only inside the isolated desktop acceptance profile."""
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/"indra/SIH-26/hermes-agent")]

def main():
    home=Path(os.environ["HERMES_HOME"]).resolve()
    expected=Path(os.environ["HERMES_TEST_ISOLATION"]).resolve()
    if home!=expected or not home.is_relative_to(ROOT/"data/test-results") or not home.name.startswith("voice-preview-"):
        raise ValueError("Usage fixture requires the isolated desktop test profile")
    from hermes_state import SessionDB
    db=SessionDB(home/"state.db")
    try:
        db.create_session("fixture-usage",source="cli",model="fixture-code")
        db.update_token_counts("fixture-usage",model="fixture-code",billing_provider="custom",input_tokens=1000,output_tokens=100,cache_read_tokens=400,cache_write_tokens=20,reasoning_tokens=30,api_call_count=1,estimated_cost_usd=.02,cost_status="estimated")
        db.update_token_counts("fixture-usage",model="fixture-code-next",billing_provider="custom",input_tokens=300,output_tokens=30,reasoning_tokens=10,api_call_count=1,estimated_cost_usd=.01,cost_status="estimated")
        db.record_auxiliary_usage("fixture-usage","vision",model="fixture-vision",billing_provider="custom",input_tokens=200,output_tokens=20,cache_read_tokens=40,api_call_count=1,cost_status="unknown")
    finally:db.close()

if __name__=="__main__":main()
