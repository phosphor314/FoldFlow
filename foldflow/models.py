"""Core data models for FoldFlow."""

from collections.abc import Callable
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Any, Tuple
import json

from mistralai.client.models import ChatCompletionChoice, Tool, ToolMessage, UserMessage, tool
from mistralai.client.models.chatcompletionrequest import ChatCompletionRequestMessage, ChatCompletionRequestTool


class ResourceType(Enum):
    """Types of resources in FoldFlow."""
    TEXT = auto()
    SKILL = auto()
    ARTIFACT = auto()


@dataclass
class Resource(ABC):
    """Abstract base class for all resources."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    
    @abstractmethod
    def get_type(self) -> ResourceType:
        """Return the resource type."""
        pass
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize resource to dictionary."""
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Resource":
        """Deserialize resource from dictionary."""
        pass


@dataclass
class TextResource(Resource):
    """A text resource (e.g., code, prompts)."""
    content: str = ""
    
    def get_type(self) -> ResourceType:
        return ResourceType.TEXT
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "text",
            "id": self.id,
            "name": self.name,
            "content": self.content,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextResource":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            content=data.get("content", ""),
        )


@dataclass
class SkillResource(Resource):
    """A skill resource (tools + SKILL.md)."""
    skill_md_content: str = ""
    tools: list[Tuple[Tool, Callable]] = field(default_factory=list)
    
    def get_type(self) -> ResourceType:
        return ResourceType.SKILL
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "skill",
            "id": self.id,
            "name": self.name,
            "skill_md_content": self.skill_md_content,
            "tools": self.tools,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SkillResource:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            skill_md_content=data.get("skill_md_content", ""),
            tools=data.get("tool_names", []),
        )


@dataclass
class ArtifactResource(Resource):
    """An artifact resource (e.g., perf recording)."""
    file_path: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)
    
    def get_type(self) -> ResourceType:
        return ResourceType.ARTIFACT
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "artifact",
            "id": self.id,
            "name": self.name,
            "file_path": self.file_path,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactResource":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            file_path=data.get("file_path", ""),
            metadata=data.get("metadata", {}),
        )


class NodeType(Enum):
    """Types of nodes in FoldFlow."""
    PROMPT = auto()
    EXECUTE = auto()


