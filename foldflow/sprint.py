"""Sprint resolution logic for FoldFlow."""

import asyncio
import uuid
from typing import Dict, List, Optional, Any
from .models import Fold, Node, Project, PromptNode, ExecuteNode


async def resolve_node(node: Node, project_root: str) -> bool:
    """Resolve a single node."""
    if node.resolved:
        # Already resolved, skip
        return True
    
    # Check if all dependencies are resolved
    # This check should be done by the caller
    
    try:
        result = await node.resolve(project_root)
        return result
    except Exception as e:
        node.error = str(e)
        node.resolved = False
        return False


async def resolve_sprint(project: Project) -> Dict[str, Any]:
    """
    Execute a sprint: resolve all nodes in bottom-up order.
    
    Returns a dictionary with:
    - success: bool indicating if all nodes were resolved
    - resolved_nodes: list of successfully resolved node IDs
    - failed_nodes: list of failed node IDs
    - results: dict of node_id -> (success, output, error)
    """
    fold = project.get_fold()
    
    # Get topological order (dependencies first)
    node_order = fold.get_topological_order()
    
    results: Dict[str, Any] = {}
    resolved_nodes: List[str] = []
    failed_nodes: List[str] = []
    
    # Track which nodes have been successfully resolved
    resolved_deps: Dict[str, bool] = {node_id: False for node_id in fold.nodes}
    
    # Process nodes in topological order (dependencies first)
    for node_id in node_order:
        node = fold.get_node(node_id)
        if not node:
            continue
        
        # Check if all dependencies are resolved
        all_deps_resolved = True
        for dep_id in node.dependencies:
            if not resolved_deps.get(dep_id, False):
                all_deps_resolved = False
                break
        
        if not all_deps_resolved:
            # Cannot resolve this node yet, skip
            # This shouldn't happen in topological order, but we check anyway
            continue
        
        # Resolve the node
        success = await resolve_node(node, project.repo_path)
        resolved_deps[node_id] = success
        
        if success:
            resolved_nodes.append(node_id)
        else:
            failed_nodes.append(node_id)
        
        results[node_id] = {
            "success": success,
            "output": node.output,
            "error": node.error,
        }
    
    return {
        "success": len(failed_nodes) == 0,
        "resolved_nodes": resolved_nodes,
        "failed_nodes": failed_nodes,
        "results": results,
    }


