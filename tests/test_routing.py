from app.graph import route_intent


def test_routing_smart_inbox():
    state = {"user_input": "Which emails need my attention today?"}
    decision = route_intent(state)
    assert decision.get("intent") in ("smart_inbox", "morning_brief")


def test_routing_meeting_prep():
    state = {"user_input": "Prepare me for my next meeting with Sarah."}
    decision = route_intent(state)
    assert decision.get("intent") == "meeting_prep"


def test_routing_what_next():
    state = {"user_input": "What should I work on right now?"}
    decision = route_intent(state)
    assert decision.get("intent") == "what_next"
