#!/usr/bin/env python3
"""
IDR Agent UI - Incident Detection & Remediation with Chat
Uses Strands Agent with MCP Tools + Integrated Chat Window
"""

import streamlit as st
import pandas as pd
import json
import os
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp import StdioServerParameters, stdio_client
from datetime import datetime
import boto3

# Configuration
AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'dat-ws-v9-incidents')
IDR_KB_ID = os.environ.get('IDR_KB_ID', '')
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-20250514-v1:0')

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

@st.cache_resource
def create_mcp_clients():
    """Create and start MCP clients - Following official Strands pattern"""
    
    # IDR MCP Server (incident management)
    idr_client = MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="python3",
                args=[os.path.join(os.path.dirname(__file__), "idr_mcp_server.py")],
                env={
                    "AWS_REGION": AWS_REGION,
                    "DYNAMODB_TABLE": DYNAMODB_TABLE
                }
            )
        )
    )
    
    # Bedrock KB Retrieval MCP Server (for runbooks)
    kb_client = MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="uvx",
                args=["awslabs.bedrock-kb-retrieval-mcp-server@latest"],
                env={
                    "AWS_REGION": AWS_REGION,
                    "FASTMCP_LOG_LEVEL": "ERROR"
                }
            )
        )
    )
    
    # AWS API MCP Server (for remediation)
    aws_api_client = MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="uvx",
                args=["awslabs.aws-api-mcp-server@latest", "--region", AWS_REGION]
            )
        )
    )
    
    # Start all clients (initialize connections)
    idr_client.start()
    kb_client.start()
    aws_api_client.start()
    
    return {
        'idr': idr_client,
        'kb': kb_client,
        'aws_api': aws_api_client
    }

def create_idr_agent():
    """Create IDR agent with proper MCP tools registration"""
    
    if 'idr_agent' in st.session_state:
        return st.session_state.idr_agent, st.session_state.mcp_clients
    
    # Get MCP clients
    mcp_clients = create_mcp_clients()
    
    # Get tools from all MCP servers (CRITICAL: This is the correct pattern!)
    tools = (
        mcp_clients['idr'].list_tools_sync() + 
        mcp_clients['kb'].list_tools_sync() + 
        mcp_clients['aws_api'].list_tools_sync()
    )
    
    # Create Bedrock model
    model = BedrockModel(model_id=BEDROCK_MODEL_ID)
    
    # Create agent with proper tools
    agent = Agent(
        name="IDR_Agent",
        model=model,
        tools=tools,  # Pass the actual tools, not MCPClient objects!
        system_prompt=f"""You are an AWS incident remediation specialist with access to MCP tools.

**Your Tools:**
- IDR MCP Server: list_incidents, get_incident_details, update_incident_status
- Bedrock KB Retrieval: retrieve (knowledge_base_id: {IDR_KB_ID})
- AWS API Server: call_aws (execute AWS CLI commands)

**CRITICAL: AWS Region**
- ALL AWS operations MUST use region: {AWS_REGION}
- ALWAYS include --region {AWS_REGION} in call_aws commands
- Example: "aws rds describe-db-instances --db-instance-identifier <id> --region {AWS_REGION}"

**Remediation Workflow:**

1. **Get Runbook**: Use retrieve tool to get remediation runbook from knowledge base
   - Query: "[incident_type] remediation runbook"
   - Extract the exact runbook name/title and steps

2. **Follow Runbook Steps EXACTLY**: The runbook contains specific instructions:
   - Conditions to check (e.g., "IF usage > 80%")
   - Commands to execute
   - Calculations to perform (e.g., "increase by 20%")

3. **Execute Commands**: Use call_aws tool to:
   - Get current configuration (ALWAYS with --region {AWS_REGION})
   - Check metrics
   - Apply changes
   - Verify results

4. **Update Status**: Use update_incident_status with:
   - incident_id: The incident ID
   - runbook_name: The exact name/title of the runbook used (e.g., "IOPS Remediation Runbook")
   - remediation_steps: Array of strings, each describing a step taken (e.g., ["Retrieved current IOPS: 3000", "Calculated new IOPS: 3600 (20% increase)", "Applied modification with modify-db-instance", "Verified change applied successfully"])

**CRITICAL Rules:**
- ALWAYS use your tools - never simulate or assume
- ALWAYS include --region {AWS_REGION} in AWS commands
- Follow runbook logic exactly - don't hardcode values
- Calculate based on current state and runbook instructions
- Verify changes before updating incident status
- Provide clear step-by-step output showing what you did
- When calling update_incident_status, provide the runbook name and detailed steps array
- If a resource is not found, STOP and report the error - don't guess or simulate

**Example for IOPS incident:**
1. retrieve runbook for "IOPS remediation"
2. call_aws: aws rds describe-db-instances --db-instance-identifier <id> --region {AWS_REGION}
3. Calculate new IOPS per runbook (e.g., current * 1.2)
4. call_aws: aws rds modify-db-instance --db-instance-identifier <id> --iops <new> --region {AWS_REGION} --apply-immediately
5. call_aws: verify change was applied
6. update_incident_status(incident_id="...", runbook_name="IOPS Remediation Runbook", remediation_steps=["Step 1: ...", "Step 2: ...", ...])

Always show your work: what you found, what you calculated, what you executed."""
    )
    
    # Store in session state
    st.session_state.idr_agent = agent
    st.session_state.mcp_clients = mcp_clients
    
    return agent, mcp_clients

