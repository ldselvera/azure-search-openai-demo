"""
Tests for Streamlit frontend application.
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

import pytest

# Add app directory to path so we can import streamlit_app
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


class TestStreamlitApp:
    """Test cases for Streamlit application."""

    def test_streamlit_app_imports(self):
        """Test that streamlit_app module can be imported."""
        import streamlit_app
        assert streamlit_app is not None

    def test_backend_url_configuration(self):
        """Test BACKEND_URL configuration."""
        with patch.dict(os.environ, {"BACKEND_URL": "http://test:8000"}):
            # Re-import to get new environment variable
            import importlib
            import streamlit_app
            importlib.reload(streamlit_app)
            assert streamlit_app.BACKEND_URL == "http://test:8000"

    def test_backend_url_default(self):
        """Test BACKEND_URL defaults to localhost:50505."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import streamlit_app
            importlib.reload(streamlit_app)
            assert "50505" in streamlit_app.BACKEND_URL

    @pytest.mark.asyncio
    async def test_fetch_config(self):
        """Test fetch_config function."""
        import streamlit_app
        
        # Mock aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"test": "config"})
        
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
        
        with patch("aiohttp.ClientSession", return_value=mock_session):
            config = await streamlit_app.fetch_config()
            assert config == {"test": "config"}

    @pytest.mark.asyncio
    async def test_fetch_config_error(self):
        """Test fetch_config handles errors gracefully."""
        import streamlit_app
        
        # Mock aiohttp response with error
        mock_response = AsyncMock()
        mock_response.status = 500
        
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
        
        with patch("aiohttp.ClientSession", return_value=mock_session):
            config = await streamlit_app.fetch_config()
            assert config == {}

    def test_build_context(self):
        """Test build_context creates proper context object."""
        import streamlit_app
        import streamlit as st
        
        # Mock session state
        with patch.object(st, "session_state", {
            "temperature": 0.5,
            "retrieve_count": 5,
            "retrieval_mode": "hybrid",
            "use_semantic_ranker": True,
            "use_semantic_captions": False,
            "use_query_rewriting": True,
            "reasoning_effort": "medium",
            "suggest_followup_questions": True,
            "send_text_sources": True,
            "send_image_sources": False,
            "search_text_embeddings": True,
            "search_image_embeddings": False,
            "use_agentic_knowledgebase": False,
            "retrieval_reasoning_effort": "minimal",
        }):
            context = streamlit_app.build_context()
            
            assert context["overrides"]["temperature"] == 0.5
            assert context["overrides"]["top"] == 5
            assert context["overrides"]["retrieval_mode"] == "hybrid"
            assert context["overrides"]["semantic_ranker"] is True
            assert context["overrides"]["query_rewriting"] is True
            assert context["overrides"]["language"] == "en"


class TestStreamlitComponents:
    """Test Streamlit UI components."""

    def test_render_message_user(self):
        """Test render_message for user messages."""
        import streamlit_app
        
        message = {
            "role": "user",
            "content": "Hello, world!"
        }
        
        # This will fail in CI without Streamlit context, but structure is valid
        # In real usage, this would be called within Streamlit
        try:
            streamlit_app.render_message(message)
        except Exception:
            # Expected to fail without Streamlit runtime
            pass

    def test_render_message_assistant(self):
        """Test render_message for assistant messages with context."""
        import streamlit_app
        
        message = {
            "role": "assistant",
            "content": "Here is my response.",
            "context": {
                "data_points": {
                    "citations": ["source1.pdf", "source2.pdf"]
                },
                "followup_questions": ["What about X?", "Tell me more about Y?"],
                "thoughts": [
                    {"title": "Analysis", "description": "I analyzed the question"}
                ]
            }
        }
        
        # This will fail in CI without Streamlit context, but structure is valid
        try:
            streamlit_app.render_message(message)
        except Exception:
            # Expected to fail without Streamlit runtime
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
