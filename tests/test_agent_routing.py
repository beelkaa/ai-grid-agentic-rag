import unittest
from unittest.mock import AsyncMock, patch

import backend.core.agent as agent


CATALOG_REQUESTS = (
    "What models are currently available?",
    "List all available AI Grid models.",
)
ARCHITECTURE_REQUESTS = (
    "Design an Agentic RAG architecture and determine which models should be used for each component.",
    "Compare models such as Gemma and Qwen for a production coding agent.",
    "You are not being asked to list AI Grid models. Design the architecture and explain model selection, retrieval, and compatibility decisions.",
)


class AgentRoutingTests(unittest.IsolatedAsyncioTestCase):
    def test_catalog_requests_keep_catalog_tool_available(self):
        tool_names = {
            tool["function"]["name"]
            for tool in agent._tools_for_messages(
                [{"role": "user", "content": CATALOG_REQUESTS[0]}]
            )
        }

        self.assertIn("list_available_models", tool_names)
        self.assertIn("search_documents", tool_names)

    def test_complex_requests_keep_retrieval_and_catalog_tools_available(self):
        for question in ARCHITECTURE_REQUESTS:
            with self.subTest(question=question):
                tool_names = {
                    tool["function"]["name"]
                    for tool in agent._tools_for_messages(
                        [{"role": "user", "content": question}]
                    )
                }

                self.assertIn("search_documents", tool_names)
                self.assertIn("list_available_models", tool_names)

    async def test_blocking_entry_uses_react_for_architecture_question(self):
        question = ARCHITECTURE_REQUESTS[0]
        run_result = {
            "answer": "grounded draft",
            "context": "retrieved documentation",
            "search_iterations": 1,
        }

        with (
            patch.object(agent, "get_messages", new=AsyncMock(return_value=[])),
            patch.object(agent, "run_agent", new=AsyncMock(return_value=run_result)) as run_agent,
            patch.object(agent, "reflect", new=AsyncMock(return_value={"sufficient": True, "missing": ""})),
            patch.object(agent, "list_available_models", new=AsyncMock()) as list_models,
            patch.object(agent, "save_message", new=AsyncMock()),
        ):
            answer = await agent.chat_with_agent(question, session_id=1)

        self.assertEqual(answer, "grounded draft")
        run_agent.assert_awaited_once()
        list_models.assert_not_awaited()

    async def test_streaming_entry_uses_react_for_problematic_question(self):
        question = ARCHITECTURE_REQUESTS[2]
        stream_calls = []
        run_result = {
            "answer": "grounded draft",
            "context": "retrieved documentation",
            "search_iterations": 1,
        }

        async def fake_stream_agent(*args, **kwargs):
            stream_calls.append((args, kwargs))
            yield {"type": "token", "text": "grounded draft"}
            yield {"type": "complete", **run_result}

        with (
            patch.object(agent, "get_messages", new=AsyncMock(return_value=[])),
            patch.object(agent, "stream_agent", new=fake_stream_agent),
            patch.object(agent, "reflect", new=AsyncMock(return_value={"sufficient": True, "missing": ""})),
            patch.object(agent, "list_available_models", new=AsyncMock()) as list_models,
            patch.object(agent, "save_message", new=AsyncMock()),
        ):
            events = [event async for event in agent.stream_chat_with_agent(question, session_id=1)]

        self.assertEqual(len(events), 1)
        self.assertFalse(any("Available AI Grid models:" in event for event in events))
        self.assertEqual(len(stream_calls), 1)
        list_models.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
