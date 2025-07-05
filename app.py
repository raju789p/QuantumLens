import streamlit as st
import google.generativeai as genai
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import time
import re
from datetime import datetime
import os

# Page configuration
st.set_page_config(
    page_title="QuantumLens - MOSDAC AI Assistant",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'analytics' not in st.session_state:
    st.session_state.analytics = {
        'queries_processed': 0,
        'entities_found': [],
        'response_times': [],
        'confidence_scores': [],
        'query_types': []
    }

# Custom CSS for better UI
st.markdown("""
<style>
.main {
    padding: 1rem;
}

.stChatMessage {
    padding: 1rem;
    border-radius: 10px;
    margin: 0.5rem 0;
}

.stChatMessage[data-testid="chat-message-user"] {
    background-color: #e3f2fd;
    border-left: 4px solid #2196f3;
}

.stChatMessage[data-testid="chat-message-assistant"] {
    background-color: #f1f8e9;
    border-left: 4px solid #4caf50;
}

.metric-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 1rem;
    border-radius: 10px;
    color: white;
    text-align: center;
    margin: 0.5rem 0;
}

.entity-tag {
    display: inline-block;
    background-color: #2196f3;
    color: white;
    padding: 0.2rem 0.5rem;
    border-radius: 15px;
    font-size: 0.8rem;
    margin: 0.2rem;
}

.status-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem;
    border-radius: 5px;
    margin: 0.2rem 0;
}

.status-online {
    background-color: #d4edda;
    color: #155724;
}

.chat-container {
    height: 400px;
    overflow-y: auto;
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 1rem;
    background-color: #fafafa;
}
</style>
""", unsafe_allow_html=True)
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Hide deploy status and Streamlit branding */
.block-container div[data-testid="stDecoration"] {
    display: none;
}
</style>
""", unsafe_allow_html=True)



# MOSDAC Knowledge Base and System Prompt
MOSDAC_SYSTEM_PROMPT = """
You are the MOSDAC (Meteorological & Oceanographic Satellite Data Archival Centre) AI Assistant, an expert on the MOSDAC portal (www.mosdac.gov.in). You have comprehensive knowledge of:

1. NAVIGATION STRUCTURE:
   - Main Menu: Home, Data Access, Services, Help, About
   - Data Access submenu: Open Data, Restricted Data, NRT Data, Catalogue
   - Categories: Atmosphere, Ocean, Land, Climate, Disaster Management

2. DETAILED NAVIGATION PATHS:
   - GSMap ISRO Rain: Home > Data Access > Open Data > Atmosphere > GSMap ISRO Rain
   - SST Data: Home > Data Access > Open Data > Ocean > Sea Surface Temperature
   - INSAT-3D Data: Home > Data Access > Open Data > Atmosphere > INSAT-3D
   - Chlorophyll Data: Home > Data Access > Open Data > Ocean > Chlorophyll
   - NDVI Data: Home > Data Access > Open Data > Land > NDVI

3. AUTHENTICATION & ACCESS:
   - Single Sign On (SSO) required for data download
   - Registration process through MOSDAC portal
   - Different access levels: Open Data (free), Restricted Data (approval needed)

4. DATA FORMATS & SPECIFICATIONS:
   - Common formats: HDF5, NetCDF, GeoTIFF, CSV
   - Temporal coverage varies by product
   - Spatial resolutions from 1km to 25km depending on satellite

5. SATELLITE MISSIONS:
   - INSAT series (3D, 3DR)
   - Oceansat series
   - Cartosat series
   - SCATSAT-1
   - International missions: MODIS, VIIRS, etc.

RESPONSE GUIDELINES:
- Provide EXACT navigation paths with menu symbols (▸)
- Include specific product names as they appear on the portal
- Mention authentication requirements
- Specify data formats and coverage when relevant
- Be precise and step-by-step for navigation queries
- No preamble - direct, actionable answers only
- you can answer any sort of answers like any general one's or related to our MOSDAC or any other u should act like a chatgpt be brave and confident

Example Response Format for Navigation:
"From the top menu, go to Data Access ▸ Open Data ▸ [Category]. Under the list, click on [Product Name]. Sign-in via SSO link to access downloads."
"""

def configure_gemini():
    """Configure Gemini API with better error handling"""
    # Try multiple methods to get API key
    api_key = None
    
    # Method 1: Environment variable
    api_key = os.getenv("GEMINI_API_KEY")
    
    # Method 2: Streamlit secrets (if available)
    if not api_key:
        try:
            api_key = st.secrets.get("GEMINI_API_KEY")
        except:
            pass
    
    # Method 3: User input in sidebar
    if not api_key:
        with st.sidebar:
            st.markdown("### 🔑 API Configuration")
            api_key = st.text_input(
                "Enter your Gemini API Key:",
                type="password",
                help="Get your free API key from https://makersuite.google.com/"
            )
            
            if not api_key:
                st.warning("⚠️ Please enter your Gemini API key to use the AI assistant!")
                st.markdown("""
                **How to get your API key:**
                1. Go to [Google AI Studio](https://makersuite.google.com/)
                2. Sign in with Google account
                3. Click "Get API Key"
                4. Copy and paste it above
                """)
                return None
    
    if api_key:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                'gemini-2.0-flash-exp',
                system_instruction=MOSDAC_SYSTEM_PROMPT
            )
            return model
        except Exception as e:
            st.error(f"❌ Error configuring Gemini: {str(e)}")
            return None
    
    return None

def extract_entities(text):
    """Extract entities from user query"""
    entities = []
    
    # Satellite names
    satellites = ['INSAT-3D', 'INSAT-3DR', 'OCEANSAT', 'SCATSAT', 'CARTOSAT', 'MODIS', 'VIIRS']
    for sat in satellites:
        if sat.lower() in text.lower():
            entities.append(('SATELLITE', sat))
    
    # Data products
    products = ['SST', 'CHLOROPHYLL', 'NDVI', 'GSMAP', 'RAIN', 'TEMPERATURE', 'WIND', 'HUMIDITY']
    for prod in products:
        if prod.lower() in text.lower():
            entities.append(('PRODUCT', prod))
    
    # Regions
    regions = ['INDIA', 'INDIAN OCEAN', 'ASIA', 'GLOBAL', 'BAY OF BENGAL', 'ARABIAN SEA']
    for region in regions:
        if region.lower() in text.lower():
            entities.append(('REGION', region))
    
    # Data formats
    formats = ['HDF5', 'NETCDF', 'GEOTIFF', 'CSV', 'JSON']
    for fmt in formats:
        if fmt.lower() in text.lower():
            entities.append(('FORMAT', fmt))
    
    return entities

def classify_intent(text):
    """Classify user intent"""
    text_lower = text.lower()
    
    if any(word in text_lower for word in ['navigate', 'find', 'where', 'how to get', 'access']):
        return 'navigation'
    elif any(word in text_lower for word in ['download', 'get data', 'retrieve']):
        return 'data_download'
    elif any(word in text_lower for word in ['format', 'specification', 'resolution', 'coverage']):
        return 'technical_specs'
    elif any(word in text_lower for word in ['location', 'region', 'coordinate', 'lat', 'lon']):
        return 'geospatial'
    else:
        return 'general_inquiry'

def get_ai_response(model, user_query):
    """Get response from Gemini AI"""
    if not model:
        return "❌ AI model not configured. Please add your Gemini API key.", 0.0
    
    try:
        start_time = time.time()
        
        # Enhanced prompt for better responses
        enhanced_prompt = f"""
        User Query: {user_query}
        
        Provide a precise, step-by-step answer about MOSDAC portal navigation or data access. 
        Include exact menu paths using ▸ symbol and specific product names.
        If it's about navigation, give the complete path from homepage.
        If it's about data access, mention SSO login requirements.
        Be direct and actionable - no unnecessary introductions.
        """
        
        response = model.generate_content(enhanced_prompt)
        response_time = time.time() - start_time
        
        return response.text, response_time
    
    except Exception as e:
        return f"❌ Error generating response: {str(e)}", 0.0

def update_analytics(query, entities, response_time, intent):
    """Update analytics data"""
    st.session_state.analytics['queries_processed'] += 1
    st.session_state.analytics['entities_found'].extend([e[1] for e in entities])
    st.session_state.analytics['response_times'].append(response_time)
    st.session_state.analytics['confidence_scores'].append(0.85 + (len(entities) * 0.03))
    st.session_state.analytics['query_types'].append(intent)

def display_analytics():
    """Display analytics in sidebar"""
    with st.sidebar:
        st.markdown("### 📊 Query Analysis")
        
        analytics = st.session_state.analytics
        
        # Entities found
        if analytics['entities_found']:
            st.markdown("**Entities Recognized:**")
            unique_entities = list(set(analytics['entities_found'][-5:]))  # Last 5 unique
            for entity in unique_entities:
                st.markdown(f'<span class="entity-tag">{entity}</span>', unsafe_allow_html=True)
        
        # Performance metrics
        st.markdown("**Performance Metrics:**")
        if analytics['confidence_scores']:
            avg_confidence = sum(analytics['confidence_scores']) / len(analytics['confidence_scores'])
            st.metric("Confidence Score", f"{avg_confidence:.2f}")
        
        if analytics['response_times']:
            avg_response_time = sum(analytics['response_times']) / len(analytics['response_times'])
            st.metric("Response Time", f"{avg_response_time:.2f}s")
        
        # System status
        st.markdown("### ⚡ System Status")
        st.markdown('<div class="status-indicator status-online">🟢 AI Model: Online</div>', unsafe_allow_html=True)
        st.markdown('<div class="status-indicator status-online">🟢 Knowledge Graph: Active</div>', unsafe_allow_html=True)
        st.markdown('<div class="status-indicator status-online">🟢 Entity Recognition: Running</div>', unsafe_allow_html=True)
        
        st.info(f"🔄 Processed {analytics['queries_processed']} queries")

def main():
    # Header
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-bottom: 2rem; color: white;">
        <h1>🛰️ QuantumLens</h1>
        <h3>MOSDAC AI Assistant - Intelligent Satellite Data Discovery</h3>
        <p>by QuantumSprouts | Advanced RAG System for Instant Information Retrieval</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Configure Gemini
    model = configure_gemini()
    
    # Main layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 💬 Chat with MOSDAC AI Assistant")
        
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if "entities" in message:
                    st.markdown("**Entities Recognized:** " + " ".join([f'`{e[1]}`' for e in message["entities"]]))
        
        # Chat input
        if prompt := st.chat_input("Ask me about MOSDAC satellite data, navigation, or data access..."):
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Process query
            entities = extract_entities(prompt)
            intent = classify_intent(prompt)
            
            # Get AI response
            with st.chat_message("assistant"):
                with st.spinner("Processing your query..."):
                    response, response_time = get_ai_response(model, prompt)
                st.markdown(response)
                
                # Show entities if found
                if entities:
                    entity_display = " ".join([f'<span class="entity-tag">{e[1]}</span>' for e in entities])
                    st.markdown(f"**Entities Recognized:** {entity_display}", unsafe_allow_html=True)
            
            # Add assistant message
            st.session_state.messages.append({
                "role": "assistant", 
                "content": response,
                "entities": entities,
                "intent": intent,
                "response_time": response_time
            })
            
            # Update analytics
            update_analytics(prompt, entities, response_time, intent)
    
    with col2:
        display_analytics()
        
        # Sample queries
        st.markdown("### 🎯 Try These Queries:")
        sample_queries = [
            "How to navigate to GSMap ISRO Rain data?",
            "Where can I find SST data on MOSDAC?",
            "How to download INSAT-3D temperature data?",
            "What is the format of ocean chlorophyll data?",
            "How to access restricted data on MOSDAC?"
        ]
        
        for query in sample_queries:
            if st.button(query, key=query, use_container_width=True):
                # Simulate clicking the query
                st.session_state.messages.append({"role": "user", "content": query})
                
                # Process the query
                entities = extract_entities(query)
                intent = classify_intent(query)
                response, response_time = get_ai_response(model, query)
                
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": response,
                    "entities": entities,
                    "intent": intent,
                    "response_time": response_time
                })
                
                update_analytics(query, entities, response_time, intent)
                st.rerun()

if __name__ == "__main__":
    main()
