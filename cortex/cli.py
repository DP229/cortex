"""
Cortex CLI - Enhanced Command Line Interface

Provides a complete CLI for Cortex:
- Agent creation and execution
- Memory management
- Knowledge base operations
- Configuration management
- Interactive mode

Run:
    cortex --help
"""

import os
import sys
import json
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cortex import (
    Memory, Brain,
    Orchestrator, AgentSpec,
    create_agent, create_kb_agent,
    ModelProvider,
    KnowledgeBase,
)
from cortex.config import CortexConfig
from cortex.ingest import IngestPipeline
from cortex.query_agent import QueryAgent
from cortex.render import OutputRenderer


@dataclass
class CLIConfig:
    """CLI configuration"""
    model: str = "llama3"
    memory_enabled: bool = True
    tools_enabled: bool = True
    verbose: bool = False
    json_output: bool = False
    color: bool = True


class CortexCLI:
    """Cortex Command Line Interface"""
    
    def __init__(self, config: Optional[CLIConfig] = None):
        self.config = config or CLIConfig()
        self.memory = None
        self.agent = None
        self.brain = Brain()
    
    def _get_kb(self) -> KnowledgeBase:
        """Get or create a knowledge base from config"""
        config = CortexConfig.load()
        memory = Memory(storage_path=config.config_dir)
        return KnowledgeBase(
            wiki_path=config.wiki.path,
            raw_path=config.wiki.raw_path,
            memory=memory,
        )
    
    # === Agent Commands ===
    
    def cmd_agent_create(self, name: str, model: str = None, 
                        instructions: str = None) -> Dict[str, Any]:
        """Create a new agent"""
        model = model or self.config.model
        instructions = instructions or "You are a helpful AI assistant."
        
        self.agent = create_agent(
            name=name,
            model=model,
            instructions=instructions,
            memory=self.config.memory_enabled,
            tools=self.config.tools_enabled,
        )
        
        if not self.config.json_output:
            print(f"✅ Created agent: {name}")
            print(f"   Model: {model}")
            print(f"   Memory: {'enabled' if self.config.memory_enabled else 'disabled'}")
        
        return {"name": name, "model": model, "status": "created"}
    
    def cmd_agent_run(self, prompt: str) -> Dict[str, Any]:
        """Run agent with prompt"""
        if not self.agent:
            self.agent = create_agent(
                model=self.config.model,
                memory=self.config.memory_enabled,
            )
        
        if self.config.verbose:
            print(f"📝 Prompt: {prompt[:100]}...")
        
        start = time.time()
        response = self.agent.run(prompt)
        duration = int((time.time() - start) * 1000)
        
        if self.config.json_output:
            return {
                "content": response.content,
                "latency_ms": duration,
                "cost": response.cost,
                "turns": len(response.turns),
            }
        
        print("\n" + "=" * 60)
        print("🤖 Response:")
        print("=" * 60)
        print(response.content)
        print("=" * 60)
        print(f"⏱️  Latency: {duration}ms | 💰 Cost: ${response.cost:.4f}")
        
        return {"content": response.content, "latency_ms": duration}
    
    def cmd_agent_chat(self):
        """Interactive chat mode"""
        print("\n🎭 Entering chat mode. Type 'exit' to quit.\n")
        
        if not self.agent:
            self.agent = create_agent(
                model=self.config.model,
                memory=self.config.memory_enabled,
            )
        
        while True:
            try:
                prompt = input("👤 You: ")
                if prompt.lower() in ['exit', 'quit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                if not prompt.strip():
                    continue
                
                response = self.agent.run(prompt)
                print(f"\n🤖 Agent: {response.content}\n")
                
            except (KeyboardInterrupt, EOFError):
                print("\n👋 Goodbye!")
                break
    
    # === Memory Commands ===
    
    def cmd_memory_list(self) -> Dict[str, Any]:
        """List memory statistics"""
        if not self.memory:
            self.memory = Memory()
        
        stats = self.memory.get_stats()
        
        if self.config.json_output:
            return stats
        
        print("\n📊 Memory Statistics:")
        print(f"   Short-term: {stats['stm_size']}")
        print(f"   Working: {stats['working_size']}")
        print(f"   Long-term: {stats['ltm_size']}")
        print(f"   Total: {stats['total_memories']}")
        
        return stats
    
    def cmd_memory_add(self, content: str, entry_type: str = "fact",
                       importance: float = 0.5) -> Dict[str, Any]:
        """Add memory"""
        if not self.memory:
            self.memory = Memory()
        
        entry = self.memory.add(
            content=content,
            entry_type=entry_type,
            importance=importance,
        )
        
        if not self.config.json_output:
            print(f"✅ Added memory: {entry.id}")
            print(f"   Type: {entry_type}")
            print(f"   Importance: {importance}")
        
        return {"id": entry.id, "status": "added"}
    
    def cmd_memory_search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Search memory"""
        if not self.memory:
            self.memory = Memory()
        
        results = self.memory.retrieve(query, limit=limit)
        
        if self.config.json_output:
            return {"results": [r.to_dict() for r in results]}
        
        if not results:
            print("❌ No results found")
            return {"results": []}
        
        print(f"\n🔍 Results for: '{query}'")
        for i, entry in enumerate(results, 1):
            print(f"\n{i}. [{entry.entry_type}] {entry.content[:100]}...")
            print(f"   Importance: {'⭐' * int(entry.importance * 5)}")
        
        return {"results": [r.content for r in results]}
    
    def cmd_memory_clear(self) -> Dict[str, Any]:
        """Clear all memories"""
        if not self.memory:
            self.memory = Memory()
        
        count = self.memory.get_stats()['total_memories']
        self.memory.clear()
        
        if not self.config.json_output:
            print(f"✅ Cleared {count} memories")
        
        return {"cleared": count, "status": "cleared"}
    
    # === Model Commands ===
    
    def cmd_model_list(self, provider: str = None) -> Dict[str, Any]:
        """List available models"""
        registry = self.brain.registry
        
        if provider:
            prov = ModelProvider(provider)
            models = registry.list(provider=prov)
        else:
            models = registry.list()
        
        if self.config.json_output:
            return {"models": [m.name for m in models]}
        
        print("\n🤖 Available Models:")
        for m in models:
            cost = f"${m.cost_per_1k:.4f}/1K" if m.cost_per_1k > 0 else "FREE"
            print(f"   {m.name:<30} [{m.provider.value:<10}] {cost}")
        
        return {"models": [m.name for m in models]}
    
    def cmd_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get model information"""
        model = self.brain.registry.get(model_name)
        
        if not model:
            return {"error": f"Model not found: {model_name}"}
        
        if self.config.json_output:
            return {
                "name": model.name,
                "provider": model.provider.value,
                "context_length": model.context_length,
                "cost_per_1k": model.cost_per_1k,
                "capabilities": model.capabilities,
                "description": model.description,
            }
        
        print(f"\n📋 Model: {model.name}")
        print(f"   Provider: {model.provider.value}")
        print(f"   Context: {model.context_length} tokens")
        print(f"   Cost: ${model.cost_per_1k:.4f}/1K tokens")
        print(f"   Capabilities: {', '.join(model.capabilities)}")
        print(f"   Description: {model.description}")
        
        return {"name": model.name}
    
    # === Orchestrator Commands ===
    
    def cmd_orchestrate(self, pattern: str, task: str) -> Dict[str, Any]:
        """Run orchestration pattern"""
        orchestrator = Orchestrator()
        
        if pattern == "sequential":
            agents = [
                AgentSpec("researcher", "researcher", "Research and find key information."),
                AgentSpec("writer", "writer", "Write a clear summary based on research."),
            ]
            result = orchestrator.sync_sequential(agents, task)
        
        elif pattern == "parallel":
            agents = [
                AgentSpec("analyst1", "analyst", "Analyze from perspective A."),
                AgentSpec("analyst2", "analyst", "Analyze from perspective B."),
            ]
            result = orchestrator.sync_parallel(agents, task)
        
        else:
            return {"error": f"Unknown pattern: {pattern}"}
        
        if self.config.json_output:
            return result.to_dict()
        
        print(f"\n✅ Orchestration complete ({pattern})")
        print(f"   Duration: {result.duration_ms}ms")
        print(f"   Agents: {len(result.agent_results)}")
        
        for name, output in result.outputs.items():
            if name not in ['aggregate']:
                print(f"\n📄 {name}:")
                print(f"   {output[:200]}...")
        
        return {"pattern": pattern, "duration_ms": result.duration_ms}
    
    # === Config Commands ===
    
    def cmd_config_show(self) -> Dict[str, Any]:
        """Show current configuration"""
        config = {
            "model": self.config.model,
            "memory_enabled": self.config.memory_enabled,
            "tools_enabled": self.config.tools_enabled,
            "verbose": self.config.verbose,
            "json_output": self.config.json_output,
        }
        
        if self.config.json_output:
            return config
        
        print("\n⚙️  Current Configuration:")
        for key, value in config.items():
            print(f"   {key}: {value}")
        
        return config
    
    def cmd_config_set(self, key: str, value: str) -> Dict[str, Any]:
        """Set configuration value"""
        if key == "model":
            self.config.model = value
        elif key == "memory":
            self.config.memory_enabled = value.lower() == "true"
        elif key == "tools":
            self.config.tools_enabled = value.lower() == "true"
        elif key == "verbose":
            self.config.verbose = value.lower() == "true"
        elif key == "json":
            self.config.json_output = value.lower() == "true"
        else:
            return {"error": f"Unknown config key: {key}"}
        
        return {"key": key, "value": value, "status": "set"}
    
    # === Knowledge Base Commands ===
    
    def cmd_init(self, path: str) -> Dict[str, Any]:
        """Initialize a new knowledge base"""
        wiki_path = os.path.join(path, "wiki")
        raw_path = os.path.join(path, "raw")
        
        kb = self._get_kb()
        if kb.wiki_path != Path(wiki_path).resolve():
            kb = KnowledgeBase(wiki_path, raw_path, memory=kb.memory)
        
        config = CortexConfig.load()
        config.wiki.path = wiki_path
        config.wiki.raw_path = raw_path
        config.save()
        
        if not self.config.json_output:
            print(f"✅ Initialized knowledge base at {path}")
            print(f"   Wiki: {wiki_path}")
            print(f"   Raw:  {raw_path}")
        
        return {"status": "initialized", "path": path, "wiki": wiki_path, "raw": raw_path}
    
    def cmd_ingest(self, path: str, recursive: bool = True) -> Dict[str, Any]:
        """Ingest files into the knowledge base"""
        kb = self._get_kb()
        pipeline = IngestPipeline(kb)
        
        if os.path.isfile(path):
            results = [pipeline.ingest_file(path)]
        else:
            results = pipeline.ingest_directory(path, recursive=recursive)
        
        kb.generate_index()
        kb.update_backlinks()
        
        if not self.config.json_output:
            print(f"✅ Ingested {len(results)} files")
            for r in results:
                print(f"   📄 {r.title} → {r.wiki_path} ({r.word_count:,} words)")
        
        return {
            "status": "ingested",
            "files": len(results),
            "results": [
                {"title": r.title, "wiki_path": r.wiki_path, "words": r.word_count}
                for r in results
            ],
        }
    
    def cmd_ask(self, question: str) -> Dict[str, Any]:
        """Ask a question against the knowledge base"""
        kb = self._get_kb()
        config = CortexConfig.load()
        agent = create_kb_agent(model=config.llm.model, knowledgebase=kb, memory=kb.memory)
        query_agent = QueryAgent(agent, kb)
        
        result = query_agent.ask(question)
        
        if not self.config.json_output:
            print(f"\n🔍 Question: {question}")
            print(f"⏱️  Latency: {result.latency_ms}ms")
            print(f"📚 Sources: {', '.join(result.sources)}")
            if result.output_path:
                print(f"📄 Output: {result.output_path}")
            print(f"\n{'=' * 60}")
            print(result.answer)
            print(f"{'=' * 60}")
        
        return {
            "question": result.question,
            "answer": result.answer,
            "sources": result.sources,
            "output_path": result.output_path,
            "latency_ms": result.latency_ms,
        }
    
    def cmd_maintain(self, lint: bool = False, suggest: bool = False) -> Dict[str, Any]:
        """Run wiki maintenance"""
        kb = self._get_kb()
        
        results = {}
        
        kb.update_backlinks()
        results["backlinks_updated"] = True
        
        kb.generate_index()
        results["index_regenerated"] = True
        
        results["stats"] = kb.get_stats()
        
        if lint:
            from cortex.wiki_health import WikiHealthChecker
            checker = WikiHealthChecker(kb)
            issues = checker.check_all()
            results["health"] = checker.get_summary()
            results["health_issues"] = [
                {"type": i.type, "severity": i.severity, "article": i.article, "message": i.message}
                for i in issues
            ]
        
        if suggest:
            from cortex.wiki_health import WikiHealthChecker
            checker = WikiHealthChecker(kb)
            results["suggestions"] = checker.suggest_new_articles()
        
        if not self.config.json_output:
            stats = results["stats"]
            print("\n🔧 Wiki Maintenance Complete")
            print(f"   📊 Articles: {stats['total_articles']}")
            print(f"   📝 Words: {stats['total_words']:,}")
            print(f"   📂 Categories: {', '.join(stats['categories'])}")
            print(f"   🔗 Backlinks: {stats['backlink_count']}")
            print(f"   📁 Raw files: {stats['raw_files']}")
            
            if lint and "health" in results:
                health = results["health"]
                print("\n🏥 Health Check:")
                print(f"   ❌ Errors: {health['by_severity'].get('error', 0)}")
                print(f"   ⚠️  Warnings: {health['by_severity'].get('warning', 0)}")
                print(f"   ℹ️  Info: {health['by_severity'].get('info', 0)}")
                if results.get("health_issues"):
                    for issue in results["health_issues"][:10]:
                        icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue["severity"], "•")
                        print(f"   {icon} [{issue['type']}] {issue['article']}: {issue['message']}")
            
            if suggest and results.get("suggestions"):
                print("\n💡 Suggested new articles:")
                for s in results["suggestions"][:10]:
                    print(f"   • {s}")
        
        return results
    
    def cmd_render(self, input_path: str, format: str = "html") -> Dict[str, Any]:
        """Render wiki content"""
        kb = self._get_kb()
        config = CortexConfig.load()
        article = kb.get_article(input_path)
        
        if not article:
            return {"error": f"Article not found: {input_path}"}
        
        renderer = OutputRenderer(config.wiki.outputs_path)
        
        if format == "marp":
            output = renderer.render_marp(article.content)
        elif format == "pdf":
            output = renderer.render_pdf(article.content)
        elif format == "mermaid":
            output = renderer.render_mermaid(article.content)
        else:
            output = renderer.render_marp(article.content)
        
        if not self.config.json_output:
            print(f"✅ Rendered {input_path} → {output}")
        
        return {"status": "rendered", "input": input_path, "output": output, "format": format}
    
    def cmd_finetune(self, output: str, format: str = "qa", num_samples: int = 100) -> Dict[str, Any]:
        """Export wiki content as fine-tuning dataset"""
        kb = self._get_kb()
        from cortex.finetune import FineTuneExporter
        exporter = FineTuneExporter(kb)
        
        if format == "qa":
            path = exporter.export_qa_dataset(output, num_questions=num_samples)
        elif format == "completion":
            path = exporter.export_completion_dataset(output, num_samples=num_samples)
        elif format == "instruction":
            path = exporter.export_instruction_dataset(output, num_instructions=num_samples)
        else:
            return {"error": f"Unknown format: {format}"}
        
        if not self.config.json_output:
            print(f"✅ Exported {format} dataset → {path}")
            print(f"   Samples: {num_samples}")
        
        return {"status": "exported", "format": format, "output": path, "samples": num_samples}