def get_incidents_data(status="PENDING"):
    """Get incidents from DynamoDB"""
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)
    
    try:
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
    
    # Add user message
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    
    # Get agent response
    agent = st.session_state.idr_agent
    
    # Add context if incident is selected
    context_prompt = prompt
    if st.session_state.selected_incident_context:
        context_prompt = f"Context: {st.session_state.selected_incident_context}\n\nUser request: {prompt}"
    
    try:
        with st.spinner("IDR Agent thinking..."):
            response = agent(context_prompt)
        
        # Add agent response
        st.session_state.chat_messages.append({"role": "assistant", "content": str(response)})
        
    except Exception as e:
        st.session_state.chat_messages.append({
            "role": "assistant", 
            "content": f"Error: {str(e)}"
        })
    
    st.rerun()

def show_pending_incidents():
    """Show pending incidents page with agent-based remediation"""
    st.title(":orange[Pending Incidents]")
    st.subheader(f":orange[Metric Summary as of] :blue[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]", divider=True)
    
    # Get agent
    agent = st.session_state.idr_agent
    
    # Get incidents
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
        
        # Update chat context
        st.session_state.selected_incident_context = f"Incident {selected_incident['incident_id']} ({selected_incident['incidentType']}) on {selected_incident['incidentIdentifier']}"
    
    # Get Runbook action
    if runbook_action:
        if selected_incident is None:
            col4.error("Please select an incident to get the runbook")
        else:
            with col4.status("Agent retrieving runbook..."):
                col4.markdown(f"***Runbook Instructions for {selected_incident['incident_id']}***")
                
                # Use agent to get runbook
                prompt = f"""Get the remediation runbook for {selected_incident['incidentType']} incident.

Use the retrieve tool with:
- knowledge_base_id: {IDR_KB_ID}
- query: "{selected_incident['incidentType']} remediation runbook"

Return ONLY the runbook text content, formatted for readability. Replace markdown headers with bold text."""
                
                response = agent(prompt)
                
                # Format the response
                runbook_text = str(response)
                runbook_text = runbook_text.replace("# Title", "**Title:**")
                runbook_text = runbook_text.replace("## ", "\n\n**").replace(" ##", ":**")
                runbook_text = runbook_text.replace(". 1.", ".\n\n1.")
                runbook_text = runbook_text.replace(". 2.", ".\n\n2.")
                runbook_text = runbook_text.replace(". 3.", ".\n\n3.")
                runbook_text = runbook_text.replace(". 4.", ".\n\n4.")
                
                col4.markdown(runbook_text)
    
    # Remediate action
    if remediate_action:
        if selected_incident is None:
            col4.error("Please select an incident to auto-remediate")
        else:
            with col4.status("Agent remediating incident..."):
                col4.markdown(f"***Auto-remediation for {selected_incident['incident_id']}***")
                
                # Use agent to remediate
                prompt = f"""Remediate this {selected_incident['incidentType']} incident following the runbook EXACTLY.

**Incident Details:**
- ID: {selected_incident['incident_id']}
- Type: {selected_incident['incidentType']}
- Resource: {selected_incident['incidentIdentifier']}
- Region: {AWS_REGION}
- Reason: {selected_incident['alarm_reason']}

**CRITICAL Instructions:**

1. **Get Runbook**: Use retrieve tool to get "{selected_incident['incidentType']} remediation runbook" from KB {IDR_KB_ID}

2. **Follow Runbook Steps**: Execute each step in order:
   - Step 1: Check resource status
   - Step 2: Get current metrics
   - Step 3: Get current configuration
   - Step 4: Calculate new value per runbook (e.g., increase by 20%)
   - Step 5: Apply the change
   - Step 6: Verify the change

3. **Use call_aws Tool**: For ALL AWS operations, use call_aws with:
   - ALWAYS specify --region {AWS_REGION}
   - Use exact resource identifier: {selected_incident['incidentIdentifier']}
   - Example: "aws rds describe-db-instances --db-instance-identifier {selected_incident['incidentIdentifier']} --region {AWS_REGION}"

4. **Show Your Work**: For each step, show:
   - What command you're running
   - What the result was
   - What calculation you performed
   - What the new value is

5. **Update Status**: ONLY after successful verification, use update_incident_status

**DO NOT:**
- Simulate or assume - use actual AWS calls
- Skip verification
- Update status before verifying
- Use wrong region (must be {AWS_REGION})

Start with Step 1 of the runbook."""
                
                response = agent(prompt)
                col4.markdown(str(response))
                
                # Show success message and button to refresh
                col4.success("✅ Remediation completed! Click 'Refresh' to see updated incident status.")
                if col4.button("Refresh Incidents", use_container_width=True):
                    st.rerun()

