"""
NeuronMesh Tools - Claude Code-inspired Tool System

Based on patterns from:
- Claude Code (Anthropic) - Tool architecture
- AutoAgent (HKUDS) - Zero-code tool creation
- Hermes Agent (Nous Research) - Skill system
"""

import os
import subprocess
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """Tool categories like Claude Code"""
    FILE = "file"
    BASH = "bash"
    SEARCH = "search"
    WEB = "web"
    CODE = "code"
    MEMORY = "memory"
    AGENT = "agent"
    CUSTOM = "custom"


@dataclass
class ToolDefinition:
    """Definition of a tool for agent use"""
    name: str
    description: str
    category: ToolCategory
    parameters: Dict[str, Any]
    returns: str
    permission_level: str = "user_confirm"  # "auto", "user_confirm", "admin"
    examples: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    
    def to_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling schema"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self.parameters,
                "required": [p for p, v in self.parameters.items() if v.get("required", False)]
            }
        }


class ToolResult:
    """Result from a tool execution"""
    def __init__(
        self,
        success: bool,
        output: Any = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.output = output
        self.error = error
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }
    
    def __str__(self) -> str:
        if self.success:
            return str(self.output)
        return f"Error: {self.error}"


class BaseTool:
    """Base class for all tools"""
    
    definition: ToolDefinition
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.name = self.definition.name
        self.category = self.definition.category
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool - override in subclasses"""
        raise NotImplementedError
    
    def validate(self, **kwargs) -> Optional[str]:
        """Validate parameters - return error message if invalid"""
        return None
    
    def get_permission_level(self) -> str:
        return self.definition.permission_level


# === Built-in Tools ===

class BashTool(BaseTool):
    """Execute shell commands - inspired by Claude Code BashTool"""
    
    definition = ToolDefinition(
        name="bash",
        description="Execute a shell command and return the output. Use for file operations, git, npm, pip, etc.",
        category=ToolCategory.BASH,
        parameters={
            "command": {
                "type": "string",
                "description": "The shell command to execute",
                "required": True,
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 30)",
            },
            "working_dir": {
                "type": "string",
                "description": "Working directory for the command",
            },
        },
        returns="JSON with stdout, stderr, and exit_code",
        permission_level="user_confirm",
    )
    
    async def execute(
        self,
        command: str,
        timeout: int = 30,
        working_dir: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        try:
            import shlex
            cwd = working_dir or os.getcwd()
            cmd_parts = shlex.split(command)
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
            
            return ToolResult(
                success=result.returncode == 0,
                output={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.returncode,
                },
                metadata={"command": command, "cwd": cwd},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error=f"Command timed out after {timeout}s")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ReadFileTool(BaseTool):
    """Read file contents - inspired by Claude Code ReadTool"""
    
    definition = ToolDefinition(
        name="read_file",
        description="Read the contents of a file. Use for reading source code, configs, logs, etc.",
        category=ToolCategory.FILE,
        parameters={
            "path": {
                "type": "string",
                "description": "Path to the file to read",
                "required": True,
            },
            "max_lines": {
                "type": "integer",
                "description": "Maximum number of lines to read",
            },
            "offset": {
                "type": "integer",
                "description": "Line offset to start reading from",
            },
        },
        returns="File contents as string",
        permission_level="auto",
    )
    
    async def execute(
        self,
        path: str,
        max_lines: Optional[int] = None,
        offset: int = 0,
        **kwargs,
    ) -> ToolResult:
        try:
            with open(path, "r") as f:
                if offset > 0:
                    for _ in range(offset):
                        f.readline()
                
                content = f.read()
                
                if max_lines:
                    lines = content.split("\n")[:max_lines]
                    content = "\n".join(lines)
            
            return ToolResult(success=True, output=content, metadata={"path": path})
        except FileNotFoundError:
            return ToolResult(success=False, error=f"File not found: {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class WriteFileTool(BaseTool):
    """Write content to a file"""
    
    definition = ToolDefinition(
        name="write_file",
        description="Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
        category=ToolCategory.FILE,
        parameters={
            "path": {
                "type": "string",
                "description": "Path to the file to write",
                "required": True,
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
                "required": True,
            },
            "append": {
                "type": "boolean",
                "description": "Append to existing file instead of overwriting",
            },
        },
        returns="Success message with path",
        permission_level="user_confirm",
    )
    
    async def execute(
        self,
        path: str,
        content: str,
        append: bool = False,
        **kwargs,
    ) -> ToolResult:
        try:
            mode = "a" if append else "w"
            
            # Create directory if needed
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            
            with open(path, mode) as f:
                f.write(content)
            
            return ToolResult(
                success=True,
                output=f"Successfully wrote to {path}",
                metadata={"path": path, "bytes": len(content)},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GlobTool(BaseTool):
    """Search for files matching a pattern"""
    
    definition = ToolDefinition(
        name="glob",
        description="Find files matching a glob pattern. Use ** for recursive matching.",
        category=ToolCategory.FILE,
        parameters={
            "pattern": {
                "type": "string",
                "description": "Glob pattern (e.g., '*.py', '**/*.ts')",
                "required": True,
            },
            "root": {
                "type": "string",
                "description": "Root directory to search from",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results",
            },
        },
        returns="List of matching file paths",
        permission_level="auto",
    )
    
    async def execute(
        self,
        pattern: str,
        root: Optional[str] = None,
        max_results: int = 100,
        **kwargs,
    ) -> ToolResult:
        import glob as glob_module
        
        try:
            root_dir = root or os.getcwd()
            search_path = os.path.join(root_dir, pattern)
            
            matches = glob_module.glob(search_path, recursive=True)[:max_results]
            
            return ToolResult(
                success=True,
                output=matches,
                metadata={"pattern": pattern, "count": len(matches)},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GrepTool(BaseTool):
    """Search for text in files"""
    
    definition = ToolDefinition(
        name="grep",
        description="Search for text patterns in files. Supports regex.",
        category=ToolCategory.SEARCH,
        parameters={
            "pattern": {
                "type": "string",
                "description": "Search pattern (supports regex)",
                "required": True,
            },
            "path": {
                "type": "string",
                "description": "Directory or file to search in",
            },
            "file_pattern": {
                "type": "string",
                "description": "File glob pattern (e.g., '*.py')",
            },
            "context": {
                "type": "integer",
                "description": "Number of context lines around matches",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results",
            },
        },
        returns="List of matches with file:line:content",
        permission_level="auto",
    )
    
    async def execute(
        self,
        pattern: str,
        path: Optional[str] = None,
        file_pattern: Optional[str] = None,
        context: int = 0,
        max_results: int = 50,
        **kwargs,
    ) -> ToolResult:
        import re
        
        try:
            search_path = path or os.getcwd()
            results = []
            
            if file_pattern:
                import glob
                files = glob.glob(os.path.join(search_path, "**", file_pattern), recursive=True)
            else:
                files = [search_path] if os.path.isfile(search_path) else []
            
            for file_path in files:
                if not os.path.isfile(file_path):
                    continue
                
                try:
                    with open(file_path, "r") as f:
                        for i, line in enumerate(f, 1):
                            if re.search(pattern, line):
                                if context > 0:
                                    # Return context lines
                                    results.append(f"{file_path}:{i}: {line.rstrip()}")
                                else:
                                    results.append(f"{file_path}:{i}: {line.rstrip()}")
                                
                                if len(results) >= max_results:
                                    break
                except (UnicodeDecodeError, PermissionError):
                    continue
                
                if len(results) >= max_results:
                    break
            
            return ToolResult(
                success=True,
                output=results,
                metadata={"pattern": pattern, "count": len(results)},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class WebSearchTool(BaseTool):
    """Search the web"""
    
    definition = ToolDefinition(
        name="web_search",
        description="Search the web for information. Use for research, finding docs, etc.",
        category=ToolCategory.WEB,
        parameters={
            "query": {
                "type": "string",
                "description": "Search query",
                "required": True,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results",
            },
        },
        returns="Search results with titles, URLs, and snippets",
        permission_level="auto",
    )
    
    async def execute(
        self,
        query: str,
        max_results: int = 5,
        **kwargs,
    ) -> ToolResult:
        try:
            # DuckDuckGo HTML search (no API key needed)
            import urllib.request
            import urllib.parse
            import re
            
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; Cortex/1.0)"
            })
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            
            # Parse results
            results = []
            for match in re.finditer(
                r'class="result__title">.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
                r'class="result__snippet">(.*?)</(?:td|div)',
                html, re.DOTALL
            ):
                url = match.group(1)
                title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                snippet = re.sub(r'<[^>]+>', '', match.group(3)).strip()
                results.append({"title": title, "url": url, "snippet": snippet})
                if len(results) >= max_results:
                    break
            
            if not results:
                return ToolResult(
                    success=True,
                    output=f"No results found for: {query}",
                    metadata={"query": query},
                )
            
            output = f"Search results for: {query}\n\n"
            for i, r in enumerate(results, 1):
                output += f"{i}. **{r['title']}**\n   URL: {r['url']}\n   {r['snippet']}\n\n"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={"query": query, "count": len(results)},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Web search failed: {e}")


class MemorySearchTool(BaseTool):
    """Search agent memory"""
    
    definition = ToolDefinition(
        name="memory_search",
        description="Search the agent's long-term memory for relevant information.",
        category=ToolCategory.MEMORY,
        parameters={
            "query": {
                "type": "string",
                "description": "Search query",
                "required": True,
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results",
            },
        },
        returns="Relevant memories",
        permission_level="auto",
    )
    
    def __init__(self, memory=None, **kwargs):
        super().__init__(**kwargs)
        self.memory = memory
    
    async def execute(
        self,
        query: str,
        limit: int = 5,
        **kwargs,
    ) -> ToolResult:
        try:
            if not self.memory:
                return ToolResult(
                    success=True,
                    output="No memory configured",
                    metadata={"query": query},
                )
            
            results = self.memory.retrieve(query, limit=limit)
            
            return ToolResult(
                success=True,
                output=[r.content for r in results],
                metadata={"query": query, "count": len(results)},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class MemoryStoreTool(BaseTool):
    """Store information in agent memory"""
    
    definition = ToolDefinition(
        name="memory_store",
        description="Store important information in the agent's long-term memory.",
        category=ToolCategory.MEMORY,
        parameters={
            "content": {
                "type": "string",
                "description": "Content to store",
                "required": True,
            },
            "entry_type": {
                "type": "string",
                "description": "Type of memory (fact, preference, skill)",
            },
            "importance": {
                "type": "number",
                "description": "Importance score 0.0-1.0",
            },
        },
        returns="Success message with memory ID",
        permission_level="auto",
    )
    
    def __init__(self, memory=None, **kwargs):
        super().__init__(**kwargs)
        self.memory = memory
    
    async def execute(
        self,
        content: str,
        entry_type: str = "fact",
        importance: float = 0.5,
        **kwargs,
    ) -> ToolResult:
        try:
            if not self.memory:
                return ToolResult(success=True, output="No memory configured")
            
            entry = self.memory.add(
                content=content,
                entry_type=entry_type,
                importance=importance,
            )
            
            return ToolResult(
                success=True,
                output=f"Stored memory: {entry.id}",
                metadata={"id": entry.id, "type": entry_type},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


# === Tool Registry ===

class ToolRegistry:
    """
    Registry of all available tools - inspired by Claude Code's tool system
    """
    
    def __init__(self, wiki_path: str = None, raw_path: str = None):
        self._tools: Dict[str, BaseTool] = {}
        self._definitions: Dict[str, ToolDefinition] = {}
        self._categories: Dict[ToolCategory, List[str]] = {cat: [] for cat in ToolCategory}
        self._wiki_path = wiki_path
        self._raw_path = raw_path
    
    def register(self, tool: BaseTool, name: Optional[str] = None):
        """Register a tool"""
        tool_name = name or tool.definition.name
        self._tools[tool_name] = tool
        self._definitions[tool_name] = tool.definition
        self._categories[tool.definition.category].append(tool_name)
        
        # Register aliases
        for alias in tool.definition.aliases:
            self._tools[alias] = tool
    
    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        return self._tools.get(name)
    
    def get_schema(self) -> List[Dict[str, Any]]:
        """Get OpenAI function calling schemas for all tools"""
        return [d.to_schema() for d in self._definitions.values()]
    
    def get_by_category(self, category: ToolCategory) -> List[BaseTool]:
        """Get all tools in a category"""
        tool_names = self._categories.get(category, [])
        return [self._tools[name] for name in tool_names if name in self._tools]
    
    def list_tools(self) -> List[ToolDefinition]:
        """List all tool definitions"""
        return list(self._definitions.values())
    
    async def execute(
        self,
        name: str,
        parameters: Dict[str, Any],
        permission_callback=None,
    ) -> ToolResult:
        """Execute a tool by name with permission and path validation"""
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Tool not found: {name}")
        
        # Check permission level
        perm_level = tool.get_permission_level()
        if permission_callback and not permission_callback(perm_level):
            return ToolResult(
                success=False,
                error=f"Permission denied: {perm_level} access required for {name}",
            )
        
        # Security: block bash if disabled
        if isinstance(tool, BashTool):
            try:
                from cortex.config import CortexConfig
                config = CortexConfig.load()
                if not config.security.bash_enabled:
                    return ToolResult(
                        success=False,
                        error="Bash execution is disabled in configuration",
                    )
            except Exception:
                pass  # Config not available, allow execution
        
        # Validate parameters
        error = tool.validate(**parameters)
        if error:
            return ToolResult(success=False, error=error)
        
        # Path validation for file tools
        if tool.category in (ToolCategory.FILE, ToolCategory.BASH):
            if "path" in parameters:
                if not self._validate_path(parameters["path"]):
                    return ToolResult(
                        success=False,
                        error=f"Access denied: {parameters['path']} is outside allowed directories",
                    )
            if "command" in parameters:
                if not self._validate_command(parameters["command"]):
                    return ToolResult(
                        success=False,
                        error=f"Command blocked for security: {parameters['command']}",
                    )
        
        return await tool.execute(**parameters)
    
    def _validate_path(self, path: str) -> bool:
        """Validate path is within allowed directories (chroot)"""
        try:
            from cortex.config import CortexConfig
            config = CortexConfig.load()
        except Exception:
            return True  # No config, allow
        
        if not config.security.chroot_wiki and not config.security.chroot_raw:
            return True
        
        resolved = os.path.realpath(path)
        allowed = []
        
        if config.security.chroot_wiki and self._wiki_path:
            allowed.append(os.path.realpath(self._wiki_path))
        if config.security.chroot_raw and self._raw_path:
            allowed.append(os.path.realpath(self._raw_path))
        
        return any(resolved.startswith(p) for p in allowed)
    
    def _validate_command(self, command: str) -> bool:
        """Validate command doesn't do dangerous things"""
        dangerous_patterns = [
            "rm -rf /",
            "rm -rf /*",
            "mkfs",
            "dd if=",
            "> /dev/",
            "> /etc/",
            "chmod 777 /",
            "chown -R",
            ":(){:|:&};:",
            "wget",
            "curl",
            "nc ",
            "ncat",
            "netcat",
            "/dev/tcp",
        ]
        return not any(d in command for d in dangerous_patterns)


# === Default Tool Registry ===

def create_default_tools(memory=None, wiki_path=None, raw_path=None) -> ToolRegistry:
    """Create registry with default tools"""
    registry = ToolRegistry(wiki_path=wiki_path, raw_path=raw_path)
    
    # Core tools
    registry.register(BashTool())
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(GlobTool())
    registry.register(GrepTool())
    registry.register(WebSearchTool())
    registry.register(MemorySearchTool(memory=memory))
    registry.register(MemoryStoreTool(memory=memory))
    
    return registry
