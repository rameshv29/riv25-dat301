#!/usr/bin/env python3
"""
Unified Mahavat Agent - Final version with fixed MCP servers and clean UI
"""

import streamlit as st
import pandas as pd
import json
import os
import time
from datetime import datetime
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp import StdioServerParameters, stdio_client
import boto3

# Configuration - Using workshop environment variables
AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'dat301-ws-incidents')
MAIN_KB_ID = os.environ.get('MAIN_KB_ID', os.environ.get('IDR_KB_ID', ''))
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-20250514-v1:0')
DATABASE_NAME = os.environ.get('DATABASE_NAME', 'workshop_db')
RDS_CLUSTER_ARN = os.environ.get('RDS_CLUSTER_ARN', '')

# Use main database secret ARN for PostgreSQL
DATABASE_SECRET_ARN = os.environ.get('DATABASE_SECRET_ARN', '')
POSTGRES_SECRET_ARN = DATABASE_SECRET_ARN  # Use main DB secret
POSTGRES_RESOURCE_ARN = RDS_CLUSTER_ARN

def get_kpi(iconname, metricname, metricvalue):
    """Create KPI card"""
    wch_colour_box = (0,204,102)
    wch_colour_font = (0,0,0)
    fontsize = 32
    lnk = '<link rel="stylesheet" href="https://use.fontawesome.com/releases/v6.6.0/css/all.css" crossorigin="anonymous">'
    
    htmlstr = f"""<p style='background-color: rgb({wch_colour_box[0]}, 
                                              {wch_colour_box[1]}, 
                                              {wch_colour_box[2]}, 0.75); 
                        color: rgb({wch_colour_font[0]}, 
                                   {wch_colour_font[1]}, 
                                   {wch_colour_font[2]}, 0.75); 
                        font-size: {fontsize}px; 
                        border-radius: 7px; 
                        padding-left: 12px; 
                        padding-top: 18px; 
                        padding-bottom: 18px; 
                        line-height:25px;'>
                        <i class='{iconname} fa-xs'></i> {metricvalue}
                        </style><BR><span style='font-size: 14px; 
                        margin-top: 0;'>{metricname}</style></span></p>"""
    return lnk + htmlstr

def create_mcp_client_safe(name, server_params, status_container):
    """Safely create MCP client with error handling - messages in sidebar"""
    try:
        with status_container:
            st.info(f"🔄 Initializing {name}...")
        client = MCPClient(lambda: stdio_client(server_params))
        client.start()
        with status_container:
            st.success(f"✅ {name}")
        return client
    except Exception as e:
        with status_container:
            st.warning(f"⚠️ {name}: {str(e)[:50]}...")
        return None