@dataclass
class Node(ABC):
    """Abstract base class for all nodes."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    consumed_resources: Dict[str, Resource] = field(default_factory=dict)
    emitted_resources: Dict[str, Resource] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    resolved: bool = False
    output: Optional[str] = None
    error: Optional[str] = None
    
    @abstractmethod
    def get_type(self) -> NodeType:
        """Return the node type."""
        pass
    
    @abstractmethod
    async def resolve(self, project_root: str) -> bool:
        """Resolve the node. Returns True if successful."""
        pass
    
    def add_consumed_resource(self, name: str, resource: Resource) -> None:
        """Add a consumed resource."""
        self.consumed_resources[name] = resource
    
    def add_emitted_resource(self, name: str, resource: Resource) -> None:
        """Add an emitted resource."""
        self.emitted_resources[name] = resource
    
    def add_dependency(self, node_id: str) -> None:
        """Add a dependency node ID."""
        if node_id not in self.dependencies:
            self.dependencies.append(node_id)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize node to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.get_type().name.lower(),
            "consumed_resources": {k: v.to_dict() for k, v in self.consumed_resources.items()},
            "emitted_resources": {k: v.to_dict() for k, v in self.emitted_resources.items()},
            "dependencies": self.dependencies,
            "resolved": self.resolved,
            "output": self.output,
            "error": self.error,
        }
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Node":
        """Deserialize node from dictionary."""
        pass
    
    def get_consumed_resource_names(self) -> List[str]:
        """Get list of consumed resource names."""
        return list(self.consumed_resources.keys())
    
    def get_emitted_resource_names(self) -> List[str]:
        """Get list of emitted resource names."""
        return list(self.emitted_resources.keys())


@dataclass
class PromptNode(Node):
    """A node that prompts an LLM."""
    prompt_template: str = ""
    model: str = "dummy"  # Default to dummy model for testing
    temperature: float = 0.7
    max_tokens: int = 2048
    
    def get_type(self) -> NodeType:
        return NodeType.PROMPT
    
    async def resolve(self, project_root: str) -> bool:
        """Resolve by building prompt and calling LLM."""
        self.output = ""
        self.error = ""
        
        try:
            # Build prompt from consumed resources
            prompt_parts = []
            
            # Add text resources
            for name, resource in self.consumed_resources.items():
                if isinstance(resource, TextResource):
                    prompt_parts.append(f"[{name}]\n{resource.content}\n")
                elif isinstance(resource, SkillResource):
                    prompt_parts.append(f"[{name} SKILL]\n{resource.skill_md_content}\n")
            
            # Add the prompt template
            if self.prompt_template:
                prompt_parts.append(self.prompt_template)
            
            prompt = "\n".join(prompt_parts)
            
            # get tools provided by skills
            requestTools = []
            functionDict = {}
            for name, resource in self.consumed_resources.items():
                if not isinstance(resource, SkillResource):
                    continue
                for t in resource.tools:
                    requestTools.append(t[0])
                    if t[0].function.name in functionDict:
                        self.resolved = False
                        self.output = None
                        conflict_resource = None
                        for _name, _resource in self.consumed_resources.items():
                            if not isinstance(_resource, SkillResource):
                                continue
                            for _t in _resource.tools:
                                if t[0].function.name in functionDict:
                                    conflict_resource = _name
                        assert(conflict_resource)
                        self.error = "Tools from skill resource " + name + " and " + conflict_resource + " share a name. Tool names must be unique!"
                        return False
                    functionDict[t[0].function.name] = t[1]
            
            # Use dummy model for testing
            if self.model == "dummy":
                self.output = f"LLM response to prompt: {prompt[:100]}..."
                self.resolved = True
                self.error = None
                return True
            
            # Use actual Mistral API for non-dummy models
            try:
                from mistralai.client import Mistral
                import os
                
                api_key = os.environ.get("MISTRAL_API_KEY")
                if not api_key:
                    self.error = "Mistral API key not provided"
                    self.resolved = False
                    return False
                
                client = Mistral(api_key=api_key)
                
                # Convert prompt to messages format
                messages: list[ChatCompletionRequestMessage] = [UserMessage(content=prompt)]
                
                tokens_left = self.max_tokens + 1
                
                while (tokens_left > 0):
                    response = client.chat.complete(
                        model=self.model,
                        messages=messages,
                        tools=requestTools,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                    )
                    assert(response.usage.prompt_tokens)
                    tokens_left -= response.usage.prompt_tokens
                    
                    for c in response.choices:
                        if not c.message:
                            continue
                        if c.message.tool_calls:
                            for t in c.message.tool_calls:
                                try:
                                    if isinstance(t.function.arguments, str):
                                        tool_resp = functionDict[t.function.name][1](**json.loads(t.function.arguments))
                                    else:
                                        tool_resp = functionDict[t.function.name][1](**t.function.arguments)
                                    if not tool_resp:
                                        tool_resp = "success"
                                    messages.append(ToolMessage(content=str(tool_resp), tool_call_id=t.id))
                                except Exception as e:
                                    messages.append(ToolMessage(content="Error while calling tool " + t.function.name + ": " + str(e), tool_call_id=t.id))
                        elif c.message.content:
                            assert(type(c.message.content) == str)
                            self.output += c.message.content
                
                if self.output == "":
                    self.output = "No response from LLM"
                if tokens_left == 0:
                    self.error = "Ran out of tokens!"
                    self.resolved = False
                    return False
                    
                self.resolved = True
                self.error = None
                return True
                
            except ImportError:
                self.error = "mistralai package not installed"
                self.resolved = False
                return False
            except Exception as e:
                self.error = f"Mistral API error: {str(e)}"
                self.resolved = False
                return False
            
        except Exception as e:
            self.error = str(e)
            self.resolved = False
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "prompt_template": self.prompt_template,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        })
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptNode":
        node = cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            prompt_template=data.get("prompt_template", ""),
            model=data.get("model", "dummy"),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens", 2048),
            resolved=data.get("resolved", False),
            output=data.get("output"),
            error=data.get("error"),
        )
        
        # Deserialize consumed resources
        for name, res_data in data.get("consumed_resources", {}).items():
            res_type = res_data.get("type", "text")
            if res_type == "text":
                node.consumed_resources[name] = TextResource.from_dict(res_data)
            elif res_type == "skill":
                node.consumed_resources[name] = SkillResource.from_dict(res_data)
            elif res_type == "artifact":
                node.consumed_resources[name] = ArtifactResource.from_dict(res_data)
        
        # Deserialize emitted resources
        for name, res_data in data.get("emitted_resources", {}).items():
            res_type = res_data.get("type", "text")
            if res_type == "text":
                node.emitted_resources[name] = TextResource.from_dict(res_data)
            elif res_type == "skill":
                node.emitted_resources[name] = SkillResource.from_dict(res_data)
            elif res_type == "artifact":
                node.emitted_resources[name] = ArtifactResource.from_dict(res_data)
        
        node.dependencies = data.get("dependencies", [])
        return node


@dataclass
class ExecuteNode(Node):
    """A node that executes a shell command."""
    command: str = ""
    timeout: int = 300  # seconds
    
    def get_type(self) -> NodeType:
        return NodeType.EXECUTE
    
    async def resolve(self, project_root: str) -> bool:
        """Resolve by executing the shell command."""
        import asyncio
        
        try:
            # Execute the command
            proc = await asyncio.create_subprocess_shell(
                self.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=project_root,
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout,
            )
            
            if proc.returncode != 0:
                self.error = f"Command failed with return code {proc.returncode}: {stderr.decode()}"
                self.resolved = False
                self.output = stdout.decode()
                return False
            
            self.output = stdout.decode()
            self.resolved = True
            self.error = None
            return True
            
        except asyncio.TimeoutError:
            self.error = f"Command timed out after {self.timeout} seconds"
            self.resolved = False
            return False
        except Exception as e:
            self.error = str(e)
            self.resolved = False
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "command": self.command,
            "timeout": self.timeout,
        })
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecuteNode":
        node = cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            command=data.get("command", ""),
            timeout=data.get("timeout", 300),
            resolved=data.get("resolved", False),
            output=data.get("output"),
            error=data.get("error"),
        )
        
        # Deserialize consumed resources
        for name, res_data in data.get("consumed_resources", {}).items():
            res_type = res_data.get("type", "text")
            if res_type == "text":
                node.consumed_resources[name] = TextResource.from_dict(res_data)
            elif res_type == "skill":
                node.consumed_resources[name] = SkillResource.from_dict(res_data)
            elif res_type == "artifact":
                node.consumed_resources[name] = ArtifactResource.from_dict(res_data)
        
        # Deserialize emitted resources
        for name, res_data in data.get("emitted_resources", {}).items():
            res_type = res_data.get("type", "text")
            if res_type == "text":
                node.emitted_resources[name] = TextResource.from_dict(res_data)
            elif res_type == "skill":
                node.emitted_resources[name] = SkillResource.from_dict(res_data)
            elif res_type == "artifact":
                node.emitted_resources[name] = ArtifactResource.from_dict(res_data)
        
        node.dependencies = data.get("dependencies", [])
        return node


@dataclass
class Fold:
    """A DAG of nodes representing a project workflow."""
    nodes: Dict[str, Node] = field(default_factory=dict)
    
    def add_node(self, node: Node) -> None:
        """Add a node to the fold."""
        self.nodes[node.id] = node
    
    def remove_node(self, node_id: str) -> bool:
        """Remove a node from the fold. Returns True if removed."""
        if node_id in self.nodes:
            del self.nodes[node_id]
            # Remove dependencies on this node
            for other_node in self.nodes.values():
                if node_id in other_node.dependencies:
                    other_node.dependencies.remove(node_id)
            return True
        return False
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        return self.nodes.get(node_id)
    
    def get_dependencies(self, node_id: str) -> List[Node]:
        """Get all dependency nodes for a given node."""
        node = self.get_node(node_id)
        if not node:
            return []
        return [self.get_node(dep_id) for dep_id in node.dependencies if self.get_node(dep_id)]
    
    def get_dependents(self, node_id: str) -> List[Node]:
        """Get all nodes that depend on a given node."""
        result = []
        for node in self.nodes.values():
            if node_id in node.dependencies:
                result.append(node)
        return result
    
    def get_topological_order(self) -> List[str]:
        """Get nodes in topological order (dependencies first)."""
        visited = set()
        order = []
        visiting = set()
        
        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise ValueError(f"Cycle detected involving node {node_id}")
            if node_id in visited:
                return
            
            visiting.add(node_id)
            node = self.get_node(node_id)
            if node:
                for dep_id in node.dependencies:
                    visit(dep_id)
            
            visiting.remove(node_id)
            visited.add(node_id)
            order.append(node_id)
        
        for node_id in self.nodes:
            visit(node_id)
        
        return order
    
    def get_resolvable_order(self) -> List[str]:
        """Get nodes in order that can be resolved (bottom-up)."""
        # Reverse topological order for bottom-up resolution
        return list(reversed(self.get_topological_order()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize fold to dictionary."""
        return {
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()},
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fold":
        """Deserialize fold from dictionary."""
        fold = cls()
        for node_id, node_data in data.get("nodes", {}).items():
            node_type = node_data.get("type", "prompt")
            if node_type == "prompt":
                fold.nodes[node_id] = PromptNode.from_dict(node_data)
            elif node_type == "execute":
                fold.nodes[node_id] = ExecuteNode.from_dict(node_data)
        return fold
    
    def to_json(self) -> str:
        """Serialize fold to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "Fold":
        """Deserialize fold from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class Project:
    """A project is a git repository with a fold."""
    repo_path: str
    fold: Fold = field(default_factory=Fold)
    fold_file_path: str = "fold.json"
    
    def get_fold_file_path(self) -> str:
        """Get the full path to the fold file."""
        import os
        return os.path.join(self.repo_path, self.fold_file_path)
    
    def save_fold(self) -> None:
        """Save the fold to the fold file."""
        fold_path = self.get_fold_file_path()
        with open(fold_path, "w") as f:
            f.write(self.fold.to_json())
    
    def load_fold(self) -> None:
        """Load the fold from the fold file."""
        fold_path = self.get_fold_file_path()
        try:
            with open(fold_path, "r") as f:
                self.fold = Fold.from_json(f.read())
        except FileNotFoundError:
            self.fold = Fold()
    
    def get_fold(self) -> Fold:
        """Get the project's fold."""
        return self.fold
    
    def set_fold(self, fold: Fold) -> None:
        """Set the project's fold."""
        self.fold = fold
