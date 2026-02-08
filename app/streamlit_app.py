"""
Streamlit frontend for Azure Search OpenAI Demo.
This replaces the React/TypeScript frontend.
"""

import asyncio
import json
import os
from typing import Any

import aiohttp
import streamlit as st

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:50505")


# Helper functions
async def fetch_config():
    """Fetch application configuration from backend."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BACKEND_URL}/config") as response:
            if response.status == 200:
                return await response.json()
            return {}


async def send_chat_message(messages: list[dict], context: dict, session_state: Any, stream: bool = True):
    """Send chat message to backend."""
    async with aiohttp.ClientSession() as session:
        url = f"{BACKEND_URL}/chat/stream" if stream else f"{BACKEND_URL}/chat"
        payload = {
            "messages": messages,
            "context": context,
            "session_state": session_state
        }
        
        if stream:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    async for line in response.content:
                        if line:
                            try:
                                yield json.loads(line.decode('utf-8'))
                            except json.JSONDecodeError:
                                continue
        else:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    yield result
                else:
                    yield {"error": f"Error: {response.status}"}


def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "config" not in st.session_state:
        # Run async function in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        config = loop.run_until_complete(fetch_config())
        st.session_state.config = config
        loop.close()
    
    # Chat settings
    if "temperature" not in st.session_state:
        st.session_state.temperature = 0.3
    if "retrieve_count" not in st.session_state:
        st.session_state.retrieve_count = 3
    if "retrieval_mode" not in st.session_state:
        st.session_state.retrieval_mode = "hybrid"
    if "use_semantic_ranker" not in st.session_state:
        st.session_state.use_semantic_ranker = True
    if "use_query_rewriting" not in st.session_state:
        st.session_state.use_query_rewriting = False
    if "use_semantic_captions" not in st.session_state:
        st.session_state.use_semantic_captions = False
    if "suggest_followup_questions" not in st.session_state:
        st.session_state.suggest_followup_questions = False
    if "send_text_sources" not in st.session_state:
        st.session_state.send_text_sources = st.session_state.config.get("sendTextSources", True)
    if "send_image_sources" not in st.session_state:
        st.session_state.send_image_sources = st.session_state.config.get("sendImageSources", False)
    if "search_text_embeddings" not in st.session_state:
        st.session_state.search_text_embeddings = st.session_state.config.get("searchTextEmbeddings", True)
    if "search_image_embeddings" not in st.session_state:
        st.session_state.search_image_embeddings = st.session_state.config.get("searchImageEmbeddings", False)
    if "use_agentic_knowledgebase" not in st.session_state:
        st.session_state.use_agentic_knowledgebase = False
    if "reasoning_effort" not in st.session_state:
        st.session_state.reasoning_effort = st.session_state.config.get("defaultReasoningEffort", "")
    if "retrieval_reasoning_effort" not in st.session_state:
        st.session_state.retrieval_reasoning_effort = st.session_state.config.get("defaultRetrievalReasoningEffort", "minimal")


def render_settings_sidebar():
    """Render settings in sidebar."""
    with st.sidebar:
        st.header("⚙️ Settings")
        
        config = st.session_state.config
        
        # Basic settings
        st.subheader("Model Settings")
        st.session_state.temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state.temperature,
            step=0.1,
            help="Controls randomness in responses"
        )
        
        # Retrieval settings
        st.subheader("Retrieval Settings")
        st.session_state.retrieve_count = st.number_input(
            "Retrieve Count",
            min_value=1,
            max_value=50,
            value=st.session_state.retrieve_count,
            help="Number of documents to retrieve"
        )
        
        if config.get("showVectorOption", False):
            st.session_state.retrieval_mode = st.selectbox(
                "Retrieval Mode",
                options=["hybrid", "vectors", "text"],
                index=["hybrid", "vectors", "text"].index(st.session_state.retrieval_mode),
                help="How to retrieve documents"
            )
        
        if config.get("showSemanticRankerOption", False):
            st.session_state.use_semantic_ranker = st.checkbox(
                "Use Semantic Ranker",
                value=st.session_state.use_semantic_ranker,
                help="Use semantic ranking for better results"
            )
        
        if config.get("showQueryRewritingOption", False):
            st.session_state.use_query_rewriting = st.checkbox(
                "Query Rewriting",
                value=st.session_state.use_query_rewriting,
                help="Rewrite queries for better search"
            )
        
        st.session_state.use_semantic_captions = st.checkbox(
            "Semantic Captions",
            value=st.session_state.use_semantic_captions,
            help="Generate semantic captions"
        )
        
        # Response settings
        st.subheader("Response Settings")
        st.session_state.suggest_followup_questions = st.checkbox(
            "Suggest Follow-up Questions",
            value=st.session_state.suggest_followup_questions,
            help="Generate follow-up question suggestions"
        )
        
        # Advanced settings
        with st.expander("Advanced Settings"):
            st.session_state.send_text_sources = st.checkbox(
                "Send Text Sources",
                value=st.session_state.send_text_sources
            )
            st.session_state.send_image_sources = st.checkbox(
                "Send Image Sources",
                value=st.session_state.send_image_sources
            )
            st.session_state.search_text_embeddings = st.checkbox(
                "Search Text Embeddings",
                value=st.session_state.search_text_embeddings
            )
            st.session_state.search_image_embeddings = st.checkbox(
                "Search Image Embeddings",
                value=st.session_state.search_image_embeddings
            )
            
            if config.get("showAgenticRetrievalOption", False):
                st.session_state.use_agentic_knowledgebase = st.checkbox(
                    "Use Agentic Knowledge Base",
                    value=st.session_state.use_agentic_knowledgebase
                )
            
            if config.get("showReasoningEffortOption", False):
                reasoning_options = ["", "low", "medium", "high"]
                current_idx = reasoning_options.index(st.session_state.reasoning_effort) if st.session_state.reasoning_effort in reasoning_options else 0
                st.session_state.reasoning_effort = st.selectbox(
                    "Reasoning Effort",
                    options=reasoning_options,
                    index=current_idx
                )
        
        # Clear chat button
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()


def render_message(message: dict[str, Any]):
    """Render a chat message."""
    role = message.get("role", "user")
    content = message.get("content", "")
    
    if role == "user":
        with st.chat_message("user"):
            st.markdown(content)
    else:
        with st.chat_message("assistant"):
            st.markdown(content)
            
            # Render citations if available
            if "context" in message and message["context"]:
                context = message["context"]
                
                # Show data points/citations
                if "data_points" in context:
                    data_points = context["data_points"]
                    citations = data_points.get("citations", [])
                    
                    if citations:
                        with st.expander("📚 Sources"):
                            for i, citation in enumerate(citations, 1):
                                st.markdown(f"{i}. {citation}")
                
                # Show follow-up questions
                if "followup_questions" in context and context["followup_questions"]:
                    with st.expander("💡 Follow-up Questions"):
                        for question in context["followup_questions"]:
                            if st.button(question, key=f"followup_{question}"):
                                # Add follow-up question as new user message
                                st.session_state.messages.append({
                                    "role": "user",
                                    "content": question
                                })
                                st.rerun()
                
                # Show thought process
                if "thoughts" in context and context["thoughts"]:
                    with st.expander("🤔 Thought Process"):
                        for thought in context["thoughts"]:
                            st.markdown(f"**{thought.get('title', 'Thought')}**: {thought.get('description', '')}")


def build_context() -> dict[str, Any]:
    """Build context object from current settings."""
    return {
        "overrides": {
            "temperature": st.session_state.temperature,
            "top": st.session_state.retrieve_count,
            "retrieval_mode": st.session_state.retrieval_mode,
            "semantic_ranker": st.session_state.use_semantic_ranker,
            "semantic_captions": st.session_state.use_semantic_captions,
            "query_rewriting": st.session_state.use_query_rewriting,
            "reasoning_effort": st.session_state.reasoning_effort,
            "suggest_followup_questions": st.session_state.suggest_followup_questions,
            "send_text_sources": st.session_state.send_text_sources,
            "send_image_sources": st.session_state.send_image_sources,
            "search_text_embeddings": st.session_state.search_text_embeddings,
            "search_image_embeddings": st.session_state.search_image_embeddings,
            "use_agentic_knowledgebase": st.session_state.use_agentic_knowledgebase,
            "retrieval_reasoning_effort": st.session_state.retrieval_reasoning_effort,
            "language": "en",
        }
    }


async def process_chat_stream(messages: list[dict], context: dict):
    """Process streaming chat response."""
    response_placeholder = st.empty()
    full_response = ""
    response_context = None
    
    async for chunk in send_chat_message(messages, context, None, stream=True):
        if "delta" in chunk and chunk["delta"]:
            delta_content = chunk["delta"].get("content", "")
            full_response += delta_content
            response_placeholder.markdown(full_response + "▌")
        
        if "context" in chunk:
            response_context = chunk["context"]
    
    response_placeholder.markdown(full_response)
    
    # Store complete message
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response,
        "context": response_context
    })


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Azure Search OpenAI Demo",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    initialize_session_state()
    
    # Render sidebar with settings
    render_settings_sidebar()
    
    # Main chat interface
    st.title("💬 Azure Search OpenAI Chat")
    st.markdown("Chat with your data using Azure OpenAI and Azure AI Search")
    
    # Display chat history
    for message in st.session_state.messages:
        render_message(message)
    
    # Chat input
    if prompt := st.chat_input("Ask a question about your data..."):
        # Add user message to chat
        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Display assistant response with streaming
        with st.chat_message("assistant"):
            # Prepare messages for API
            api_messages = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in st.session_state.messages
            ]
            
            # Build context
            context = build_context()
            
            # Process streaming response
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(process_chat_stream(api_messages, context))
            finally:
                loop.close()
            
            # Rerun to display the complete message with citations
            st.rerun()
    
    # Footer
    st.markdown("---")
    st.markdown("🔒 Powered by Azure OpenAI and Azure AI Search")


if __name__ == "__main__":
    main()
