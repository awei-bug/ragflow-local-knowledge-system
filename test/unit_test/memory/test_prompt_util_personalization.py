from memory.utils.prompt_util import PromptAssembler


def test_personal_memory_contract_rejects_agent_guesses_and_secrets():
    prompt = PromptAssembler.assemble_system_prompt({"memory_type": ["semantic", "episodic", "procedural"]})

    assert "agent response is context, not evidence" in prompt.lower()
    assert "Never store passwords" in prompt
    assert "Do not store speculative personality judgments" in prompt
    assert "is_correction=true" in prompt
    assert "Personal learning is passive and gradual" in prompt
    assert "missing profile fields" in prompt


def test_personal_memory_schema_preserves_scope_and_provenance():
    prompt = PromptAssembler.assemble_system_prompt({"memory_type": ["semantic"]})

    assert "category" in prompt
    assert "scope" in prompt
    assert "source" in prompt
    assert "stability" in prompt
    assert "work_style" in prompt
    assert "User prefers official framework patterns" in prompt
