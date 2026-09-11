"""Sprint resolution logic for FoldFlow."""

import asyncio
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


async def edit_fold(project: Project, sprint_results: Dict[str, Any]) -> Fold:
    """
    Edit the fold based on sprint results.
    
    This is a placeholder for the LLM-based fold editing.
    In a real implementation, this would:
    1. Provide the LLM with access to node data (outputs, errors)
    2. Allow the LLM to modify the fold structure
    3. Return the modified fold
    
    For now, this just returns the current fold unchanged.
    """
    # TODO: Implement LLM-based fold editing
    # This would involve:
    # 1. Creating a prompt with sprint results
    # 2. Providing tools to read node data and modify the fold
    # 3. Getting the LLM's response and applying changes
    
    return project.get_fold()


async def run_sprint_cycle(project: Project) -> Dict[str, Any]:
    """
    Run a complete sprint cycle:
    1. Resolve nodes in bottom-up order
    2. Edit the fold based on results
    
    Returns sprint results and the modified fold.
    """
    # Step 1: Resolve sprint
    sprint_results = await resolve_sprint(project)
    
    # Step 2: Edit fold
    new_fold = await edit_fold(project, sprint_results)
    project.set_fold(new_fold)
    
    return {
        "sprint_results": sprint_results,
        "fold_modified": False,  # Would be True if fold was actually modified
    }