async def edit_fold(project: Project, sprint_results: Dict[str, Any], model: str = "dummy", api_key: Optional[str] = None) -> Fold:
    """
    Edit the fold based on sprint results using Mistral API.
    
    This function uses an LLM to analyze sprint results and suggest improvements
    to the fold structure. It:
    1. Creates a prompt describing the sprint results and current fold state
    2. Calls Mistral API to get suggestions for fold improvements
    3. Parses the response and applies changes to the fold
    
    Args:
        project: The project containing the fold
        sprint_results: Results from the sprint resolution
        model: The Mistral model to use ('dummy' for testing without API calls)
        api_key: Optional Mistral API key (can also use MISTRAL_API_KEY env var)
    
    Returns:
        The modified fold
    """
    fold = project.get_fold()
    
    # If using dummy model, just return the fold unchanged
    if model == "dummy":
        return fold
    
    # Build prompt for the LLM
    prompt_parts = [
        "You are a FoldFlow assistant. Analyze the sprint results and suggest improvements to the fold structure.",
        "",
        "## Sprint Summary",
        f"- Success: {sprint_results.get('success', False)}",
        f"- Resolved nodes: {len(sprint_results.get('resolved_nodes', []))}",
        f"- Failed nodes: {len(sprint_results.get('failed_nodes', []))}",
        "",
        "## Current Fold Structure",
        f"- Total nodes: {len(fold.nodes)}",
        "",
        "## Node Details",
    ]
    
    # Add details for each node
    for node_id, node in fold.nodes.items():
        node_type = node.get_type().name.lower()
        status = "resolved" if node.resolved else "pending"
        error = node.error or "none"
        output = node.output or "none"
        
        prompt_parts.append(f"### Node: {node.name} ({node_type}, {status})")
        prompt_parts.append(f"- ID: {node_id}")
        prompt_parts.append(f"- Dependencies: {node.dependencies}")
        prompt_parts.append(f"- Error: {error}")
        prompt_parts.append(f"- Output: {output[:100]}..." if output else "- Output: none")
        
        # Add consumed and emitted resources
        if node.consumed_resources:
            prompt_parts.append(f"- Consumed resources: {list(node.consumed_resources.keys())}")
        if node.emitted_resources:
            prompt_parts.append(f"- Emitted resources: {list(node.emitted_resources.keys())}")
        
        prompt_parts.append("")
    
    # Add failed nodes details
    failed_nodes = sprint_results.get("failed_nodes", [])
    if failed_nodes:
        prompt_parts.append("## Failed Nodes Analysis")
        for node_id in failed_nodes:
            node = fold.get_node(node_id)
            if node:
                result = sprint_results.get("results", {}).get(node_id, {})
                prompt_parts.append(f"### {node.name} ({node_id})")
                prompt_parts.append(f"- Error: {result.get('error', 'unknown')}")
                prompt_parts.append(f"- Output: {result.get('output', 'none')}")
                prompt_parts.append("")
    
    prompt_parts.append("## Instructions")
    prompt_parts.append("Based on the sprint results above, suggest improvements to the fold structure.")
    prompt_parts.append("Consider:")
    prompt_parts.append("- Adding missing dependencies")
    prompt_parts.append("- Fixing failed nodes")
    prompt_parts.append("- Adding new nodes to address gaps")
    prompt_parts.append("- Removing unnecessary nodes")
    prompt_parts.append("")
    prompt_parts.append("Respond with a JSON object describing the changes to make:")
    prompt_parts.append('{"changes": [{"action": "add_node" | "remove_node" | "add_edge" | "modify_node", ...}]}')
    
    prompt = "\n".join(prompt_parts)
    
    # Use Mistral API to get suggestions
    try:
        from mistralai.client import Mistral
        import os
        import json
        
        actual_api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        if not actual_api_key:
            print("Warning: No Mistral API key provided, using dummy mode")
            return fold
        
        client = Mistral(api_key=actual_api_key)
        
        response = client.chat.complete(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048,
        )
        
        # Parse the response
        if response.choices and len(response.choices) > 0:
            response_text = response.choices[0].message.content
            
            # Try to parse as JSON
            try:
                changes = json.loads(response_text)
                
                # Apply changes to the fold
                if "changes" in changes:
                    for change in changes["changes"]:
                        action = change.get("action")
                        
                        if action == "add_node":
                            node_type = change.get("type", "prompt")
                            node_name = change.get("name", "new_node")
                            node_id = change.get("id", str(uuid.uuid4()))
                            
                            if node_type == "prompt":
                                new_node = PromptNode(
                                    id=node_id,
                                    name=node_name,
                                    prompt_template=change.get("prompt_template", ""),
                                    model=change.get("model", "dummy"),
                                )
                            else:  # execute
                                new_node = ExecuteNode(
                                    id=node_id,
                                    name=node_name,
                                    command=change.get("command", ""),
                                )
                            
                            fold.add_node(new_node)
                            
                        elif action == "remove_node":
                            node_id = change.get("id")
                            if node_id:
                                fold.remove_node(node_id)
                            
                        elif action == "add_edge":
                            from_node = change.get("from_node")
                            to_node = change.get("to_node")
                            if from_node and to_node:
                                to_node_obj = fold.get_node(to_node)
                                if to_node_obj:
                                    to_node_obj.add_dependency(from_node)
                            
                        elif action == "modify_node":
                            node_id = change.get("id")
                            if node_id:
                                node = fold.get_node(node_id)
                                if node:
                                    if isinstance(node, PromptNode):
                                        if "prompt_template" in change:
                                            node.prompt_template = change["prompt_template"]
                                        if "model" in change:
                                            node.model = change["model"]
                                    elif isinstance(node, ExecuteNode):
                                        if "command" in change:
                                            node.command = change["command"]
            except json.JSONDecodeError:
                # Response is not JSON, just log it
                print(f"LLM response (not JSON): {response_text}")
        
    except ImportError:
        print("Warning: mistralai package not installed, using dummy mode")
        return fold
    except Exception as e:
        print(f"Warning: Error calling Mistral API: {e}, using dummy mode")
        return fold
    
    return fold


async def run_sprint_cycle(project: Project, edit_model: str = "dummy", edit_api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Run a complete sprint cycle:
    1. Resolve nodes in bottom-up order
    2. Edit the fold based on results
    
    Args:
        project: The project to run the cycle on
        edit_model: The Mistral model to use for fold editing ('dummy' for testing)
        edit_api_key: Optional Mistral API key for fold editing
    
    Returns sprint results and the modified fold.
    """
    # Step 1: Resolve sprint
    sprint_results = await resolve_sprint(project)
    
    # Step 2: Edit fold
    old_fold_json = project.get_fold().to_json()
    new_fold = await edit_fold(project, sprint_results, model=edit_model, api_key=edit_api_key)
    project.set_fold(new_fold)
    
    new_fold_json = new_fold.to_json()
    fold_modified = old_fold_json != new_fold_json
    
    return {
        "sprint_results": sprint_results,
        "fold_modified": fold_modified,
    }
