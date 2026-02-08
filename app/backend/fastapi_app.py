"""
FastAPI backend application for Azure Search OpenAI Demo.
This replaces the Quart-based app.py with FastAPI.
"""

import dataclasses
import io
import json
import logging
import mimetypes
import os
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, cast

from azure.cognitiveservices.speech import (
    ResultReason,
    SpeechConfig,
    SpeechSynthesisOutputFormat,
    SpeechSynthesisResult,
    SpeechSynthesizer,
)
from azure.identity.aio import (
    AzureDeveloperCliCredential,
    ManagedIdentityCredential,
    get_bearer_token_provider,
)
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.search.documents.knowledgebases.aio import KnowledgeBaseRetrievalClient
from fastapi import FastAPI, HTTPException, Request, Depends, UploadFile, File as FastAPIFile
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from pydantic import BaseModel

from approaches.approach import Approach
from approaches.chatreadretrieveread import ChatReadRetrieveReadApproach
from approaches.promptmanager import PromptManager
from chat_history.cosmosdb import chat_history_cosmosdb_bp
from config import (
    CONFIG_AGENTIC_KNOWLEDGEBASE_ENABLED,
    CONFIG_AUTH_CLIENT,
    CONFIG_CHAT_APPROACH,
    CONFIG_CHAT_HISTORY_BROWSER_ENABLED,
    CONFIG_CHAT_HISTORY_COSMOS_ENABLED,
    CONFIG_CREDENTIAL,
    CONFIG_DEFAULT_REASONING_EFFORT,
    CONFIG_DEFAULT_RETRIEVAL_REASONING_EFFORT,
    CONFIG_GLOBAL_BLOB_MANAGER,
    CONFIG_INGESTER,
    CONFIG_KNOWLEDGEBASE_CLIENT,
    CONFIG_KNOWLEDGEBASE_CLIENT_WITH_SHAREPOINT,
    CONFIG_KNOWLEDGEBASE_CLIENT_WITH_WEB,
    CONFIG_KNOWLEDGEBASE_CLIENT_WITH_WEB_AND_SHAREPOINT,
    CONFIG_LANGUAGE_PICKER_ENABLED,
    CONFIG_MULTIMODAL_ENABLED,
    CONFIG_OPENAI_CLIENT,
    CONFIG_QUERY_REWRITING_ENABLED,
    CONFIG_RAG_SEARCH_IMAGE_EMBEDDINGS,
    CONFIG_RAG_SEARCH_TEXT_EMBEDDINGS,
    CONFIG_RAG_SEND_IMAGE_SOURCES,
    CONFIG_RAG_SEND_TEXT_SOURCES,
    CONFIG_REASONING_EFFORT_ENABLED,
    CONFIG_SEARCH_CLIENT,
    CONFIG_SEMANTIC_RANKER_DEPLOYED,
    CONFIG_SHAREPOINT_SOURCE_ENABLED,
    CONFIG_SPEECH_INPUT_ENABLED,
    CONFIG_SPEECH_OUTPUT_AZURE_ENABLED,
    CONFIG_SPEECH_OUTPUT_BROWSER_ENABLED,
    CONFIG_SPEECH_SERVICE_ID,
    CONFIG_SPEECH_SERVICE_LOCATION,
    CONFIG_SPEECH_SERVICE_TOKEN,
    CONFIG_SPEECH_SERVICE_VOICE,
    CONFIG_STREAMING_ENABLED,
    CONFIG_USER_BLOB_MANAGER,
    CONFIG_USER_UPLOAD_ENABLED,
    CONFIG_VECTOR_SEARCH_ENABLED,
    CONFIG_WEB_SOURCE_ENABLED,
)
from core.authentication import AuthenticationHelper
from core.sessionhelper import create_session_id
from decorators import authenticated, authenticated_path
from error import error_dict, error_response
from prepdocs import (
    OpenAIHost,
    setup_embeddings_service,
    setup_file_processors,
    setup_image_embeddings_service,
    setup_openai_client,
    setup_search_info,
)
from prepdocslib.blobmanager import AdlsBlobManager, BlobManager
from prepdocslib.embeddings import ImageEmbeddings
from prepdocslib.filestrategy import UploadUserFileStrategy
from prepdocslib.listfilestrategy import File

# Fix Windows registry issue with mimetypes
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