def show_all_incidents():
    """Show all incidents page"""
    st.title(":orange[All Incidents]")
    st.subheader(f":orange[Incident History as of] :blue[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]", divider=True)
    
    # Get all incidents
    incidents = get_incidents_data(status=None)
    
    if not incidents:
        st.info("No incidents found")
        return
    
    # Prepare dataframe
    incidents_data = []
    for item in incidents:
        incidents_data.append({
            'incident_id': item.get('incident_id', ''),
            'incidentIdentifier': item.get('incidentIdentifier', item.get('incident_identifier', '')),
            'incidentType': item.get('incidentType', item.get('incident_type', '')),
            'incident_status': item.get('incident_status', ''),
            'incident_time': item.get('incident_time', ''),
            'alarm_name': item.get('alarm_name', ''),
            'created_at': item.get('created_at', ''),
            'runbook_used': item.get('resolution', ''),
            'remediation_steps': ', '.join(item.get('remediation_steps', []))
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
            "runbook_used": "Runbook Used",
            "remediation_steps": "Remediation Steps"
        },
        column_order=("incident_id", "incidentIdentifier", "incidentType", "incident_status", "incident_time", "runbook_used", "remediation_steps")
    )
    
    st.caption(f"Total incidents: {len(df)}")

def main():
    """Main application"""
    st.set_page_config(page_title="IDR: Incident Detection & Remediation", layout="wide")
    
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
        st.image("Mahavat.png", width=120)
        st.subheader("IDR: Incident Detection & Remediation")
        st.caption("Powered by Amazon Aurora & Bedrock")
        st.divider()
        
        page = st.radio("Navigation", ["Pending Incidents", "All Incidents"], key="page_nav")
        
        st.divider()
        
        # Chat toggle in sidebar
        if st.button("💬 IDR Agent Chat", use_container_width=True):
            st.session_state.show_chat = not st.session_state.show_chat
            st.rerun()
        
        st.divider()
        st.caption("Built with Strands Agent Framework")
    
    # Initialize agent
    if 'idr_agent' not in st.session_state:
        with st.spinner("🔧 Initializing IDR Agent..."):
            agent, mcp_clients = create_idr_agent()
    
    # Main content
    if page == "Pending Incidents":
        show_pending_incidents()
    else:
        show_all_incidents()
    
    # Show chat section at bottom if enabled
    if st.session_state.show_chat:
        st.divider()
        st.markdown("### 💬 IDR Agent Chat")
        
        # Context indicator
        if st.session_state.selected_incident_context:
            st.info(f"🎯 Context: {st.session_state.selected_incident_context}")
        
        # Chat messages
        chat_container = st.container(height=300)
        with chat_container:
            for msg in st.session_state.chat_messages:
                avatar = "Mahavat.png" if msg["role"] == "assistant" else None
                with st.chat_message(msg["role"], avatar=avatar):
                    st.write(msg["content"])
        
        # Chat input
        if prompt := st.chat_input("Ask IDR Agent...", key="chat_input"):
            handle_chat_message(prompt)

if __name__ == "__main__":
    main()
