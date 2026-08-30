import asyncio
from pathlib import Path
import sys
import uuid

# Auto-inject project root and .venv site-packages
PROJECT_ROOT = Path(__file__).resolve().parent
VENV_SITE_PACKAGES = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if VENV_SITE_PACKAGES.exists() and str(VENV_SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(VENV_SITE_PACKAGES))

from app.graph import graph


async def main():
    print("\n" + "=" * 55)
    print("  Personal AI Executive Assistant")
    print("  Powered by LangGraph + FastMCP + Groq")
    print("  Type 'exit' to stop.")
    print("=" * 55 + "\n")

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit"):
                print("\nGoodbye!")
                break

            result = await graph.ainvoke(
                {"user_input": user_input},
                config=config,
            )

            intent = result.get("intent", "general")
            print(f"\n[Workflow: {intent}]")
            print("-" * 55)
            print(result.get("response", "No response generated."))

            if result.get("error"):
                print(f"\n[Notice]: {result['error']}")

            print("-" * 55 + "\n")

        except (KeyboardInterrupt, EOFError):
            print("\nSession ended.")
            break
        except Exception as error:
            print(f"\nAssistant error: {error}\n")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())