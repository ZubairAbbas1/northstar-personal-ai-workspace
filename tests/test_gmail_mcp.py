import asyncio
import json

from app.mcp_client import get_gmail_tools


async def main():

    tools = await get_gmail_tools()

    print("\nAvailable tools:")

    for tool in tools:
        print("-", tool.name)

    recent_tool = next(
        tool
        for tool in tools
        if tool.name == "gmail_recent_emails"
    )

    raw_result = await recent_tool.ainvoke(
        {
            "max_results": 5
        }
    )

    emails = json.loads(
        raw_result[0]["text"]
    )

    print("\nTYPE:", type(emails))
    print("\nRECENT EMAILS\n")

    for email in emails:

        print("=" * 60)

        print(
            "From:",
            email.get("from")
        )

        print(
            "Subject:",
            email.get("subject")
        )

        print(
            "Date:",
            email.get("date")
        )

        print(
            "Snippet:",
            email.get("snippet")
        )

        print()


if __name__ == "__main__":
    asyncio.run(main())