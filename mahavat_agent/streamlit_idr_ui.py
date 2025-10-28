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
from datetime import datetime
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp import StdioServerParameters, stdio_client

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
                runbook_response = agent(
                    f"""TASK: Retrieve the EXACT runbook text for {selected_incident['incidentType']} incident.

STEPS:
1. Call the 'retrieve' tool with:
   - knowledge_base_id: {IDR_KB_ID}
   - query: "{selected_incident['incidentType']} remediation runbook"
   - max_results: 1

2. Extract the 'text' field from the first result

3. Return ONLY that text content - NO summary, NO explanation, NO modifications

CRITICAL: Your response must be ONLY the raw runbook markdown text from the retrieve tool result."""
                )
                
                col4.markdown(f"***Runbook Instructions for {selected_incident['incident_id']}***")
                col4.markdown(runbook_response)
    
    # Remediate action
    if remediate_action:
        if selected_incident is None:
            col4.error("Please select an incident to auto-remediate")
        else:
            with col4.status("Remediating incident..."):
                remediation_response = agent(
                    f"""Remediate {selected_incident['incidentType']} incident for {selected_incident['incidentIdentifier']}.

**Incident Details:**
- ID: {selected_incident['incident_id']}
- Type: {selected_incident['incidentType']}
- Identifier: {selected_incident['incidentIdentifier']}
- Reason: {selected_incident['alarm_reason']}

**Remediation Process:**

1. **Get the runbook**: Use retrieve tool to search knowledge base {IDR_KB_ID} for "{selected_incident['incidentType']} remediation runbook"

2. **Follow the runbook steps EXACTLY**: 
   - The runbook contains specific conditions (e.g., "IF usage > 80% THEN increase by 20%")
   - Execute each step using call_aws commands
   - Follow the runbook's calculation logic precisely

3. **Verify the change**: Query the configuration again to confirm it was applied

4. **Update incident status**: ONLY if verification succeeds, call update_incident_status with detailed resolution notes including what changed and the values

Provide clear summary showing:
- What the runbook instructed
- What was the current state
- What changes were made
- Verification results"""
                )
                
                col4.markdown(f"***Status of auto remediation for {selected_incident['incident_id']}***")
                col4.markdown(remediation_response)
                
                # Check if incident was actually resolved
                import boto3
                dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
                table = dynamodb.Table(DYNAMODB_TABLE)
                query_response = table.query(
                    KeyConditionExpression='pk = :pk',
                    ExpressionAttributeValues={':pk': f'INCIDENT#{selected_incident["incident_id"]}'}
                )
                
                if query_response['Items']:
                    status = query_response['Items'][0].get('incident_status', 'PENDING')
                    if status == 'RESOLVED':
                        col4.success("✅ Remediation completed and verified!")
                    else:
                        col4.warning("⚠️ Remediation attempted but not marked as resolved. Check verification results above.")

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
                runbook_response = agent(
                    f"""TASK: Retrieve the EXACT runbook text for {selected_incident['incidentType']} incident.

STEPS:
1. Call the 'retrieve' tool with:
   - knowledge_base_id: {IDR_KB_ID}
   - query: "{selected_incident['incidentType']} remediation runbook"
   - max_results: 1

2. Extract the 'text' field from the first result

3. Return ONLY that text content - NO summary, NO explanation, NO modifications

CRITICAL: Your response must be ONLY the raw runbook markdown text from the retrieve tool result."""
                )
                
                # Extract only text content, skip tool invocations
                if isinstance(runbook_response, str):
                    import re
                    # Remove all tool invocation patterns
                    clean_response = runbook_response
                    # Remove multi-line invoke tags
                    clean_response = re.sub(r'<invoke[^>]*>.*?</invoke>', '', clean_response, flags=re.DOTALL)
                    # Remove single-line invoke tags
                    clean_response = re.sub(r'<invoke[^>]*>', '', clean_response)
                    # Remove any remaining XML-like tags
                    clean_response = re.sub(r'<[^>]+>', '', clean_response)
                    clean_response = clean_response.strip()
                else:
                    clean_response = str(runbook_response)
                
                col4.markdown(f"***Runbook Instructions for {selected_incident['incident_id']}***")
                col4.markdown(clean_response)
    
    # Remediate action
    if remediate_action:
        if selected_incident is None:
            col4.error("Please select an incident to auto-remediate")
        else:
            with col4.status("Remediating incident..."):
                # Use agent with AWS API MCP server (call_aws tool)
                remediation_response = agent(
                    f"""Remediate {selected_incident['incidentType']} incident for cluster {selected_incident['incidentIdentifier']}.

**Steps:**
1. Use call_aws to get current ServerlessV2ScalingConfiguration:
   aws rds describe-db-clusters --db-cluster-identifier {selected_incident['incidentIdentifier']} --region us-west-2 --query "DBClusters[0].ServerlessV2ScalingConfiguration"

2. Calculate new MaxCapacity (add 0.5 to current value)

3. Use call_aws to modify the cluster:
   aws rds modify-db-cluster --db-cluster-identifier {selected_incident['incidentIdentifier']} --region us-west-2 --serverless-v2-scaling-configuration MinCapacity=<current>,MaxCapacity=<new> --apply-immediately

4. Confirm the change was applied

Provide summary: "Increased MaxCapacity from X to Y ACU"
"""
                )
                
                # Clean response - remove tool invocation tags
                if isinstance(remediation_response, str):
                    import re
                    clean_response = remediation_response
                    # Remove call_aws tags and content
                    clean_response = re.sub(r'<call_aws>.*?</call_aws>', '[AWS Command Executed]', clean_response, flags=re.DOTALL)
                    # Remove other invoke tags
                    clean_response = re.sub(r'<invoke[^>]*>.*?</invoke>', '', clean_response, flags=re.DOTALL)
                    clean_response = re.sub(r'<invoke[^>]*>', '', clean_response)
                    clean_response = clean_response.strip()
                else:
                    clean_response = str(remediation_response)
                
                # Update incident status
                import boto3
                dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
                table = dynamodb.Table(DYNAMODB_TABLE)
                query_response = table.query(
                    KeyConditionExpression='pk = :pk',
                    ExpressionAttributeValues={':pk': f'INCIDENT#{selected_incident["incident_id"]}'}
                )
                
                if query_response['Items']:
                    sk = query_response['Items'][0]['sk']
                    table.update_item(
                        Key={'pk': f'INCIDENT#{selected_incident["incident_id"]}', 'sk': sk},
                        UpdateExpression='SET incident_status = :status, updated_at = :updated_at',
                        ExpressionAttributeValues={
                            ':status': 'RESOLVED',
                            ':updated_at': datetime.now().isoformat()
                        }
                    )
                
                col4.markdown(f"***Status of auto remediation for {selected_incident['incident_id']}***")
                col4.markdown(clean_response)
                col4.success("Remediation completed!")

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
