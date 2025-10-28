#!/usr/bin/env python3
"""
IDR Agent UI - Incident Detection & Remediation
Uses Bedrock Knowledge Base Retrieval for runbooks
"""

import streamlit as st
import pandas as pd
import json
import os
import sys
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp import StdioServerParameters, stdio_client
from datetime import datetime

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

def create_idr_agent():
    """Create IDR agent with MCP servers"""
    if 'idr_agent' in st.session_state and 'mcp_clients' in st.session_state:
        return st.session_state.idr_agent, st.session_state.mcp_clients
    
    # IDR MCP Server (incident management only)
    idr_client = MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="python",
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
    
    # AWS API MCP Server
    aws_api_client = MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="uvx",
                args=["awslabs.aws-api-mcp-server@latest", "--region", AWS_REGION]
            )
        )
    )
    
    model = BedrockModel(model_id=BEDROCK_MODEL_ID)
    
    agent = Agent(
        model=model,
        tools=[idr_client, kb_client, aws_api_client],
        system_prompt=f"""You are an AWS incident remediation specialist.

**Available Tools:**

1. **IDR MCP Server** (incident management):
   - list_incidents: List incidents from DynamoDB
   - get_incident_details: Get specific incident info
   - update_incident_status: Update incident to RESOLVED (ONLY after verification)

2. **Bedrock KB Retrieval MCP Server** (runbooks):
   - retrieve: Search knowledge base ID {IDR_KB_ID} for remediation runbooks
   - Use this to get runbook content - DO NOT modify or summarize the runbook text

3. **AWS API MCP Server** (remediation):
   - call_aws: Execute AWS CLI commands
   - Use this to query metrics, get configurations, and apply changes

**Remediation Workflow:**

1. **Get the runbook**: Use retrieve tool to get the remediation runbook for the incident type
2. **Follow the runbook steps EXACTLY**: The runbook contains specific logic and conditions
3. **Execute each step**: Use call_aws to check status, get metrics, get current config
4. **Apply changes per runbook**: Follow the runbook's calculation logic (e.g., "increase by 20%")
5. **Verify the change**: Query the configuration again to confirm it changed
6. **Update incident**: ONLY if verification succeeds, call update_incident_status with detailed resolution notes

**Important:**
- The runbook contains dynamic logic (e.g., "IF usage > 80% THEN increase by 20%")
- You MUST follow the runbook's conditions and calculations
- Do NOT use hardcoded values - calculate based on current metrics and runbook instructions
- For runbook retrieval: Return the EXACT text, no modifications
- For remediation: Execute the runbook steps, verify success, then update status
- Resolution notes should include: what was changed, from what value to what value"""
    )
    
    mcp_clients = {'idr': idr_client, 'kb': kb_client, 'aws_api': aws_api_client}
    
    st.session_state.idr_agent = agent
    st.session_state.mcp_clients = mcp_clients
    
    return agent, mcp_clients

