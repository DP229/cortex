"""
NeuronMesh Orchestrator - Multi-Agent Coordination

Provides multi-agent orchestration patterns:
- Sequential pipeline
- Parallel execution
- Hierarchical (manager + sub-agents)
- Debate/collaboration

Inspired by AutoGen's orchestration and Hermes Agent's sub-agent spawning.
"""

import asyncio
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

from cortex.agent import Agent, AgentResponse
from cortex.memory import Memory

logger = logging.getLogger(__name__)


class OrchestrationPattern(Enum):
    """Multi-agent orchestration patterns"""
    SEQUENTIAL = "sequential"     # Output → Next input
    PARALLEL = "parallel"        # Same input, aggregate results
    HIERARCHICAL = "hierarchical"  # Manager delegates to sub-agents
    DEBATE = "debate"            # Agents argue, arbitrator decides
    PIPELINE = "pipeline"        # Linear pipeline with gates


@dataclass
class AgentSpec:
    """Specification for an agent in orchestration"""
    name: str
    role: str  # "researcher", "writer", "reviewer", etc.
    instructions: str
    model: str = "llama3"
    tools_enabled: bool = True
    memory_enabled: bool = True


@dataclass
class OrchestratorResult:
    """Result from orchestration"""
    pattern: OrchestrationPattern
    duration_ms: int
    outputs: Dict[str, Any]
    agent_results: Dict[str, AgentResponse]
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern.value,
            "duration_ms": self.duration_ms,
            "outputs": self.outputs,
            "agent_count": len(self.agent_results),
            "errors": self.errors,
        }