@st.cache_resource
def create_available_mcp_clients():
    """Initialize available MCP clients - messages in sidebar only"""
    
    # Create a placeholder in sidebar for status messages
    with st.sidebar:
        status_container = st.empty()
        with status_container:
            st.info("🔧 Initializing MCP servers...")
    
    available_clients = {}
    
    # MCP server configurations with correct package names
    mcp_configs = {
        'idr': {
            'params': StdioServerParameters(
                command="python3",
                args=[os.path.join(os.path.dirname(__file__), "idr_mcp_server.py")],
                env={
                    "AWS_REGION": AWS_REGION,
                    "DYNAMODB_TABLE": DYNAMODB_TABLE
                }
            ),
            'required': True,
            'description': 'Incident management'
        },
        'main_kb': {
            'params': StdioServerParameters(
                command="uvx",
                args=["awslabs.bedrock-kb-retrieval-mcp-server@latest"],
                env={
                    "AWS_REGION": AWS_REGION,
                    "FASTMCP_LOG_LEVEL": "ERROR"
                }
            ),
            'required': True,
            'description': 'Knowledge base retrieval'
        },
        'aws_api': {
            'params': StdioServerParameters(
                command="uvx",
                args=["awslabs.aws-api-mcp-server@latest", "--region", AWS_REGION]
            ),
            'required': True,
            'description': 'AWS operations'
        },
        'cloudwatch': {
            'params': StdioServerParameters(
                command="uvx",
                args=["awslabs.cloudwatch-mcp-server@latest"],
                env={
                    "AWS_REGION": AWS_REGION,
                    "FASTMCP_LOG_LEVEL": "ERROR"
                }
            ),
            'required': False,
            'description': 'CloudWatch logs and metrics'
        },
        'performance_insights': {
            'params': StdioServerParameters(
                command="uvx",
                args=["awslabs.rds-performance-insights-mcp-server@latest"],  # Correct package name
                env={
                    "AWS_REGION": AWS_REGION,
                    "FASTMCP_LOG_LEVEL": "ERROR"
                }
            ),
            'required': False,
            'description': 'RDS Performance Insights'
        },
        'aws_docs': {
            'params': StdioServerParameters(
                command="uvx",
                args=["awslabs.aws-documentation-mcp-server@latest"],  # Correct package name
                env={
                    "AWS_REGION": AWS_REGION,
                    "FASTMCP_LOG_LEVEL": "ERROR"
                }
            ),
            'required': False,
            'description': 'AWS documentation'
        }
    }
    
    # Add PostgreSQL server with main DB secret
    if POSTGRES_SECRET_ARN and POSTGRES_RESOURCE_ARN:
        mcp_configs['postgres'] = {
            'params': StdioServerParameters(
                command="uvx",
                args=[
                    "awslabs.postgres-mcp-server@latest",
                    "--secret_arn", POSTGRES_SECRET_ARN,
                    "--database", DATABASE_NAME,
                    "--region", AWS_REGION,
                    "--readonly", "false",
                    "--resource_arn", POSTGRES_RESOURCE_ARN
                ],
                env={"AWS_REGION": AWS_REGION}
            ),
            'required': False,
            'description': 'PostgreSQL database access'
        }
    
    # Add postgres query provider if file exists
    provider_file = os.path.join(os.path.dirname(__file__), "postgres_query_provider.py")
    if os.path.exists(provider_file):
        mcp_configs['postgres_query_provider'] = {
            'params': StdioServerParameters(
                command="python3",
                args=[provider_file],
                env={"AWS_REGION": AWS_REGION}
            ),
            'required': False,
            'description': 'PostgreSQL diagnostic workflows'
        }
    
    # Initialize each client - status messages in sidebar
    for name, config in mcp_configs.items():
        client = create_mcp_client_safe(name, config['params'], status_container)
        if client:
            available_clients[name] = client
        elif config['required']:
            with status_container:
                st.error(f"❌ Required server '{name}' failed")
    
    # Final status in sidebar
    with status_container:
        st.success(f"✅ {len(available_clients)} servers active")
        if available_clients:
            server_list = ", ".join(available_clients.keys())
            st.caption(f"Active: {server_list}")
    
    return available_clients

# Global MCP clients (initialized once)
if 'mcp_clients' not in st.session_state:
    st.session_state.mcp_clients = create_available_mcp_clients()

mcp_clients = st.session_state.mcp_clients