def show_pending_incidents():
    """Show pending incidents page"""
    st.title(":orange[Pending Incidents]")
    st.subheader(f":orange[Metric Summary as of] :blue[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]", divider=True)
    
    # Get incidents using agent (agent handles MCP client lifecycle automatically)
    agent = st.session_state.idr_agent
    
    # Get real incidents from DynamoDB via agent
    import boto3
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)
    
    try:
        response = table.scan(
            FilterExpression='incident_status = :status',
            ExpressionAttributeValues={':status': 'PENDING'}
        )
        incidents = response.get('Items', [])
    except Exception as e:
        st.error(f"Error loading incidents: {e}")
        incidents = []
    
    # Convert to DataFrame
    if incidents:
        incidents_data = []
        for inc in incidents:
            incidents_data.append({
                "pk": inc.get('pk', ''),
                "incident_id": inc.get('incident_id', ''),
                "incidentIdentifier": inc.get('incident_identifier', ''),
                "incidentType": inc.get('incident_type', ''),
                "incident_status": inc.get('incident_status', ''),
                "incident_time": inc.get('incident_time', ''),
                "alarm_name": inc.get('alarm_name', ''),
                "alarm_reason": inc.get('alarm_reason', '')
            })
        df = pd.DataFrame(incidents_data)
    else:
        df = pd.DataFrame(columns=["pk", "incident_id", "incidentIdentifier", "incidentType", "incident_status", "incident_time"])
    
    # KPIs
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
    
    # Get Runbook action
    if runbook_action:
        if selected_incident is None:
            col4.error("Please select an incident to get the runbook")
        else:
            with col4.status("Retrieving incident runbook..."):
                # Direct KB retrieval
                import boto3
                bedrock = boto3.client('bedrock-agent-runtime', region_name=AWS_REGION)
                response = bedrock.retrieve(
                    knowledgeBaseId=IDR_KB_ID,
                    retrievalQuery={'text': f"{selected_incident['incidentType']} remediation"},
                    retrievalConfiguration={'vectorSearchConfiguration': {'numberOfResults': 1}}
                )
                if response['retrievalResults']:
                    runbook_text = response['retrievalResults'][0]['content']['text']
                    # Format the text
                    runbook_text = runbook_text.replace("# Title", "**Title:**")
                    runbook_text = runbook_text.replace("## ", "\n\n**").replace(" ##", ":**")
                    runbook_text = runbook_text.replace(". 1.", ".\n\n1.")
                    runbook_text = runbook_text.replace(". 2.", ".\n\n2.")
                    runbook_text = runbook_text.replace(". 3.", ".\n\n3.")
                    runbook_text = runbook_text.replace(". 4.", ".\n\n4.")
                else:
                    runbook_text = "No runbook found"
                
                col4.markdown(f"***Runbook Instructions for {selected_incident['incident_id']}***")
                col4.markdown(runbook_text)
    # Remediate action
    if remediate_action:
        if selected_incident is None:
            col4.error("Please select an incident to auto-remediate")
        else:
            with col4.status("Remediating incident..."):
                # Direct AWS remediation
                import boto3
                
                col4.markdown(f"***Auto-remediation for {selected_incident['incident_id']}***")
                
                try:
                    rds = boto3.client('rds', region_name=AWS_REGION)
                    
                    # Step 1: Get current config
                    col4.markdown("**Step 1: Getting current configuration...**")
                    current_config = rds.describe_db_clusters(
                        DBClusterIdentifier=selected_incident['incidentIdentifier']
                    )['DBClusters'][0]['ServerlessV2ScalingConfiguration']
                    
                    current_min = current_config['MinCapacity']
                    current_max = current_config['MaxCapacity']
                    col4.markdown(f"✅ Current: MinCapacity={current_min}, MaxCapacity={current_max}")
                    
                    # Step 2: Calculate new value (20% increase, rounded to 0.5 increments)
                    col4.markdown("\n**Step 2: Calculating new MaxCapacity (20% increase)...**")
                    increase = current_max * 0.2
                    new_max = current_max + (round(increase / 0.5) * 0.5)  # Round to nearest 0.5
                    col4.markdown(f"✅ Calculated: {current_max} + 20% = {current_max + increase:.2f}, rounded to {new_max} ACU")
                    
                    # Step 3: Apply change
                    col4.markdown("\n**Step 3: Applying configuration change...**")
                    rds.modify_db_cluster(
                        DBClusterIdentifier=selected_incident['incidentIdentifier'],
                        ServerlessV2ScalingConfiguration={
                            'MinCapacity': current_min,
                            'MaxCapacity': new_max
                        },
                        ApplyImmediately=True
                    )
                    col4.markdown("✅ Modification initiated")
                    
                    # Step 4: Verify
                    import time
                    time.sleep(3)
                    col4.markdown("\n**Step 4: Verifying change...**")
                    
                    verify_config = rds.describe_db_clusters(
                        DBClusterIdentifier=selected_incident['incidentIdentifier']
                    )['DBClusters'][0]['ServerlessV2ScalingConfiguration']
                    
                    if verify_config['MaxCapacity'] == new_max:
                        col4.markdown(f"✅ Verified: MaxCapacity is now {new_max} ACU")
                        
                        # Step 5: Update incident status
                        col4.markdown("\n**Step 5: Updating incident status...**")
                        dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
                        table = dynamodb.Table(DYNAMODB_TABLE)
                        
                        table.update_item(
                            Key={
                                'pk': f"INCIDENT#{selected_incident['incident_id']}",
                                'sk': f"ALARM#{selected_incident.get('alarm_name', 'unknown')}"
                            },
                            UpdateExpression='SET incident_status = :status, resolution_notes = :notes, updated_at = :time',
                            ExpressionAttributeValues={
                                ':status': 'RESOLVED',
                                ':notes': f"Increased MaxCapacity from {current_max} to {new_max} ACU (20% increase)",
                                ':time': datetime.now().isoformat()
                            }
                        )
                        col4.success(f"✅ Incident resolved! MaxCapacity increased from {current_max} to {new_max} ACU")
                    else:
                        col4.warning(f"⚠️ Verification pending. Current MaxCapacity: {verify_config['MaxCapacity']}")
                        
                except Exception as e:
                    col4.error(f"❌ Error during remediation: {str(e)}")

