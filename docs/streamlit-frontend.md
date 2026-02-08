# Streamlit Frontend for Azure Search OpenAI Demo

This directory contains the Streamlit-based frontend for the Azure Search OpenAI Demo application, which replaces the previous React/TypeScript frontend.

## Overview

The Streamlit frontend provides a Python-based web interface for interacting with the Azure OpenAI chat application. It communicates with the existing Quart backend via HTTP APIs.

## Architecture

```
┌─────────────────────┐      HTTP/REST       ┌─────────────────────┐
│                     │  ◄─────────────────► │                     │
│  Streamlit Frontend │                      │   Quart Backend     │
│  (streamlit_app.py) │                      │   (app/backend/)    │
│                     │                      │                     │
│  Port: 8501         │                      │   Port: 50505       │
└─────────────────────┘                      └─────────────────────┘
```

## Features

### Chat Interface
- Multi-turn conversation with message history
- Streaming responses with real-time updates
- User and assistant message display
- Support for follow-up questions
- Citation display with source references
- Thought process visualization

### Settings Panel
Located in the sidebar, includes:
- **Model Settings**: Temperature control
- **Retrieval Settings**: 
  - Retrieve count
  - Retrieval mode (hybrid, vectors, text)
  - Semantic ranker toggle
  - Query rewriting toggle
  - Semantic captions toggle
- **Response Settings**: Follow-up question suggestions
- **Advanced Settings**:
  - Text/image source toggles
  - Text/image embedding search toggles
  - Agentic knowledge base toggle
  - Reasoning effort selection

### Session Management
- Clear chat button to reset conversation
- Session state persistence during interaction
- Configuration caching

## Getting Started

### Prerequisites
- Python 3.10 or later
- Virtual environment set up with requirements installed

### Running the Application

#### Using the Start Script (Recommended)

**Linux/Mac:**
```bash
cd app
./start-streamlit.sh
```

**Windows:**
```powershell
cd app
.\start-streamlit.ps1
```

The scripts will:
1. Create/activate a Python virtual environment
2. Install all dependencies
3. Start the Quart backend on port 50505
4. Start the Streamlit frontend on port 8501
5. Open your browser to http://localhost:8501

#### Manual Start

If you prefer to run the components separately:

**Terminal 1 - Backend:**
```bash
cd app/backend
python -m quart --app main:app run --port 50505 --host localhost --reload
```

**Terminal 2 - Frontend:**
```bash
cd app
BACKEND_URL=http://localhost:50505 streamlit run streamlit_app.py --server.port 8501 --server.address localhost
```

### Environment Variables

- `BACKEND_URL`: URL of the Quart backend (default: `http://localhost:50505`)
- All Azure service configuration variables remain the same as the original application

## File Structure

```
app/
├── streamlit_app.py          # Main Streamlit application
├── start-streamlit.sh        # Start script for Linux/Mac
├── start-streamlit.ps1       # Start script for Windows
└── backend/                  # Quart backend (unchanged)
    ├── app.py
    ├── main.py
    └── ...
```

## Development

### Adding New Features

To add new features to the Streamlit frontend:

1. **Add UI components** in `streamlit_app.py`
2. **Update session state** in `initialize_session_state()`
3. **Add settings** in `render_settings_sidebar()`
4. **Update context** in `build_context()` to pass settings to backend

### Debugging

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

View Streamlit logs in the terminal where you started the application.

### Hot Reload

Streamlit automatically reloads when you save changes to `streamlit_app.py`. The backend also reloads when using `--reload` flag with Quart.

## API Integration

The Streamlit frontend communicates with the backend using the following endpoints:

- `GET /config` - Fetch application configuration
- `POST /chat` - Send non-streaming chat messages
- `POST /chat/stream` - Send streaming chat messages (NDJSON)
- `POST /speech` - Text-to-speech conversion
- `POST /upload` - File upload
- `POST /delete_uploaded` - Delete uploaded files
- `GET /list_uploaded` - List uploaded files
- `GET /content/{path}` - Retrieve content files

## Migration from React

The Streamlit frontend provides equivalent functionality to the React frontend:

| React Component | Streamlit Equivalent |
|----------------|---------------------|
| Chat.tsx | `render_message()` |
| Settings Component | `render_settings_sidebar()` |
| AnalysisPanel | Citations/thoughts in `render_message()` |
| QuestionInput | `st.chat_input()` |
| Answer Component | Assistant message display |

## Troubleshooting

### Backend Connection Issues
- Ensure the backend is running on port 50505
- Check `BACKEND_URL` environment variable
- Verify no firewall blocking localhost connections

### Streamlit Not Loading
- Clear Streamlit cache: `streamlit cache clear`
- Check for port conflicts on 8501
- Verify all dependencies are installed

### Missing Configuration Options
- Ensure the backend `/config` endpoint is returning proper values
- Check backend environment variables are set correctly

## Production Deployment

For production deployment:

1. Set `BACKEND_URL` to your production backend URL
2. Configure authentication (currently handled by backend)
3. Set appropriate Streamlit server configuration
4. Use a production ASGI server for the backend (already configured)

## Performance Considerations

- Streamlit rerunss the entire script on each interaction
- Session state is used to persist data between reruns
- Async operations use `asyncio.run_until_complete()` for compatibility
- Consider caching expensive operations with `@st.cache_data` or `@st.cache_resource`

## Security

- All authentication is handled by the backend
- No sensitive credentials are stored in the frontend
- API calls include proper headers and authentication tokens
- CORS is configured in the backend

## Future Enhancements

Potential improvements:
- [ ] Add file upload UI in Streamlit
- [ ] Implement chat history management UI
- [ ] Add authentication UI elements
- [ ] Support for multiple conversation threads
- [ ] Export conversation history
- [ ] Dark/light theme toggle
- [ ] Internationalization (i18n) support
- [ ] Mobile-responsive design improvements

## Support

For issues or questions:
- Check the main project README
- Review backend logs for API errors
- Check Streamlit documentation: https://docs.streamlit.io