def main():
    """Main CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Cortex - Local-First AI Knowledge Base Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    # Global options
    parser.add_argument("--model", "-m", default="llama3", help="Default model")
    parser.add_argument("--no-memory", action="store_true", help="Disable memory")
    parser.add_argument("--no-tools", action="store_true", help="Disable tools")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    parser.add_argument("--no-color", action="store_true", help="Disable colors")
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Agent commands
    agent_parser = subparsers.add_parser("agent", help="Agent operations")
    agent_sub = agent_parser.add_subparsers(dest="action")
    
    agent_create = agent_sub.add_parser("create", help="Create agent")
    agent_create.add_argument("name", help="Agent name")
    agent_create.add_argument("--model", "-m", help="Model name")
    agent_create.add_argument("--instructions", "-i", help="System instructions")
    
    agent_run = agent_sub.add_parser("run", help="Run agent")
    agent_run.add_argument("prompt", help="Prompt text")
    
    agent_sub.add_parser("chat", help="Interactive chat")
    
    # Memory commands
    memory_parser = subparsers.add_parser("memory", help="Memory operations")
    memory_sub = memory_parser.add_subparsers(dest="action")
    
    memory_sub.add_parser("list", help="List memory stats")
    
    memory_add = memory_sub.add_parser("add", help="Add memory")
    memory_add.add_argument("content", help="Memory content")
    memory_add.add_argument("--type", "-t", default="fact", help="Memory type")
    memory_add.add_argument("--importance", "-i", type=float, default=0.5, help="Importance 0-1")
    
    memory_search = memory_sub.add_parser("search", help="Search memory")
    memory_search.add_argument("query", help="Search query")
    memory_search.add_argument("--limit", "-l", type=int, default=5, help="Result limit")
    
    memory_sub.add_parser("clear", help="Clear all memories")
    
    # Model commands
    model_parser = subparsers.add_parser("model", help="Model operations")
    model_sub = model_parser.add_subparsers(dest="action")
    
    model_list = model_sub.add_parser("list", help="List models")
    model_list.add_argument("--provider", "-p", help="Filter by provider")
    
    model_info = model_sub.add_parser("info", help="Model info")
    model_info.add_argument("name", help="Model name")
    
    # Orchestrator commands
    orch_parser = subparsers.add_parser("orchestrate", help="Multi-agent orchestration")
    orch_parser.add_argument("pattern", choices=["sequential", "parallel"], help="Pattern")
    orch_parser.add_argument("task", help="Task description")
    
    # Config commands
    config_parser = subparsers.add_parser("config", help="Configuration")
    config_sub = config_parser.add_subparsers(dest="action")
    
    config_sub.add_parser("show", help="Show config")
    
    config_set = config_sub.add_parser("set", help="Set config")
    config_set.add_argument("key", help="Config key")
    config_set.add_argument("value", help="Config value")
    
    # Info command
    subparsers.add_parser("info", help="Show Cortex info")
    
    # Knowledge base commands
    init_parser = subparsers.add_parser("init", help="Initialize knowledge base")
    init_parser.add_argument("path", help="Path for knowledge base")
    
    ingest_parser = subparsers.add_parser("ingest", help="Ingest files into knowledge base")
    ingest_parser.add_argument("path", help="File or directory to ingest")
    ingest_parser.add_argument("--no-recursive", action="store_true", help="Don't recurse into subdirectories")
    
    ask_parser = subparsers.add_parser("ask", help="Ask a question against the knowledge base")
    ask_parser.add_argument("question", help="Your question")
    
    maintain_parser = subparsers.add_parser("maintain", help="Wiki maintenance")
    maintain_parser.add_argument("--lint", action="store_true", help="Run lint checks")
    maintain_parser.add_argument("--suggest", action="store_true", help="Suggest new articles")
    
    render_parser = subparsers.add_parser("render", help="Render wiki content")
    render_parser.add_argument("input", help="Article path to render")
    render_parser.add_argument("--format", "-f", default="marp", choices=["marp", "pdf", "mermaid"], help="Output format")
    
    finetune_parser = subparsers.add_parser("finetune", help="Export wiki as fine-tuning dataset")
    finetune_parser.add_argument("output", help="Output file path (JSONL)")
    finetune_parser.add_argument("--format", "-f", default="qa", choices=["qa", "completion", "instruction"], help="Dataset format")
    finetune_parser.add_argument("--num", "-n", type=int, default=100, help="Number of samples")
    
    args = parser.parse_args()
    
    # Create CLI
    config = CLIConfig(
        model=args.model,
        memory_enabled=not args.no_memory,
        tools_enabled=not args.no_tools,
        verbose=args.verbose,
        json_output=args.json,
        color=not args.no_color,
    )
    cli = CortexCLI(config)
    
    # Execute command
    result = None
    
    if args.command is None:
        parser.print_help()
        return
    
    elif args.command == "agent":
        if args.action == "create":
            result = cli.cmd_agent_create(args.name, args.model, args.instructions)
        elif args.action == "run":
            result = cli.cmd_agent_run(args.prompt)
        elif args.action == "chat":
            cli.cmd_agent_chat()
    
    elif args.command == "memory":
        if args.action == "list":
            result = cli.cmd_memory_list()
        elif args.action == "add":
            result = cli.cmd_memory_add(args.content, args.type, args.importance)
        elif args.action == "search":
            result = cli.cmd_memory_search(args.query, args.limit)
        elif args.action == "clear":
            result = cli.cmd_memory_clear()
    
    elif args.command == "model":
        if args.action == "list":
            result = cli.cmd_model_list(args.provider)
        elif args.action == "info":
            result = cli.cmd_model_info(args.name)
    
    elif args.command == "orchestrate":
        result = cli.cmd_orchestrate(args.pattern, args.task)
    
    elif args.command == "config":
        if args.action == "show":
            result = cli.cmd_config_show()
        elif args.action == "set":
            result = cli.cmd_config_set(args.key, args.value)
    
    elif args.command == "init":
        result = cli.cmd_init(args.path)
    
    elif args.command == "ingest":
        recursive = not getattr(args, 'no_recursive', False)
        result = cli.cmd_ingest(args.path, recursive=recursive)
    
    elif args.command == "ask":
        result = cli.cmd_ask(args.question)
    
    elif args.command == "maintain":
        result = cli.cmd_maintain(
            lint=getattr(args, 'lint', False),
            suggest=getattr(args, 'suggest', False),
        )
    
    elif args.command == "render":
        result = cli.cmd_render(args.input, format=getattr(args, 'format', 'marp'))
    
    elif args.command == "finetune":
        result = cli.cmd_finetune(
            args.output,
            format=getattr(args, 'format', 'qa'),
            num_samples=getattr(args, 'num', 100),
        )
    
    elif args.command == "info":
        print("""
╔══════════════════════════════════════════════════════════════╗
║              Cortex v0.1.0                               ║
║       Local-First AI Knowledge Base Agent                  ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  🧠 Intelligent Memory     - RAG, semantic search        ║
║  🔍 Wiki Knowledge Base  - Articles, backlinks, index  ║
║  🤖 Multi-Agent           - Sequential, parallel       ║
║  📄 Document Ingest       - PDF, web, code, data     ║
║  🔒 Local-First           - Zero data leaves machine   ║
║                                                              ║
║  Docs: https://github.com/dp229/cortex                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
        """)
    
    # Print JSON result if enabled
    if result and args.json:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