def show_all_incidents():
    """Show all incidents page"""
    st.title(":orange[All Incidents]")
    st.subheader(f":orange[Incident History as of] :blue[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]", divider=True)
    
    # Get all incidents from DynamoDB directly
    import boto3
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)
    
    try:
        response = table.scan()
        incidents = response.get('Items', [])
    except Exception as e:
        st.error(f"Error loading incidents: {e}")
        incidents = []
    
    # Convert to DataFrame
    if incidents:
        incidents_data = []
        for inc in incidents:
            incidents_data.append({
                "incident_id": inc.get('incident_id', ''),
                "incidentIdentifier": inc.get('incident_identifier', ''),
                "incidentType": inc.get('incident_type', ''),
                "incident_status": inc.get('incident_status', ''),
                "incident_time": inc.get('incident_time', ''),
                "alarm_name": inc.get('alarm_name', ''),
                "created_at": inc.get('created_at', ''),
                "resolution": inc.get('resolution', '')
            })
        df = pd.DataFrame(incidents_data)
        
        # Sort by incident_time descending
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
    else:
        st.info("No incidents found")

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

def create_idr_agent():
    """Create IDR agent with MCP servers"""
    if 'idr_agent' in st.session_state and 'mcp_clients' in st.session_state:
        return st.session_state.idr_agent, st.session_state.mcp_clients
    
    # IDR MCP Server
    idr_client = MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="python",
                args=[os.path.join(os.path.dirname(__file__), "idr_mcp_server.py")],
                env={
                    "AWS_REGION": AWS_REGION,
                    "DYNAMODB_TABLE": DYNAMODB_TABLE,
                    "IDR_CLUSTER_ARN": IDR_CLUSTER_ARN,
                    "IDR_SECRET_ARN": IDR_SECRET_ARN,
                    "IDR_DATABASE_NAME": IDR_DATABASE_NAME
                }
            )
        )
    )
    
    # AWS API MCP Server
    aws_api_client = MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="uvx",
                args=["awslabs.aws-api-mcp-server@latest", "--region", AWS_REGION]
            )
        )
    )
    
    model = BedrockModel(model_id=BEDROCK_MODEL_ID)
    
    agent = Agent(
        model=model,
        tools=[idr_client, aws_api_client],
        system_prompt="""You are an AWS incident remediation specialist.

Use IDR MCP server tools:
- list_incidents: List incidents from DynamoDB
- get_incident_details: Get specific incident info
- search_kb_runbooks: Search for remediation runbooks
- update_incident_status: Update incident status to RESOLVED after remediation

Use AWS API MCP server tools to ACTUALLY execute remediation:
- call_aws or suggest_aws_commands: Execute AWS CLI commands
- For ACU incidents: Use 'rds modify-db-cluster' to increase MaxCapacity
- For other incidents: Follow the runbook steps using appropriate AWS API calls

CRITICAL: You MUST actually execute the AWS API calls, not just describe them.
After executing remediation, update the incident status to RESOLVED.

Only provide the final summary in your response."""
    )
    
    mcp_clients = {'idr': idr_client, 'aws_api': aws_api_client}
    
    st.session_state.idr_agent = agent
    st.session_state.mcp_clients = mcp_clients
    
    return agent, mcp_clients

