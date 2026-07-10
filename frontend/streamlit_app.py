"""
Streamlit UI for CodeRAG - Chat with your GitHub repositories.

Features:
- Repository cloning and indexing
- Real-time chat with code-aware responses
- Source code references with GitHub permalinks
- Streaming responses
- Search capability
"""

import streamlit as st
import requests
import json
import time
from typing import List, Dict, Any
import os

# --- Configuration ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_BASE = f"{BACKEND_URL}/api"

# --- Session State Initialization ---
if "repo_url" not in st.session_state:
    st.session_state.repo_url = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if "is_streaming" not in st.session_state:
    st.session_state.is_streaming = False
if "current_response" not in st.session_state:
    st.session_state.current_response = ""
if "sources" not in st.session_state:
    st.session_state.sources = []
if "indexing_status" not in st.session_state:
    st.session_state.indexing_status = None

# --- Helper Functions ---
def get_repo_status(repo_url: str):
    """Get the indexing status of a repository."""
    try:
        resp = requests.get(f"{API_BASE}/repo/status/{repo_url}")
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        st.error(f"Error fetching repo status: {e}")
    return None

def clone_repo(repo_url: str, branch: str = "", force_reindex: bool = False):
    """Clone or update a repository and start indexing."""
    try:
        payload = {
            "repo_url": repo_url,
            "force_reindex": force_reindex
        }
        # Only send branch if user explicitly provided one
        if branch and branch.strip():
            payload["branch"] = branch.strip()
        resp = requests.post(f"{API_BASE}/repo/clone", json=payload)
        if resp.status_code == 200:
            return resp.json()
        else:
            st.error(f"Clone failed: {resp.text}")
    except Exception as e:
        st.error(f"Error cloning repo: {e}")
    return None

def send_chat_message(question: str, max_chunks: int = 15, stream: bool = True):
    """Send a chat message to the backend."""
    try:
        payload = {
            "repo_url": st.session_state.repo_url,
            "question": question,
            "max_chunks": max_chunks,
            "stream": stream
        }
        
        if stream:
            # Streaming response
            response = requests.post(
                f"{API_BASE}/chat/stream",
                json=payload,
                stream=True
            )
            
            if response.status_code == 200:
                full_answer = ""
                sources = []
                buffer = ""
                
                for chunk in response.iter_content(chunk_size=1, decode_unicode=True):
                    if not chunk:
                        continue
                    
                    if isinstance(chunk, bytes):
                        chunk = chunk.decode('utf-8')
                    
                    buffer += chunk
                    
                    # Try to find complete lines (ending with \n)
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        
                        if not line:
                            continue
                        
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if not data_str:
                                continue
                            
                            try:
                                msg = json.loads(data_str)
                                event_type = msg.get("event")
                                
                                if event_type == "token":
                                    token_text = msg.get("data", "")
                                    full_answer += token_text
                                    yield token_text
                                elif event_type == "sources":
                                    sources_data = msg.get("data", [])
                                    sources = sources_data
                                    yield {"sources": sources}
                                elif event_type == "done":
                                    yield {"done": True}
                                elif event_type == "error":
                                    error_data = msg.get("data", {})
                                    st.error(error_data.get("error", "Unknown error"))
                            except json.JSONDecodeError:
                                # Plain text fallback - treat as token
                                full_answer += data_str
                                yield data_str
            else:
                st.error(f"Streaming error: {response.text}")
        else:
            # Non-streaming response
            response = requests.post(f"{API_BASE}/chat", json=payload)
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Chat error: {response.text}")
    except Exception as e:
        st.error(f"Error sending chat message: {e}")

def search_code(query: str, top_k: int = 10):
    """Perform a direct code search."""
    try:
        payload = {
            "repo_url": st.session_state.repo_url,
            "query": query,
            "top_k": top_k
        }
        resp = requests.post(f"{API_BASE}/search", json=payload)
        if resp.status_code == 200:
            return resp.json()
        else:
            st.error(f"Search error: {resp.text}")
    except Exception as e:
        st.error(f"Error searching code: {e}")
    return []

# --- Streamlit UI ---
st.set_page_config(page_title="CodeRAG - Chat with GitHub Repos", layout="wide")
st.title("🤖 CodeRAG: Chat with GitHub Repositories")

