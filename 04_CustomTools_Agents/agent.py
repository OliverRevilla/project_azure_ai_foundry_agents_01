import os
from dotenv import load_dotenv
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import ConnectedAgentTool, MessageRole, ListSortOrder, ToolSet, FunctionTool
from azure.identity import DefaultAzureCredential
from pathlib import Path

# Clear the console
os.system('cls' if os.name=='nt' else 'clear')

# Load environment variables from .env file
load_dotenv()
project_endpoint = os.getenv("PROJECT_ENDPOINT")
model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")


# Connect to the agents client
agents_client = AgentsClient(
     endpoint=project_endpoint,
     credential=DefaultAzureCredential(
         exclude_environment_credential=True, 
         exclude_managed_identity_credential=True
     ),
)

script_dir = Path(__file__).parent
triage_file_path = script_dir / 'triage_agent_instructions.txt'
team_file_path = script_dir / 'team_agent_instructions.txt'
effort_file_path = script_dir/ 'effort_agent_instructions.txt'
priority_file_path = script_dir / 'priority_agent_instructions.txt'

with open(priority_file_path, 'r') as priority_file:
    priority_instructions = priority_file.read()

with open(team_file_path, 'r') as team_file:
    team_instructions = team_file.read()

with open(effort_file_path, 'r') as effort_file:
    effort_instructions = effort_file.read()

with open(triage_file_path, 'r') as triage_file:
    triage_instructions = triage_file.read()


with agents_client:
    # Create an agent to prioritize support tickets
    priority_agent_name = "priority_agent"
    priority_agent_instructions = priority_instructions

    priority_agent = agents_client.create_agent(
        model=model_deployment,
        name=priority_agent_name,
        instructions=priority_agent_instructions
    )

    # Create an agent to assign tickets to the appropriate team
    team_agent_name = "team_agent"
    team_agent_instructions = team_instructions

    team_agent = agents_client.create_agent(
        model=model_deployment,
        name=team_agent_name,
        instructions=team_agent_instructions
    )

    # Create an agent to estimate effort for a support ticket
    effort_agent_name = "effort_agent"
    effort_agent_instructions = effort_instructions

    effort_agent = agents_client.create_agent(
        model=model_deployment,
        name=effort_agent_name,
        instructions=effort_agent_instructions
    )

    ##############################################################################

    # Create connected agent tools for the support agents
    priority_agent_tool = ConnectedAgentTool(
        id=priority_agent.id, 
        name=priority_agent_name, 
        description="Assess the priority of a ticket"
    )
        
    team_agent_tool = ConnectedAgentTool(
        id=team_agent.id, 
        name=team_agent_name, 
        description="Determines which team should take the ticket"
    )
        
    effort_agent_tool = ConnectedAgentTool(
        id=effort_agent.id, 
        name=effort_agent_name, 
        description="Determines the effort required to complete the ticket"
    )
    

    # Create an agent to triage support ticket processing by using connected agents
    triage_agent_name = "triage-agent"
    triage_agent_instructions = triage_instructions

    triage_agent = agents_client.create_agent(
        model=model_deployment,
        name=triage_agent_name,
        instructions=triage_agent_instructions,
        tools=[
            priority_agent_tool.definitions[0],
            team_agent_tool.definitions[0],
            effort_agent_tool.definitions[0]
        ]
    )    
    

    # Use the agents to triage a support issue
    print("Creating agent thread.")
    thread = agents_client.threads.create()  

    # Create the ticket prompt
    prompt = input("\nWhat's the support problem you need to resolve?: ")
        
    # Send a prompt to the agent
    message = agents_client.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=prompt,
    )   
        
    # Run the thread usng the primary agent
    print("\nProcessing agent thread. Please wait.")
    run = agents_client.runs.create_and_process(
        thread_id=thread.id, 
        agent_id=triage_agent.id)
            
    if run.status == "failed":
        print(f"Run failed: {run.last_error}")

    # Fetch and display messages
    messages = agents_client.messages.list(
        thread_id=thread.id, 
        order=ListSortOrder.ASCENDING
        )
    for message in messages:
        if message.text_messages:
            last_msg = message.text_messages[-1]
            print(f"{message.role}:\n{last_msg.text.value}\n")


    # Clean up
    print("Cleaning up agents:")
    agents_client.delete_agent(triage_agent.id)
    print("Deleted triage agent.")
    agents_client.delete_agent(priority_agent.id)
    print("Deleted priority agent.")
    agents_client.delete_agent(team_agent.id)
    print("Deleted team agent.")
    agents_client.delete_agent(effort_agent.id)
    print("Deleted effort agent.")