# Request/Response Models
class ChatRequest(BaseModel):
    messages: list[dict[str, Any]]
    context: dict[str, Any] = {}
    session_state: Any = None


class SpeechRequest(BaseModel):
    text: str


class DeleteFileRequest(BaseModel):
    filename: str


# Global app state (similar to Quart's current_app.config)
app_state: dict[str, Any] = {}


# Helper to get auth claims (placeholder for actual implementation)
async def get_auth_claims(request: Request) -> dict[str, Any]:
    """Extract authentication claims from request."""
    # This is a simplified version - actual implementation depends on auth setup
    return {}


# Helper to format streaming responses
async def format_as_ndjson(response: AsyncGenerator) -> AsyncGenerator[str, None]:
    """Format async generator as newline-delimited JSON."""
    try:
        async for event in response:
            yield json.dumps(event, ensure_ascii=False) + "\n"
    except Exception as error:
        logging.exception("Exception while generating response stream: %s", error)
        yield json.dumps(error_dict(error))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Azure Search OpenAI Demo")

    # Configure CORS
    if allowed_origin := os.getenv("ALLOWED_ORIGIN"):
        allowed_origins = allowed_origin.split(";")
        if len(allowed_origins) > 0:
            logging.info("CORS enabled for %s", allowed_origins)
            app.add_middleware(
                CORSMiddleware,
                allow_origins=allowed_origins,
                allow_methods=["GET", "POST"],
                allow_headers=["*"],
            )

    # Configure Application Insights if enabled
    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        logging.info("APPLICATIONINSIGHTS_CONNECTION_STRING is set, enabling Azure Monitor")
        configure_azure_monitor(
            instrumentation_options={
                "django": {"enabled": False},
                "psycopg2": {"enabled": False},
                "fastapi": {"enabled": True},
            }
        )
        AioHttpClientInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()
        OpenAIInstrumentor().instrument()
        FastAPIInstrumentor.instrument_app(app)

    # Configure logging
    logging.basicConfig(level=logging.WARNING)
    app_level = os.getenv("APP_LOG_LEVEL", "INFO")
    logging.getLogger("app").setLevel(app_level)
    logging.getLogger("scripts").setLevel(app_level)

    # API Routes
    @app.post("/chat")
    async def chat(request: ChatRequest, auth_claims: dict[str, Any] = Depends(get_auth_claims)):
        """Handle chat requests."""
        context = request.context.copy()
        context["auth_claims"] = auth_claims
        try:
            approach: Approach = cast(Approach, app_state[CONFIG_CHAT_APPROACH])
            session_state = request.session_state
            if session_state is None:
                session_state = create_session_id(
                    app_state[CONFIG_CHAT_HISTORY_COSMOS_ENABLED],
                    app_state[CONFIG_CHAT_HISTORY_BROWSER_ENABLED],
                )
            result = await approach.run(
                request.messages,
                context=context,
                session_state=session_state,
            )
            return JSONResponse(content=result)
        except Exception as error:
            logging.exception("Error in /chat: %s", error)
            raise HTTPException(status_code=500, detail=str(error))

    @app.post("/chat/stream")
    async def chat_stream(request: ChatRequest, auth_claims: dict[str, Any] = Depends(get_auth_claims)):
        """Handle streaming chat requests."""
        context = request.context.copy()
        context["auth_claims"] = auth_claims
        try:
            approach: Approach = cast(Approach, app_state[CONFIG_CHAT_APPROACH])
            session_state = request.session_state
            if session_state is None:
                session_state = create_session_id(
                    app_state[CONFIG_CHAT_HISTORY_COSMOS_ENABLED],
                    app_state[CONFIG_CHAT_HISTORY_BROWSER_ENABLED],
                )
            result = await approach.run_stream(
                request.messages,
                context=context,
                session_state=session_state,
            )
            return StreamingResponse(
                format_as_ndjson(result),
                media_type="application/json-lines"
            )
        except Exception as error:
            logging.exception("Error in /chat/stream: %s", error)
            raise HTTPException(status_code=500, detail=str(error))

    @app.get("/config")
    async def config():
        """Return application configuration."""
        return JSONResponse(content={
            "showMultimodalOptions": app_state.get(CONFIG_MULTIMODAL_ENABLED, False),
            "showSemanticRankerOption": app_state.get(CONFIG_SEMANTIC_RANKER_DEPLOYED, False),
            "showQueryRewritingOption": app_state.get(CONFIG_QUERY_REWRITING_ENABLED, False),
            "showReasoningEffortOption": app_state.get(CONFIG_REASONING_EFFORT_ENABLED, False),
            "showVectorOption": app_state.get(CONFIG_VECTOR_SEARCH_ENABLED, False),
            "showUserUpload": app_state.get(CONFIG_USER_UPLOAD_ENABLED, False),
            "showLanguagePicker": app_state.get(CONFIG_LANGUAGE_PICKER_ENABLED, False),
            "showSpeechInput": app_state.get(CONFIG_SPEECH_INPUT_ENABLED, False),
            "showSpeechOutputBrowser": app_state.get(CONFIG_SPEECH_OUTPUT_BROWSER_ENABLED, False),
            "showSpeechOutputAzure": app_state.get(CONFIG_SPEECH_OUTPUT_AZURE_ENABLED, False),
            "showChatHistoryBrowser": app_state.get(CONFIG_CHAT_HISTORY_BROWSER_ENABLED, False),
            "showChatHistoryCosmos": app_state.get(CONFIG_CHAT_HISTORY_COSMOS_ENABLED, False),
            "showAgenticRetrievalOption": app_state.get(CONFIG_AGENTIC_KNOWLEDGEBASE_ENABLED, False),
            "sendTextSources": app_state.get(CONFIG_RAG_SEND_TEXT_SOURCES, False),
            "sendImageSources": app_state.get(CONFIG_RAG_SEND_IMAGE_SOURCES, False),
            "searchTextEmbeddings": app_state.get(CONFIG_RAG_SEARCH_TEXT_EMBEDDINGS, False),
            "searchImageEmbeddings": app_state.get(CONFIG_RAG_SEARCH_IMAGE_EMBEDDINGS, False),
            "webSourceSupported": app_state.get(CONFIG_WEB_SOURCE_ENABLED, False),
            "sharePointSourceSupported": app_state.get(CONFIG_SHAREPOINT_SOURCE_ENABLED, False),
            "streamingEnabled": app_state.get(CONFIG_STREAMING_ENABLED, False),
            "defaultReasoningEffort": app_state.get(CONFIG_DEFAULT_REASONING_EFFORT, ""),
            "defaultRetrievalReasoningEffort": app_state.get(CONFIG_DEFAULT_RETRIEVAL_REASONING_EFFORT, "minimal"),
        })

    @app.get("/auth_setup")
    async def auth_setup():
        """Return authentication setup information."""
        auth_helper: AuthenticationHelper = app_state[CONFIG_AUTH_CLIENT]
        return JSONResponse(content=auth_helper.get_auth_setup_for_client())

    @app.post("/speech")
    async def speech(request: SpeechRequest):
        """Convert text to speech."""
        speech_token = app_state.get(CONFIG_SPEECH_SERVICE_TOKEN)
        if speech_token is None or speech_token.expires_on < time.time() + 60:
            speech_token = await app_state[CONFIG_CREDENTIAL].get_token(
                "https://cognitiveservices.azure.com/.default"
            )
            app_state[CONFIG_SPEECH_SERVICE_TOKEN] = speech_token

        try:
            auth_token = (
                "aad#"
                + app_state[CONFIG_SPEECH_SERVICE_ID]
                + "#"
                + app_state[CONFIG_SPEECH_SERVICE_TOKEN].token
            )
            speech_config = SpeechConfig(
                auth_token=auth_token,
                region=app_state[CONFIG_SPEECH_SERVICE_LOCATION]
            )
            speech_config.speech_synthesis_voice_name = app_state[CONFIG_SPEECH_SERVICE_VOICE]
            speech_config.set_speech_synthesis_output_format(
                SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
            )
            synthesizer = SpeechSynthesizer(speech_config=speech_config, audio_config=None)
            result: SpeechSynthesisResult = synthesizer.speak_text_async(request.text).get()
            
            if result.reason == ResultReason.SynthesizingAudioCompleted:
                return StreamingResponse(
                    io.BytesIO(result.audio_data),
                    media_type="audio/mp3"
                )
            elif result.reason == ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                logging.error(
                    "Speech synthesis canceled: %s %s",
                    cancellation_details.reason,
                    cancellation_details.error_details
                )
                raise HTTPException(status_code=500, detail="Speech synthesis canceled")
            else:
                logging.error("Unexpected result reason: %s", result.reason)
                raise HTTPException(status_code=500, detail="Speech synthesis failed")
        except Exception as e:
            logging.exception("Exception in /speech")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/upload")
    async def upload(
        file: UploadFile = FastAPIFile(...),
        auth_claims: dict[str, Any] = Depends(get_auth_claims)
    ):
        """Upload a file."""
        try:
            user_oid = auth_claims.get("oid", "anonymous")
            adls_manager: AdlsBlobManager = app_state[CONFIG_USER_BLOB_MANAGER]
            file_url = await adls_manager.upload_blob(file.file, file.filename, user_oid)
            ingester: UploadUserFileStrategy = app_state[CONFIG_INGESTER]
            await ingester.add_file(
                File(content=file.file, url=file_url, acls={"oids": [user_oid]}),
                user_oid=user_oid
            )
            return JSONResponse(content={"message": "File uploaded successfully"})
        except Exception as error:
            logging.exception("Error uploading file: %s", error)
            raise HTTPException(status_code=500, detail="Error uploading file")

    @app.post("/delete_uploaded")
    async def delete_uploaded(
        request: DeleteFileRequest,
        auth_claims: dict[str, Any] = Depends(get_auth_claims)
    ):
        """Delete an uploaded file."""
        user_oid = auth_claims.get("oid", "anonymous")
        adls_manager: AdlsBlobManager = app_state[CONFIG_USER_BLOB_MANAGER]
        await adls_manager.remove_blob(request.filename, user_oid)
        ingester: UploadUserFileStrategy = app_state[CONFIG_INGESTER]
        await ingester.remove_file(request.filename, user_oid)
        return JSONResponse(content={"message": f"File {request.filename} deleted successfully"})

    @app.get("/list_uploaded")
    async def list_uploaded(auth_claims: dict[str, Any] = Depends(get_auth_claims)):
        """List uploaded files for the current user."""
        user_oid = auth_claims.get("oid", "anonymous")
        adls_manager: AdlsBlobManager = app_state[CONFIG_USER_BLOB_MANAGER]
        files = await adls_manager.list_blobs(user_oid)
        return JSONResponse(content=files)

    @app.get("/content/{path:path}")
    async def content_file(path: str, auth_claims: dict[str, Any] = Depends(get_auth_claims)):
        """Serve content files from blob storage."""
        # Remove page number from path if present
        if path.find("#page=") > 0:
            path_parts = path.rsplit("#page=", 1)
            path = path_parts[0]

        # Get blob manager and fetch content
        blob_manager: BlobManager = app_state[CONFIG_GLOBAL_BLOB_MANAGER]
        try:
            blob = await blob_manager.download_blob(path)
            # Return the file content
            return StreamingResponse(
                io.BytesIO(blob.readall()),
                media_type=mimetypes.guess_type(path)[0] or "application/octet-stream"
            )
        except Exception as e:
            logging.exception("Error serving content file: %s", e)
            raise HTTPException(status_code=404, detail="File not found")

    return app


# Startup and shutdown events
async def startup_event():
    """Initialize application state on startup."""
    # This is a placeholder - actual initialization should mirror setup_clients from app.py
    logging.info("Application starting up...")
    # Initialize all the Azure clients, OpenAI clients, etc.
    # This would need to be copied from the original app.py setup_clients function


async def shutdown_event():
    """Cleanup on shutdown."""
    logging.info("Application shutting down...")
    if CONFIG_SEARCH_CLIENT in app_state:
        await app_state[CONFIG_SEARCH_CLIENT].close()
    if CONFIG_GLOBAL_BLOB_MANAGER in app_state:
        await app_state[CONFIG_GLOBAL_BLOB_MANAGER].close_clients()
    if user_blob_manager := app_state.get(CONFIG_USER_BLOB_MANAGER):
        await user_blob_manager.close_clients()
    if CONFIG_CREDENTIAL in app_state:
        await app_state[CONFIG_CREDENTIAL].close()


# Create the app instance
app = create_app()
app.add_event_handler("startup", startup_event)
app.add_event_handler("shutdown", shutdown_event)
