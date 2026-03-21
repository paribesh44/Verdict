from app.graphs.mars_graph import build_mars_graph


def test_mars_graph_generates_final_answer():
    graph = build_mars_graph()
    result = graph.invoke({"query": "Why use hierarchical review?"})
    assert "final_answer" in result
    assert result["final_answer"].startswith("Meta-review synthesis")