# Sidebar for repo management
with st.sidebar:
    st.header("🔧 Repository Management")
    
    repo_url = st.text_input(
        "GitHub Repository URL",
        value=st.session_state.repo_url,
        placeholder="https://github.com/user/repo"
    )
    
    if repo_url != st.session_state.repo_url:
        st.session_state.repo_url = repo_url
        st.session_state.messages = []  # Reset chat when repo changes
        
    branch = st.text_input("Branch", value="", placeholder="Leave blank for default branch")
    force_reindex = st.checkbox("Force Re-index", value=False)
    
    if st.button("📥 Clone & Index"):
        if repo_url:
            with st.spinner("Cloning and indexing repository..."):
                result = clone_repo(repo_url, branch, force_reindex)
                if result:
                    st.success(f"Started indexing: {result.get('repo_name', 'Unknown')}")
                    st.session_state.indexing_status = result
        else:
            st.warning("Please enter a repository URL")
    
    # Show indexing status
    if st.session_state.indexing_status:
        st.subheader("Indexing Status")
        st.json(st.session_state.indexing_status)
    
    # List repos
    if st.button("📁 List Repositories"):
        try:
            resp = requests.get(f"{API_BASE}/repo/list")
            if resp.status_code == 200:
                repos = resp.json().get("repos", [])
                st.write("Available repositories:")
                for repo in repos:
                    st.code(repo)
            else:
                st.error("Failed to fetch repos")
        except Exception as e:
            st.error(f"Error: {e}")
    
    st.markdown("---")
    st.header("🔍 Search Code")
    search_query = st.text_input("Search query", placeholder="Find function X")
    if st.button("🔍 Search"):
        if search_query and st.session_state.repo_url:
            with st.spinner("Searching..."):
                results = search_code(search_query)
                if results:
                    st.subheader("Search Results")
                    for i, res in enumerate(results[:5]):  # Show top 5
                        meta = res.get("metadata", {})
                        st.markdown(f"**{i+1}. `{meta.get('symbol_name', 'Unknown')}`**")
                        st.caption(f"{meta.get('file_path', '')}:{meta.get('start_line', 0)}")
                        st.code(meta.get('snippet', '')[:200] + "...")
                        st.markdown(f"Score: {res.get('score', 0):.3f}")
                        st.divider()
        elif not st.session_state.repo_url:
            st.warning("Please select a repository first")

# Main chat area
if st.session_state.repo_url:
    st.subheader(f"💬 Chat with: {st.session_state.repo_url}")
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                st.markdown(message["content"])
                if "sources" in message:
                    st.markdown("**Sources:**")
                    for src in message["sources"]:
                        url = src.get("github_url", "")
                        file_path = src.get("file_path", "")
                        start_line = src.get("start_line", 0)
                        symbol_name = src.get("symbol_name", "")
                        st.markdown(f"- [{file_path}:{start_line}]({url}) - {symbol_name}")
            else:
                st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask a question about the code..."):
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Show assistant response
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            sources = []
            
            # Send message and stream response
            for chunk in send_chat_message(prompt, stream=True):
                if isinstance(chunk, dict):
                    if "sources" in chunk:
                        sources = chunk["sources"]
                    elif "done" in chunk:
                        break
                else:
                    full_response += chunk
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            
            # Show sources
            if sources:
                st.markdown("**Sources:**")
                for src in sources:
                    url = src.get("github_url", "")
                    file_path = src.get("file_path", "")
                    start_line = src.get("start_line", 0)
                    symbol_name = src.get("symbol_name", "")
                    st.markdown(f"- [{file_path}:{start_line}]({url}) - {symbol_name}")
            
            # Update session state
            st.session_state.messages.append({
                "role": "assistant",
                "content": full_response,
                "sources": sources
            })
else:
    st.info("Please enter a GitHub repository URL in the sidebar to start chatting.")

# Health check
st.markdown("---")
st.subheader("🏥 Service Health")
try:
    resp = requests.get(f"{API_BASE}/health")
    if resp.status_code == 200:
        health = resp.json()
        st.json(health)
    else:
        st.error("Failed to fetch health status")
except Exception as e:
    st.error(f"Health check error: {e}")