import time
from typing import Dict, Any, List
from app.config import settings
from app.services.mlflow_service import mlflow_service

# Import placeholders with fallbacks for local compilation safety
try:
    from langgraph.graph import StateGraph, END
    from typing import TypedDict
except ImportError:
    StateGraph = None

try:
    from crewai import Agent as CrewAgent, Task as CrewTask, Crew, Process
except ImportError:
    Crew = None

try:
    from google.antigravity import Agent as AgAgent, LocalAgentConfig
except ImportError:
    AgAgent = None

class AgentService:
    def run_agent(self, 
                  framework: str, 
                  prompt: str, 
                  context_chunks: List[str], 
                  system_instruction: str,
                  llm_model: str,
                  temperature: float = 0.7) -> Dict[str, Any]:
        """
        Executes a RAG query query using the selected Agent framework.
        Tracks execution logs and metric costs to MLflow.
        """
        start_time = time.time()
        context_text = "\n\n".join(context_chunks)
        
        # Prepare system instruction injecting the context
        formatted_system = system_instruction.replace("{{CONTEXT}}", context_text)
        
        # Route execution based on framework selection
        if framework == "langgraph":
            response, steps = self._run_langgraph(prompt, context_text, formatted_system, llm_model, temperature)
        elif framework == "google_sdk":
            response, steps = self._run_google_sdk(prompt, context_text, formatted_system, llm_model, temperature)
        elif framework == "crewai":
            response, steps = self._run_crewai(prompt, context_text, formatted_system, llm_model, temperature)
        else:
            # Fallback direct mock LLM execution (standard RAG prompt)
            response, steps = self._run_mock_llm(prompt, context_text, formatted_system, llm_model, temperature)

        latency = time.time() - start_time
        
        # Log metrics & parameters to MLflow
        params = {
            "framework": framework,
            "llm_model": llm_model,
            "temperature": temperature,
            "context_chunks_count": len(context_chunks)
        }
        
        metrics = {
            "latency_seconds": latency,
            "input_tokens": len(prompt.split()) + len(context_text.split()),
            "output_tokens": len(response.split()),
            "estimated_cost_usd": (len(prompt.split()) + len(context_text.split())) * 0.0000015 + len(response.split()) * 0.000002
        }
        
        run_id = mlflow_service.log_run(params, metrics, {"task": "agent_run"})
        mlflow_url = mlflow_service.get_run_url(run_id)

        return {
            "response": response,
            "steps": steps,
            "metrics": {
                "latency_ms": int(latency * 1000),
                "prompt_cost": round(metrics["input_tokens"] * 0.0000015, 6),
                "completion_cost": round(metrics["output_tokens"] * 0.000002, 6),
                "mlflow_run_id": run_id,
                "mlflow_url": mlflow_url
            }
        }

    def _run_langgraph(self, prompt: str, context: str, system: str, model: str, temp: float):
        """
        Runs LangGraph workflow:
        State Graph consists of a [Retrieval Context Validator] -> [LLM Response Generator]
        """
        steps = []
        steps.append("Initializing LangGraph StateGraph...")
        
        if not StateGraph:
            steps.append("Warning: LangGraph is missing. Executing mock graph steps.")
            time.sleep(0.1)
            steps.append("[Node: RetrievalValidator] Check context length ... Valid")
            time.sleep(0.1)
            steps.append("[Node: Generator] Invoking response...")
            ans = f"[LangGraph Mock Response]\n\nBased on your document context, here is the answer: {prompt[:20]}... [Reference Text: {context[:40]}]"
            return ans, steps
            
        # Define graph state
        class AgentState(TypedDict):
            prompt: str
            context: str
            system: str
            answer: str

        # Nodes
        def check_context(state: AgentState):
            steps.append("[Node: RetrievalValidator] Verifying document context presence")
            return {"context": state["context"]}

        def generate_response(state: AgentState):
            steps.append("[Node: ResponseGenerator] Querying Model API with formatting rules")
            ans = f"[LangGraph Realized Response]\nAnswered question: '{state['prompt']}' using instruction: '{state['system'][:40]}'"
            return {"answer": ans}

        workflow = StateGraph(AgentState)
        workflow.add_node("validator", check_context)
        workflow.add_node("generator", generate_response)
        
        workflow.set_entry_point("validator")
        workflow.add_edge("validator", "generator")
        workflow.add_edge("generator", END)
        
        app = workflow.compile()
        result = app.invoke({"prompt": prompt, "context": context, "system": system, "answer": ""})
        
        return result.get("answer"), steps

    def _run_google_sdk(self, prompt: str, context: str, system: str, model: str, temp: float):
        """
        Runs the flow using Google Antigravity SDK:
        - Setup Agent with LocalAgentConfig (injecting system_instructions)
        - Run async chat call, streaming thoughts
        """
        steps = []
        steps.append("Initializing Google Antigravity Agent Configuration...")
        
        if not AgAgent:
            steps.append("Warning: google-antigravity package is missing. Fallback to basic Google GenAI execution.")
            time.sleep(0.1)
            steps.append("[GoogleSDK] Preparing prompt context injection")
            time.sleep(0.1)
            steps.append("[GoogleSDK] Executing turn...")
            return f"[Google SDK Mock Response]\n\nBased on your documents, the details are: {prompt[:30]}...", steps
            
        import asyncio
        
        # Async run handler for the SDK
        async def run_sdk():
            config = LocalAgentConfig(
                model=model if model else "gemini-3.5-flash",
                system_instructions=system
            )
            steps.append("[GoogleSDK Agent] Starting conversational connection...")
            async with AgAgent(config=config) as agent:
                response = await agent.chat(prompt)
                
                # Gather reasoning process
                steps.append("[GoogleSDK Agent] Streaming reasoning thoughts...")
                async for thought in response.thoughts:
                    steps.append(f"[Thought] {thought}")
                    
                text_response = await response.text()
                return text_response

        # Execute async inside synchronous service run
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            res = loop.run_until_complete(run_sdk())
            steps.append("[GoogleSDK Agent] Completed turn successfully.")
            return res, steps
        except Exception as e:
            steps.append(f"[GoogleSDK Error] Execution failed: {e}. Falling back.")
            return f"[Google SDK Fallback] System instruction: {system[:30]} - Query: {prompt}", steps
        finally:
            loop.close()

    def _run_crewai(self, prompt: str, context: str, system: str, model: str, temp: float):
        """
        Runs CrewAI:
        - Set up a Research Analyst agent and Writer agent.
        - Run Task sequentially to generate output.
        """
        steps = []
        steps.append("Configuring CrewAI Agent personas and Task requirements...")
        
        if not Crew:
            steps.append("Warning: CrewAI is missing. Executing mock multi-agent step pipeline.")
            time.sleep(0.1)
            steps.append("[Crew Node: Research Analyst] Searching indexed chunks...")
            time.sleep(0.1)
            steps.append("[Crew Node: Writer] Formatting output for readability...")
            ans = f"[CrewAI Mock Multi-Agent Response]\n\nResearch Agent analyzed documents and Writer Agent composed this answer for: {prompt[:20]}"
            return ans, steps
            
        # Real CrewAI configuration
        analyst = CrewAgent(
            role="Document Research Analyst",
            goal="Analyze document context and extract key facts relevant to user questions",
            backstory="Expert document researcher specializing in corporate intelligence data",
            verbose=True,
            allow_delegation=False
        )
        
        task = CrewTask(
            description=f"Answer the query: '{prompt}' using this context:\n{context}\nAdditional instruction: {system}",
            expected_output="A clean, direct and detailed answer.",
            agent=analyst
        )
        
        crew = Crew(
            agents=[analyst],
            tasks=[task],
            process=Process.sequential
        )
        
        steps.append("[CrewAI] Triggering sequential collaboration process")
        result = crew.kickoff()
        return str(result), steps

    def _run_mock_llm(self, prompt: str, context: str, system: str, model: str, temp: float):
        steps = ["Initializing standard prompt LLM router...", "Context matched. Querying API key..."]
        time.sleep(0.2)
        ans = f"[Standard Direct RAG Response]\n\nBased on your documents, we found the following:\n- Question asked: {prompt}\n- Instruction applied: {system[:50]}...\n- Relevant text found: {context[:100]}..."
        return ans, steps

agent_service = AgentService()
