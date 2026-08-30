from services.memory_service import delete_fact, get_facts, search_facts, store_fact


def test_memory_store_and_search():
    fact = store_fact(
        category="project",
        key="Project Alpha",
        fact="Project Alpha launch is scheduled for Q4 with Sarah as lead contact",
    )

    assert fact["id"] is not None
    assert fact["category"] == "project"

    all_facts = get_facts()
    assert any(f["id"] == fact["id"] for f in all_facts)

    search_results = search_facts("Sarah")
    assert any(f["id"] == fact["id"] for f in search_results)

    deleted = delete_fact(fact["id"])
    assert deleted is True