def get_incidents_data(status="PENDING"):
    """Get incidents using agent"""
    agent = create_idr_agent()
    
    with st.session_state.idr_client, st.session_state.aws_api_client:
        response = agent(f"List all incidents with status {status}. Return only the raw data.")
        
        # Parse response to extract incident data
        # For now, return mock data structure
        return []

def main():
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
    
    # Sidebar
    with st.sidebar:
        st.image("https://d1.awsstatic.com/logos/aws-logo-lockups/poweredbyaws/PB_AWS_logo_RGB_stacked_REV_SQ.91cd4af40773cbfbd15577a3c2b8a346fe3e8fa2.png", width=120)
        st.subheader("IDR: Incident Detection & Remediation")
        st.caption("Powered by Amazon Aurora & Bedrock")
        st.divider()
        
        page = st.radio("Navigation", ["Pending Incidents", "All Incidents"], key="page_nav")
        
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

def show_pending_incidents():
    """Show pending incidents page"""
    st.title(":orange[Pending Incidents]")
    st.subheader(f":orange[Metric Summary as of] :blue[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]", divider=True)
    
    # Get incidents using agent (agent handles MCP client lifecycle automatically)
    agent = st.session_state.idr_agent
    
    # Get real incidents from DynamoDB via agent
    import boto3
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)
    
    try:
        response = table.scan(
            FilterExpression='incident_status = :status',
            ExpressionAttributeValues={':status': 'PENDING'}
        )
        incidents = response.get('Items', [])
    except Exception as e:
        st.error(f"Error loading incidents: {e}")
        incidents = []
    
    # Convert to DataFrame
    if incidents:
        incidents_data = []
        for inc in incidents:
            incidents_data.append({
                "pk": inc.get('pk', ''),
                "incident_id": inc.get('incident_id', ''),
                "incidentIdentifier": inc.get('incident_identifier', ''),
                "incidentType": inc.get('incident_type', ''),
                "incident_status": inc.get('incident_status', ''),
                "incident_time": inc.get('incident_time', ''),
                "alarm_name": inc.get('alarm_name', ''),
                "alarm_reason": inc.get('alarm_reason', '')
            })
        df = pd.DataFrame(incidents_data)
    else:
        df = pd.DataFrame(columns=["pk", "incident_id", "incidentIdentifier", "incidentType", "incident_status", "incident_time"])
    
    # KPIs
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
    
    # Get Runbook action
    if runbook_action:
        if selected_incident is None:
            col4.error("Please select an incident to get the runbook")
        else:
            with col4.status("Retrieving incident runbook..."):
                # Direct KB retrieval
                import boto3
                bedrock = boto3.client('bedrock-agent-runtime', region_name=AWS_REGION)
                response = bedrock.retrieve(
                    knowledgeBaseId=IDR_KB_ID,
                    retrievalQuery={'text': f"{selected_incident['incidentType']} remediation"},
                    retrievalConfiguration={'vectorSearchConfiguration': {'numberOfResults': 1}}
                )
                if response['retrievalResults']:
                    runbook_text = response['retrievalResults'][0]['content']['text']
                    # Format the text
                    runbook_text = runbook_text.replace("# Title", "**Title:**")
                    runbook_text = runbook_text.replace("## ", "\n\n**").replace(" ##", ":**")
                    runbook_text = runbook_text.replace(". 1.", ".\n\n1.")
                    runbook_text = runbook_text.replace(". 2.", ".\n\n2.")
                    runbook_text = runbook_text.replace(". 3.", ".\n\n3.")
                    runbook_text = runbook_text.replace(". 4.", ".\n\n4.")
                else:
                    runbook_text = "No runbook found"
                
                col4.markdown(f"***Runbook Instructions for {selected_incident['incident_id']}***")
                col4.markdown(runbook_text)
    # Remediate action
    if remediate_action:
        if selected_incident is None:
            col4.error("Please select an incident to auto-remediate")
        else:
            with col4.status("Remediating incident..."):
                # Direct AWS remediation
                import boto3
                
                col4.markdown(f"***Auto-remediation for {selected_incident['incident_id']}***")
                
                try:
                    rds = boto3.client('rds', region_name=AWS_REGION)
                    
                    # Step 1: Get current config
                    col4.markdown("**Step 1: Getting current configuration...**")
                    current_config = rds.describe_db_clusters(
                        DBClusterIdentifier=selected_incident['incidentIdentifier']
                    )['DBClusters'][0]['ServerlessV2ScalingConfiguration']
                    
                    current_min = current_config['MinCapacity']
                    current_max = current_config['MaxCapacity']
                    col4.markdown(f"✅ Current: MinCapacity={current_min}, MaxCapacity={current_max}")
                    
                    # Step 2: Calculate new value (20% increase, rounded to 0.5 increments)
                    col4.markdown("\n**Step 2: Calculating new MaxCapacity (20% increase)...**")
                    increase = current_max * 0.2
                    new_max = current_max + (round(increase / 0.5) * 0.5)  # Round to nearest 0.5
                    col4.markdown(f"✅ Calculated: {current_max} + 20% = {current_max + increase:.2f}, rounded to {new_max} ACU")
                    
                    # Step 3: Apply change
                    col4.markdown("\n**Step 3: Applying configuration change...**")
                    rds.modify_db_cluster(
                        DBClusterIdentifier=selected_incident['incidentIdentifier'],
                        ServerlessV2ScalingConfiguration={
                            'MinCapacity': current_min,
                            'MaxCapacity': new_max
                        },
                        ApplyImmediately=True
                    )
                    col4.markdown("✅ Modification initiated")
                    
                    # Step 4: Verify
                    import time
                    time.sleep(3)
                    col4.markdown("\n**Step 4: Verifying change...**")
                    
                    verify_config = rds.describe_db_clusters(
                        DBClusterIdentifier=selected_incident['incidentIdentifier']
                    )['DBClusters'][0]['ServerlessV2ScalingConfiguration']
                    
                    if verify_config['MaxCapacity'] == new_max:
                        col4.markdown(f"✅ Verified: MaxCapacity is now {new_max} ACU")
                        
                        # Step 5: Update incident status
                        col4.markdown("\n**Step 5: Updating incident status...**")
                        dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
                        table = dynamodb.Table(DYNAMODB_TABLE)
                        
                        table.update_item(
                            Key={
                                'pk': f"INCIDENT#{selected_incident['incident_id']}",
                                'sk': f"ALARM#{selected_incident.get('alarm_name', 'unknown')}"
                            },
                            UpdateExpression='SET incident_status = :status, resolution_notes = :notes, updated_at = :time',
                            ExpressionAttributeValues={
                                ':status': 'RESOLVED',
                                ':notes': f"Increased MaxCapacity from {current_max} to {new_max} ACU (20% increase)",
                                ':time': datetime.now().isoformat()
                            }
                        )
                        col4.success(f"✅ Incident resolved! MaxCapacity increased from {current_max} to {new_max} ACU")
                    else:
                        col4.warning(f"⚠️ Verification pending. Current MaxCapacity: {verify_config['MaxCapacity']}")
                        
                except Exception as e:
                    col4.error(f"❌ Error during remediation: {str(e)}")