@tool
def postgres_diagnostic_specialist(
    query: str, 
    context: str = "",
    enable_streaming: bool = True,
    workshop_mode: bool = False
) -> str:
    """PostgreSQL diagnostic specialist with available MCP servers."""
    
    # Get available PostgreSQL MCP tools
    postgres_mcp_tools = []
    postgres_servers = ['postgres_query_provider', 'postgres', 'performance_insights', 
                       'cloudwatch', 'aws_api', 'aws_docs', 'main_kb']
    
    for server_name in postgres_servers:
        if server_name in mcp_clients and mcp_clients[server_name]:
            try:
                tools = mcp_clients[server_name].list_tools_sync()
                postgres_mcp_tools.extend(tools)
            except Exception as e:
                pass  # Silent failure for tool loading
    
    if not postgres_mcp_tools:
        return "PostgreSQL diagnostic tools are not available. Please check MCP server initialization."
    
    # PostgreSQL system prompt
    postgres_system_prompt = f"""You are a PostgreSQL Database expert with comprehensive MCP server access.

**Available MCP Servers:** {list(mcp_clients.keys())}

**WORKFLOW-FIRST Approach:**
• vacuum/bloat/autovacuum → vacuum_analysis_diagnostic()
• slow queries/performance → query_performance_diagnostic()
• locks/blocking → lock_analysis_diagnostic()
• connections/sessions → connection_analysis_diagnostic()

**Multi-Server Capabilities:**
• PostgreSQL: Direct SQL execution and database analysis
• Performance Insights: RDS metrics and top SQL queries
• CloudWatch: Log analysis and infrastructure metrics
• AWS API: RDS configuration and parameter analysis
• AWS Docs: Best practices and troubleshooting guides
• Main KB: Runbook retrieval (ID: {MAIN_KB_ID})

**CRITICAL Rules:**
- Use all available tools for comprehensive analysis
- ALWAYS include --region {AWS_REGION} in AWS commands
- Provide multi-dimensional analysis combining database + infrastructure data
- Execute parallel analysis across multiple MCP servers when possible

DATABASE: {DATABASE_NAME}, REGION: {AWS_REGION}
"""
    
    # Create PostgreSQL specialist agent
    postgres_agent = Agent(
        name="PostgreSQL_Diagnostic_Specialist",
        model=BedrockModel(model_id=BEDROCK_MODEL_ID),
        tools=postgres_mcp_tools,
        system_prompt=postgres_system_prompt
    )
    
    enhanced_prompt = f"""
CONTEXT: {context}
USER QUERY: {query}

Available servers: {list(mcp_clients.keys())}
Total tools: {len(postgres_mcp_tools)}

Execute comprehensive PostgreSQL diagnostics using all available MCP servers:
- Use workflow detection if postgres_query_provider available
- Execute SQL queries if postgres server available  
- Get Performance Insights metrics if available
- Search CloudWatch logs if available
- Check AWS configuration if aws_api available
- Retrieve runbooks from Main KB if available

Provide multi-server analysis with actionable recommendations.
"""
    
    try:
        return str(postgres_agent(enhanced_prompt))
    except Exception as e:
        return f"PostgreSQL diagnostic error: {str(e)}"

@tool
def idr_incident_specialist(
    incident_context: str,
    action: str,
    incident_data: dict = None
) -> str:
    """IDR specialist with available MCP servers."""
    
    # Get available IDR MCP tools
    idr_mcp_tools = []
    idr_servers = ['idr', 'main_kb', 'aws_api']
    
    for server_name in idr_servers:
        if server_name in mcp_clients and mcp_clients[server_name]:
            try:
                tools = mcp_clients[server_name].list_tools_sync()
                idr_mcp_tools.extend(tools)
            except Exception as e:
                pass  # Silent failure for tool loading
    
    if not idr_mcp_tools:
        return "IDR tools are not available. Please check MCP server initialization."
    
    # IDR system prompt
    idr_system_prompt = f"""You are an AWS incident remediation specialist.

**Available MCP Servers:** {list(mcp_clients.keys())}

**Capabilities:**
• IDR Server: Incident management (list, details, status updates)
• Main KB: Runbook retrieval from knowledge base (ID: {MAIN_KB_ID})
• AWS API: Resource modifications and verification

**CRITICAL Rules:**
- Follow runbook procedures exactly when available
- ALWAYS include --region {AWS_REGION} in AWS commands
- Verify all changes before updating incident status
- Provide step-by-step remediation guidance

DATABASE: {DATABASE_NAME}, REGION: {AWS_REGION}
DYNAMODB_TABLE: {DYNAMODB_TABLE}
"""
    
    # Create IDR specialist agent
    idr_agent = Agent(
        name="IDR_Incident_Specialist",
        model=BedrockModel(model_id=BEDROCK_MODEL_ID),
        tools=idr_mcp_tools,
        system_prompt=idr_system_prompt
    )
    
    enhanced_prompt = f"""
INCIDENT CONTEXT: {incident_context}
ACTION REQUESTED: {action}
INCIDENT DATA: {incident_data}

Available servers: {list(mcp_clients.keys())}

Execute IDR tasks:
- Use IDR server for incident management if available
- Use Main KB (ID: {MAIN_KB_ID}) for runbooks if available
- Use AWS API for resource modifications if available

Provide comprehensive remediation guidance.
"""
    
    try:
        return str(idr_agent(enhanced_prompt))
    except Exception as e:
        return f"IDR specialist error: {str(e)}"

