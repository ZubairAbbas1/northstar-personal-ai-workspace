import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.inbox import InboxAnalysis, InboxItem
from app.workflows.smart_inbox import (
    format_inbox_response,
    parse_mcp_tool_result,
    smart_inbox,
)


def test_parse_mcp_tool_result():
    # Format 1: Text list payload
    raw_1 = [{"type": "text", "text": '[{"id": "123", "subject": "Test"}]'}]
    assert parse_mcp_tool_result(raw_1) == [{"id": "123", "subject": "Test"}]

    # Format 2: Direct JSON string
    raw_2 = '[{"id": "456", "subject": "Test 2"}]'
    assert parse_mcp_tool_result(raw_2) == [{"id": "456", "subject": "Test 2"}]

    # Format 3: Direct list
    raw_3 = [{"id": "789", "subject": "Test 3"}]
    assert parse_mcp_tool_result(raw_3) == [{"id": "789", "subject": "Test 3"}]

    # Format 4: Empty / Invalid
    assert parse_mcp_tool_result([]) == []
    assert parse_mcp_tool_result("invalid json") == []


def test_format_inbox_response():
    analysis = InboxAnalysis(
        items=[
            InboxItem(
                email_id="1",
                category="urgent",
                reason="Server down notification",
                suggested_action="Restart service immediately",
            ),
            InboxItem(
                email_id="2",
                category="action_needed",
                reason="Client asking for quote",
                suggested_action="Send updated pricing sheet",
            ),
            InboxItem(
                email_id="3",
                category="fyi",
                reason="Weekly company newsletter",
                suggested_action=None,
            ),
            InboxItem(
                email_id="4",
                category="ignore",
                reason="Discount on shoes",
                suggested_action=None,
            ),
        ]
    )

    emails_by_id = {
        "1": {"id": "1", "from": "alerts@infra.io", "subject": "Production Alert: Server Down"},
        "2": {"id": "2", "from": "alice@client.com", "subject": "Quote Request for Project Alpha"},
        "3": {"id": "3", "from": "news@company.com", "subject": "Company Update #42"},
        "4": {"id": "4", "from": "promo@deals.com", "subject": "50% Off Everything"},
    }

    result = format_inbox_response(analysis, emails_by_id)

    assert "SMART INBOX" in result
    assert "Urgent: 1 | Action needed: 1 | FYI: 1 | Ignore: 1" in result
    assert "[URGENT] Production Alert: Server Down" in result
    assert "[ACTION NEEDED] Quote Request for Project Alpha" in result
    assert "[FYI] Company Update #42" in result
    # Ignore items should not be listed in the body
    assert "50% Off Everything" not in result


@pytest.mark.asyncio
async def test_smart_inbox_workflow_with_mocks():
    mock_search_tool = MagicMock()
    mock_search_tool.name = "gmail_search"
    mock_search_tool.ainvoke = AsyncMock(return_value=[{
        "type": "text",
        "text": '[{"id": "msg1", "from": "boss@co.com", "subject": "Urgent review", "snippet": "Please review this ASAP", "date": "Today"}]'
    }])

    mock_llm = MagicMock()
    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=InboxAnalysis(
        items=[
            InboxItem(
                email_id="msg1",
                category="urgent",
                reason="Boss requested ASAP review",
                suggested_action="Review attached proposal",
            )
        ]
    ))
    mock_llm.with_structured_output.return_value = mock_structured_llm

    with patch("app.workflows.smart_inbox.get_gmail_tools", AsyncMock(return_value=[mock_search_tool])):
        state = {"user_input": "Check my inbox"}
        result = await smart_inbox(state, llm=mock_llm)

        assert "emails" in result
        assert len(result["emails"]) == 1
        assert "inbox_analysis" in result
        assert result["inbox_analysis"][0]["category"] == "urgent"
        assert "[URGENT] Urgent review" in result["response"]