def show_all_incidents():
    """Show all incidents page"""
    st.title(":orange[All Incidents]")
    st.subheader(f":orange[Incident History as of] :blue[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]", divider=True)
    
    # Get all incidents from DynamoDB directly
    import boto3
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)
    
    try:
        response = table.scan()
        incidents = response.get('Items', [])
    except Exception as e:
        st.error(f"Error loading incidents: {e}")
        incidents = []
    
    # Convert to DataFrame
    if incidents:
        incidents_data = []
        for inc in incidents:
            incidents_data.append({
                "incident_id": inc.get('incident_id', ''),
                "incidentIdentifier": inc.get('incident_identifier', ''),
                "incidentType": inc.get('incident_type', ''),
                "incident_status": inc.get('incident_status', ''),
                "incident_time": inc.get('incident_time', ''),
                "alarm_name": inc.get('alarm_name', ''),
                "created_at": inc.get('created_at', '')
            })
        df = pd.DataFrame(incidents_data)
        
        # Sort by incident_time descending
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
                "created_at": "Created At"
            },
            column_order=("incident_id", "incidentIdentifier", "incidentType", "incident_status", "incident_time", "alarm_name")
        )
        
        st.caption(f"Total incidents: {len(df)}")
    else:
        st.info("No incidents found")

if __name__ == "__main__":
    main()