def create_unified_mahavat_agent():
    """Create unified Mahavat agent with available specialist tools"""
    
    available_servers = list(mcp_clients.keys())
    
    unified_system_prompt = f"""You are the Mahavat Agent - a unified AWS database management specialist.

**Environment:**
- AWS Region: {AWS_REGION}
- Database: {DATABASE_NAME}
- DynamoDB: {DYNAMODB_TABLE}
- Main KB: {MAIN_KB_ID}

**Available MCP Servers ({len(available_servers)}):** {available_servers}

**Specialist Tools:**
1. 🚨 IDR Incident Specialist - incidents, alarms, remediation, runbooks
2. 🐘 PostgreSQL Diagnostic Specialist - database diagnostics, performance, vacuum, locks

**INTELLIGENT ROUTING:**
- Route to IDR specialist for: incidents, alarms, remediation, runbooks
- Route to PostgreSQL specialist for: database diagnostics, performance, vacuum, locks
- Use both specialists for: complex database incidents requiring analysis + remediation

**CONTEXT SHARING:**
- Maintain full conversation context across specialists
- Share incident details with diagnostic analysis
- Coordinate between specialists for comprehensive solutions
"""
    
    unified_agent = Agent(
        name="Mahavat_Agent",
        model=BedrockModel(model_id=BEDROCK_MODEL_ID),
        tools=[
            postgres_diagnostic_specialist,
            idr_incident_specialist
        ],
        system_prompt=unified_system_prompt
    )
    
    return unified_agent

def get_incidents_data(status="PENDING"):
    """Get incidents from DynamoDB"""
    try:
        dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
        table = dynamodb.Table(DYNAMODB_TABLE)
        
        if status:
            response = table.scan(
                FilterExpression='incident_status = :status',
                ExpressionAttributeValues={':status': status}
            )
        else:
            response = table.scan()
        
        return response.get('Items', [])
    except Exception as e:
        st.error(f"Error fetching incidents: {str(e)}")
        return []

def handle_chat_message(prompt):
    """Handle chat message from user"""
    
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    
    unified_agent = st.session_state.unified_mahavat_agent
    
    context_prompt = prompt
    if st.session_state.selected_incident_context:
        context_prompt = f"Context: {st.session_state.selected_incident_context}\n\nUser request: {prompt}"
    
    try:
        with st.spinner("Mahavat Agent thinking..."):
            response = unified_agent(context_prompt)
        
        st.session_state.chat_messages.append({"role": "assistant", "content": str(response)})
        
    except Exception as e:
        st.session_state.chat_messages.append({
            "role": "assistant", 
            "content": f"Error: {str(e)}"
        })
    
    st.rerun()