class Orchestrator:
    """
    Multi-agent orchestrator.
    
    Coordinates multiple agents working together on complex tasks.
    
    Inspired by:
    - AutoGen's GroupChat
    - Hermes Agent's sub-agent spawning
    - CrewAI's crew patterns
    
    Example:
        orchestrator = Orchestrator()
        
        # Sequential pipeline
        result = await orchestrator.sequential(
            agents=[
                AgentSpec("researcher", "Research", "Find info about..."),
                AgentSpec("writer", "Write", "Based on research, write..."),
            ],
            initial_input="AI agents"
        )
        
        print(result.outputs["writer"])
    """
    
    def __init__(
        self,
        memory: Optional[Memory] = None,
        default_model: str = "llama3",
    ):
        self.memory = memory
        self.default_model = default_model
        self.agents: Dict[str, Agent] = {}
    
    def create_agent(self, spec: AgentSpec) -> Agent:
        """Create an agent from specification"""
        agent = Agent(
            name=spec.name,
            model=spec.model,
            memory=self.memory,
            config=None,
        )
        
        # Override system prompt with role
        agent.config.system_prompt = spec.instructions
        agent.config.tools_enabled = spec.tools_enabled
        agent.config.memory_enabled = spec.memory_enabled
        
        self.agents[spec.name] = agent
        return agent
    
    async def sequential(
        self,
        agents: List[AgentSpec],
        initial_input: str,
        stop_on_error: bool = True,
    ) -> OrchestratorResult:
        """
        Sequential orchestration: output from one agent feeds into the next.
        
        Pipeline: Input → Agent1 → Output1 → Agent2 → Output2 → ...
        """
        start_time = time.time()
        outputs = {}
        agent_results = {}
        errors = []
        
        current_input = initial_input
        
        for spec in agents:
            try:
                agent = self.create_agent(spec)
                
                logger.info(f"Sequential: Running {spec.name}")
                
                response = await agent.run_async(current_input)
                
                agent_results[spec.name] = response
                outputs[spec.name] = response.content
                
                if response.error:
                    errors.append(f"{spec.name}: {response.error}")
                    if stop_on_error:
                        break
                
                # Feed output to next agent
                current_input = response.content
                
            except Exception as e:
                logger.error(f"Sequential error in {spec.name}: {e}")
                errors.append(f"{spec.name}: {str(e)}")
                if stop_on_error:
                    break
        
        return OrchestratorResult(
            pattern=OrchestrationPattern.SEQUENTIAL,
            duration_ms=int((time.time() - start_time) * 1000),
            outputs=outputs,
            agent_results=agent_results,
            errors=errors,
        )
    
    async def parallel(
        self,
        agents: List[AgentSpec],
        input: str,
        aggregate: Optional[Callable[[List[str]], str]] = None,
    ) -> OrchestratorResult:
        """
        Parallel orchestration: all agents work on same input simultaneously.
        
        Pipeline: Input → [Agent1, Agent2, Agent3, ...] → Aggregate → Output
        """
        start_time = time.time()
        outputs = {}
        agent_results = {}
        errors = []
        
        # Run all agents concurrently
        async def run_agent(spec: AgentSpec) -> tuple[str, AgentResponse, Optional[str]]:
            try:
                agent = self.create_agent(spec)
                response = await agent.run_async(input)
                return spec.name, response, None
            except Exception as e:
                return spec.name, None, str(e)
        
        # Execute all in parallel
        tasks = [run_agent(spec) for spec in agents]
        results = await asyncio.gather(*tasks)
        
        for name, response, error in results:
            if error:
                errors.append(f"{name}: {error}")
            else:
                agent_results[name] = response
                outputs[name] = response.content
        
        # Aggregate results if aggregator provided
        final_output = None
        if aggregate and outputs:
            try:
                final_output = aggregate(list(outputs.values()))
                outputs["aggregate"] = final_output
            except Exception as e:
                errors.append(f"aggregate: {str(e)}")
        elif outputs:
            # Default: concatenate
            final_output = "\n\n".join(outputs.values())
            outputs["aggregate"] = final_output
        
        return OrchestratorResult(
            pattern=OrchestrationPattern.PARALLEL,
            duration_ms=int((time.time() - start_time) * 1000),
            outputs=outputs,
            agent_results=agent_results,
            errors=errors,
        )
    
    async def hierarchical(
        self,
        manager: AgentSpec,
        sub_agents: List[AgentSpec],
        input: str,
        collect_responses: bool = True,
    ) -> OrchestratorResult:
        """
        Hierarchical orchestration: manager delegates to sub-agents.
        
        Pipeline:
        Input → Manager → Delegate tasks → [SubAgent1, SubAgent2, ...]
                  ↓
              Synthesize ← Collect results
                  ↓
                Output
        """
        start_time = time.time()
        outputs = {}
        agent_results = {}
        errors = []
        
        # Step 1: Manager analyzes task
        logger.info("Hierarchical: Manager analyzing task")
        manager_agent = self.create_agent(manager)
        manager_response = await manager_agent.run_async(
            f"Task: {input}\n\nAnalyze this task and break it down into subtasks for specialized agents."
        )
        
        if manager_response.error:
            errors.append(f"manager: {manager_response.error}")
            return OrchestratorResult(
                pattern=OrchestrationPattern.HIERARCHICAL,
                duration_ms=int((time.time() - start_time) * 1000),
                outputs={},
                agent_results={},
                errors=errors,
            )
        
        agent_results["manager"] = manager_response
        outputs["manager_analysis"] = manager_response.content
        
        # Step 2: Run sub-agents in parallel
        logger.info(f"Hierarchical: Running {len(sub_agents)} sub-agents")
        
        async def run_sub_agent(spec: AgentSpec) -> tuple[str, AgentResponse, Optional[str]]:
            try:
                agent = self.create_agent(spec)
                # Include manager's analysis in sub-agent prompt
                enhanced_input = f"{manager_response.content}\n\nYour specific task: {spec.role}"
                response = await agent.run_async(enhanced_input)
                return spec.name, response, None
            except Exception as e:
                return spec.name, None, str(e)
        
        tasks = [run_sub_agent(spec) for spec in sub_agents]
        results = await asyncio.gather(*tasks)
        
        for name, response, error in results:
            if error:
                errors.append(f"{name}: {error}")
            else:
                agent_results[name] = response
                outputs[f"subagent_{name}"] = response.content
        
        # Step 3: Manager synthesizes results
        if collect_responses and agent_results:
            logger.info("Hierarchical: Manager synthesizing results")
            
            synthesis_input = f"Original task: {input}\n\n"
            synthesis_input += "Sub-agent results:\n" + "\n\n".join([
                f"- {name}: {r.content[:500]}"
                for name, r in agent_results.items()
                if name != "manager"
            ])
            
            synthesis_response = await manager_agent.run_async(
                synthesis_input + "\n\nSynthesize the sub-agent results into a coherent response."
            )
            
            agent_results["synthesis"] = synthesis_response
            outputs["synthesis"] = synthesis_response.content
        
        return OrchestratorResult(
            pattern=OrchestrationPattern.HIERARCHICAL,
            duration_ms=int((time.time() - start_time) * 1000),
            outputs=outputs,
            agent_results=agent_results,
            errors=errors,
        )
    
    async def debate(
        self,
        agents: List[AgentSpec],
        proposition: str,
        rounds: int = 2,
        arbitrator: Optional[AgentSpec] = None,
    ) -> OrchestratorResult:
        """
        Debate orchestration: agents argue, arbitrator decides.
        
        Pipeline:
        Proposition → [Agent1 argues FOR, Agent2 argues AGAINST]
                      ↓
                   Rounds of debate
                      ↓
                   Arbitrator decides winner
        """
        start_time = time.time()
        outputs = {}
        agent_results = {}
        errors = []
        
        if len(agents) < 2:
            raise ValueError("Debate requires at least 2 agents")
        
        if arbitrator is None:
            arbitrator = AgentSpec(
                name="arbitrator",
                role="judge",
                instructions="You are a fair judge. Evaluate the arguments and decide which side makes the stronger case.",
            )
        
        # Create debate agents
        debate_agents = []
        for i, spec in enumerate(agents[:2]):
            agent = self.create_agent(spec)
            # Add debate instructions
            stance = "FOR" if i == 0 else "AGAINST"
            agent.config.system_prompt = (
                f"{spec.instructions}\n\n"
                f"Argue {stance} the proposition. "
                f"Present clear, logical arguments."
            )
            debate_agents.append((f"debater_{i}", agent, stance))
        
        # Create arbitrator
        arb_agent = self.create_agent(arbitrator)
        
        # Debate rounds
        debate_history = []
        
        for round_num in range(rounds):
            logger.info(f"Debate: Round {round_num + 1}")
            
            round_arguments = {}
            
            for name, agent, stance in debate_agents:
                # Build context from previous rounds
                context = f"Proposition: {proposition}\n\n"
                if debate_history:
                    context += "Previous arguments:\n" + "\n".join(debate_history) + "\n\n"
                context += f"Argue {stance} the proposition."
                
                response = await agent.run_async(context)
                
                if response.error:
                    errors.append(f"{name}: {response.error}")
                else:
                    round_text = f"[{stance}] {name}: {response.content}"
                    debate_history.append(round_text)
                    round_arguments[name] = response.content
                    agent_results[f"{name}_round_{round_num}"] = response
            
            outputs[f"round_{round_num}"] = round_arguments
        
        outputs["debate_history"] = debate_history
        
        # Arbitrator makes final decision
        logger.info("Debate: Arbitrator deciding")
        
        arb_input = (
            f"Proposition: {proposition}\n\n"
            f"Debate history:\n" + "\n\n".join(debate_history) +
            "\n\nWho makes the stronger argument? Provide your verdict and reasoning."
        )
        
        arb_response = await arb_agent.run_async(arb_input)
        agent_results["arbitrator"] = arb_response
        outputs["verdict"] = arb_response.content
        
        return OrchestratorResult(
            pattern=OrchestrationPattern.DEBATE,
            duration_ms=int((time.time() - start_time) * 1000),
            outputs=outputs,
            agent_results=agent_results,
            errors=errors,
        )
    
    def sync_sequential(
        self,
        agents: List[AgentSpec],
        initial_input: str,
        stop_on_error: bool = True,
    ) -> OrchestratorResult:
        """Synchronous version of sequential"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return asyncio.get_event_loop().run_until_complete(
                self.sequential(agents, initial_input, stop_on_error)
            )
        else:
            return asyncio.run(self.sequential(agents, initial_input, stop_on_error))
    
    def sync_parallel(
        self,
        agents: List[AgentSpec],
        input: str,
        aggregate: Optional[Callable[[List[str]], str]] = None,
    ) -> OrchestratorResult:
        """Synchronous version of parallel"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return asyncio.get_event_loop().run_until_complete(
                self.parallel(agents, input, aggregate)
            )
        else:
            return asyncio.run(self.parallel(agents, input, aggregate))


# === Convenience Functions ===

def create_research_pipeline(model: str = "llama3") -> Orchestrator:
    """Create a research pipeline: researcher → analyzer → writer"""
    orchestrator = Orchestrator(default_model=model)
    return orchestrator


def create_code_review_team(model: str = "codellama") -> Orchestrator:
    """Create a code review team: reviewer → tester → security"""
    orchestrator = Orchestrator(default_model=model)
    return orchestrator
