import sys

from scripts.provider_preflight import gemini_model_info, nim_model_info

sys.path.insert(0,"backend")

from app.assistant.knowledge import ProjectKnowledge


def test_nim_preflight_requires_exact_visible_model():
    data = {"data": [{"id": "z-ai/glm-5.3"}, {"id": "meta/other"}]}
    assert nim_model_info(data, "z-ai/glm-5.3") == {"models_visible": 2, "model_listed": True,
        "related_model_ids": ["z-ai/glm-5.3"]}
    assert nim_model_info(data, "z-ai/glm-5.2") == {"models_visible": 2, "model_listed": False,
        "related_model_ids": ["z-ai/glm-5.3"]}


def test_gemini_preflight_keeps_only_model_capabilities():
    body = {"name": "models/gemini-3.1-flash-lite", "inputTokenLimit": 1048576,
            "outputTokenLimit": 65536, "supportedGenerationMethods": ["generateContent", "streamGenerateContent"],
            "description": "not needed in the profile"}
    assert gemini_model_info(body) == {key: body[key] for key in
        ("name", "inputTokenLimit", "outputTokenLimit", "supportedGenerationMethods")}
    assert gemini_model_info(None) == {}


def test_project_knowledge_prefers_current_ephemeris_facts_over_submission_history(tmp_path):
    root=tmp_path/"project"
    current=root/"docs"/"assistant"/"lunarsight-current-context.md"
    historical=root/"docs"/"submission"/"project-description.md"
    current.parent.mkdir(parents=True)
    historical.parent.mkdir(parents=True)
    current.write_text("Current verified JPL Horizons coverage is exactly Site01_P1 and Site04_P1; it does not cover Site02 or all catalog regions.",encoding="utf-8")
    historical.write_text("JPL Horizons supports two precomputed sites for this submission.",encoding="utf-8")
    index=ProjectKnowledge(tmp_path/"knowledge.sqlite3",root,tmp_path/"raw")
    index.rebuild()
    hits=index.search("JPL Horizons coverage all catalog regions P1 Site02",8)
    assert hits and hits[0]["path"]=="docs/assistant/lunarsight-current-context.md"
    assert hits[0]["source_status"]=="current"
    old=index.search("submission JPL Horizons precomputed",8)
    assert any(item["source_status"]=="historical" for item in old)