def show_pending_incidents():
    """Show pending incidents page"""
    st.title(":orange[Pending Incidents]")
    st.subheader(f":orange[Metric Summary as of] :blue[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]", divider=True)
    
    incidents = get_incidents_data(status="PENDING")
    
    if not incidents:
        st.info("No pending incidents found")
        return
    
    # Prepare dataframe
    incidents_data = []
    for item in incidents:
        incidents_data.append({
            'pk': item.get('pk', ''),
            'incident_id': item.get('incident_id', ''),
            'incidentIdentifier': item.get('incidentIdentifier', item.get('incident_identifier', '')),
            'incidentType': item.get('incidentType', item.get('incident_type', '')),
            'incident_status': item.get('incident_status', ''),
            'incident_time': item.get('incident_time', ''),
            'alarm_name': item.get('alarm_name', ''),
            'alarm_reason': item.get('alarm_reason', '')
        })
    
    df = pd.DataFrame(incidents_data)
    df = df.sort_values('incident_time', ascending=False)
    
    # Display KPIs
    col1, col2, col3 = st.columns(3)
    col1.markdown(get_kpi("fa-solid fa-circle-exclamation", "Total Pending Incidents", len(df)), unsafe_allow_html=True)
    col2.markdown(get_kpi("fa-solid fa-server", "Total Unique Instance", df['incidentIdentifier'].nunique()), unsafe_allow_html=True)
    col3.markdown(get_kpi("fa-solid fa-bell", "Total Unique Alert Type", df['incidentType'].nunique()), unsafe_allow_html=True)
    
    # Incident table and actions
    col4, col5 = st.columns([3, 1])
    
    col4.markdown("### :orange[Incident Summary]")
    col4.write("Select an incident to process by clicking the row")
    
    event = col4.dataframe(
        df,
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        column_config={
            "incidentType": "Incident Type",
            "pk": "Session ID",
            "incidentIdentifier": "Database Instance",
            "incident_status": "Status",
            "incident_time": "Incident Time"
        },
        column_order=("pk", "incidentIdentifier", "incidentType", "incident_status", "incident_time")
    )
    
    # User actions
    col5.markdown("### :orange[User Action]")
    col5.write("Actions requiring manual intervention")
    
    runbook_action = col5.button("Get Runbook", use_container_width=True)
    remediate_action = col5.button("Remediate Incident", use_container_width=True)
    
    col5.divider()
    
    # Handle selection
    rows = event['selection']['rows']
    selected_incident = None
    
    if len(rows) != 0:
        selected_incident = df.iloc[rows[0]]
        col4.info(f"Selected: {selected_incident['incident_id']}")
        
        st.session_state.selected_incident_context = f"Incident {selected_incident['incident_id']} ({selected_incident['incidentType']}) on {selected_incident['incidentIdentifier']}"
    
    # Get Runbook action
    if runbook_action:
        if selected_incident is None:
            col4.error("Please select an incident to get the runbook")
        else:
            with col4.status("Mahavat Agent retrieving runbook..."):
                col4.markdown(f"***Runbook Instructions for {selected_incident['incident_id']}***")
                
                prompt = f"""Get the remediation runbook for {selected_incident['incidentType']} incident from Main Knowledge Base (ID: {MAIN_KB_ID})."""
                
                response = st.session_state.unified_mahavat_agent(prompt)
                col4.markdown(str(response))
    
    # Remediate action
    if remediate_action:
        if selected_incident is None:
            col4.error("Please select an incident to auto-remediate")
        else:
            with col4.status("Mahavat Agent remediating incident..."):
                col4.markdown(f"***Auto-remediation for {selected_incident['incident_id']}***")
                
                prompt = f"""Remediate this {selected_incident['incidentType']} incident on {selected_incident['incidentIdentifier']} in region {AWS_REGION}. Use both PostgreSQL diagnostics and IDR remediation as needed."""
                
                response = st.session_state.unified_mahavat_agent(prompt)
                col4.markdown(str(response))
                
                col4.success("✅ Remediation completed! Click 'Refresh' to see updated incident status.")
                if col4.button("Refresh Incidents", use_container_width=True):
                    st.rerun()

def show_all_incidents():
    """Show all incidents page"""
    st.title(":orange[All Incidents]")
    st.subheader(f":orange[Incident History as of] :blue[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]", divider=True)
    
    incidents = get_incidents_data(status=None)
    
    if not incidents:
        st.info("No incidents found")
        return
    
    # Prepare dataframe
    incidents_data = []
    for item in incidents:
        incidents_data.append({
            'incident_id': item.get('incident_id', ''),
            'incidentIdentifier': item.get('incidentIdentifier', ''),
            'incidentType': item.get('incidentType', ''),
            'incident_status': item.get('incident_status', ''),
            'incident_time': item.get('incident_time', ''),
            'alarm_name': item.get('alarm_name', ''),
            'created_at': item.get('created_at', ''),
            'resolution': item.get('resolution_notes', '')
        })
    
    df = pd.DataFrame(incidents_data)
    df = df.sort_values('incident_time', ascending=False)
    
    st.markdown("### :orange[All Incidents]")
    st.dataframe(
        df,
        hide_index=True,
        column_config={
            "incident_id": "Incident ID",
            "incidentIdentifier": "Database Instance",
            "incidentType": "Type",
            "incident_status": "Status",
            "incident_time": "Incident Time",
            "alarm_name": "Alarm Name",
            "created_at": "Created At",
            "resolution": "Resolution"
        },
        column_order=("incident_id", "incidentIdentifier", "incidentType", "incident_status", "incident_time", "resolution")
    )
    
    st.caption(f"Total incidents: {len(df)}")

def main():
    """Main application"""
    st.set_page_config(page_title="Mahavat Agent - Unified Database Management", layout="wide")
    
    st.markdown("""
        <style>
               .block-container {
                    padding-top: 1rem;
                    padding-bottom: 0rem;
                    padding-left: 5rem;
                    padding-right: 5rem;
                }
        </style>
        """, unsafe_allow_html=True)
    
    # Initialize chat state
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    if 'show_chat' not in st.session_state:
        st.session_state.show_chat = False
    if 'selected_incident_context' not in st.session_state:
        st.session_state.selected_incident_context = None
    
    # Sidebar
    with st.sidebar:
        st.image("https://d1.awsstatic.com/logos/aws-logo-lockups/poweredbyaws/PB_AWS_logo_RGB_stacked_REV_SQ.91cd4af40773cbfbd15577a3c2b8a346fe3e8fa2.png", width=120)
        st.subheader("Mahavat Agent")
        st.caption("Unified Database Management")
        st.caption("IDR + PostgreSQL Diagnostics")
        st.divider()
        
        page = st.radio("Navigation", ["Pending Incidents", "All Incidents"], key="page_nav")
        
        st.divider()
        
        # Chat toggle in sidebar
        if st.button("💬 Mahavat Agent Chat", use_container_width=True):
            st.session_state.show_chat = not st.session_state.show_chat
            st.rerun()
        
        st.divider()
        st.caption("Built with Strands Agents-as-Tools")
        
        # MCP Server Status - shows initialization messages here
        with st.expander("🛠️ MCP Server Status"):
            available_servers = list(mcp_clients.keys())
            st.markdown(f"**Active Servers ({len(available_servers)}):**")
            for server in available_servers:
                st.markdown(f"✅ {server}")
    
    # Initialize unified agent
    if 'unified_mahavat_agent' not in st.session_state:
        with st.spinner("🔧 Initializing Unified Mahavat Agent..."):
            st.session_state.unified_mahavat_agent = create_unified_mahavat_agent()
    
    # Main content
    if page == "Pending Incidents":
        show_pending_incidents()
    else:
        show_all_incidents()
    
    # Show chat section at bottom if enabled
    if st.session_state.show_chat:
        st.divider()
        st.markdown("### 💬 Mahavat Agent Chat")
        st.caption(f"🤖 Active servers: {', '.join(list(mcp_clients.keys()))}")
        
        # Context indicator
        if st.session_state.selected_incident_context:
            st.info(f"🎯 Context: {st.session_state.selected_incident_context}")
        
        # Chat messages
        chat_container = st.container(height=300)
        with chat_container:
            for msg in st.session_state.chat_messages:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])
        
        # Chat input
        if prompt := st.chat_input("Ask about incidents, remediation, or PostgreSQL diagnostics...", key="chat_input"):
            handle_chat_message(prompt)

if __name__ == "__main__":
    main()
