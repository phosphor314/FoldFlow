"""Command-line interface for FoldFlow."""

import argparse
import asyncio
import json
import os
import sys
from typing import Optional

from .models import (
    Fold, Project, Node, PromptNode, ExecuteNode,
    Resource, TextResource, SkillResource, ArtifactResource
)
from .sprint import resolve_sprint, run_sprint_cycle


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        description="FoldFlow - A DAG-based project workflow engine"
    )
    
    subparsers = parser.add_subparsers(
        title="commands",
        dest="command",
        required=True,
    )
    
    # init command
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a FoldFlow project in the current directory",
    )
    init_parser.add_argument(
        "--repo-path",
        default=".",
        help="Path to the repository (default: current directory)",
    )
    init_parser.add_argument(
        "--fold-file",
        default="fold.json",
        help="Path to the fold file (default: fold.json)",
    )
    
    # add-node command
    add_node_parser = subparsers.add_parser(
        "add-node",
        help="Add a node to the fold",
    )
    add_node_parser.add_argument(
        "--type",
        choices=["prompt", "execute"],
        required=True,
        help="Type of node to add",
    )
    add_node_parser.add_argument(
        "--name",
        required=True,
        help="Name of the node",
    )
    add_node_parser.add_argument(
        "--id",
        help="ID of the node (auto-generated if not provided)",
    )
    add_node_parser.add_argument(
        "--command",
        help="Command to execute (for execute nodes)",
    )
    add_node_parser.add_argument(
        "--prompt",
        help="Prompt template (for prompt nodes)",
    )
    add_node_parser.add_argument(
        "--model",
        default="dummy",
        help="LLM model to use (for prompt nodes, 'dummy' for testing)",
    )
    add_node_parser.add_argument(
        "--api-key",
        help="Mistral API key (optional, can also use MISTRAL_API_KEY env var)",
    )
    add_node_parser.add_argument(
        "--dependency",
        action="append",
        help="Add a dependency node ID",
    )
    add_node_parser.add_argument(
        "--repo-path",
        default=".",
        help="Path to the repository (default: current directory)",
    )
    add_node_parser.add_argument(
        "--fold-file",
        default="fold.json",
        help="Path to the fold file",
    )
    
    # remove-node command
    remove_node_parser = subparsers.add_parser(
        "remove-node",
        help="Remove a node from the fold",
    )
    remove_node_parser.add_argument(
        "node_id",
        help="ID of the node to remove",
    )
    remove_node_parser.add_argument(
        "--repo-path",
        default=".",
        help="Path to the repository",
    )
    remove_node_parser.add_argument(
        "--fold-file",
        default="fold.json",
        help="Path to the fold file",
    )
    
    # add-edge command
    add_edge_parser = subparsers.add_parser(
        "add-edge",
        help="Add a dependency edge between nodes",
    )
    add_edge_parser.add_argument(
        "from_node",
        help="Source node ID",
    )
    add_edge_parser.add_argument(
        "to_node",
        help="Target node ID",
    )
    add_edge_parser.add_argument(
        "--resource-name",
        help="Name of the resource passed along the edge",
    )
    add_edge_parser.add_argument(
        "--resource-type",
        choices=["text", "skill", "artifact"],
        help="Type of resource",
    )
    add_edge_parser.add_argument(
        "--repo-path",
        default=".",
        help="Path to the repository",
    )
    add_edge_parser.add_argument(
        "--fold-file",
        default="fold.json",
        help="Path to the fold file",
    )
    
    # list-nodes command
    list_nodes_parser = subparsers.add_parser(
        "list-nodes",
        help="List all nodes in the fold",
    )
    list_nodes_parser.add_argument(
        "--repo-path",
        default=".",
        help="Path to the repository",
    )
    list_nodes_parser.add_argument(
        "--fold-file",
        default="fold.json",
        help="Path to the fold file",
    )
    
    # show-fold command
    show_fold_parser = subparsers.add_parser(
        "show-fold",
        help="Show the fold structure",
    )
    show_fold_parser.add_argument(
        "--repo-path",
        default=".",
        help="Path to the repository",
    )
    show_fold_parser.add_argument(
        "--fold-file",
        default="fold.json",
        help="Path to the fold file",
    )
    
    # sprint command
    sprint_parser = subparsers.add_parser(
        "sprint",
        help="Execute a sprint (resolve all nodes)",
    )
    sprint_parser.add_argument(
        "--repo-path",
        default=".",
        help="Path to the repository",
    )
    sprint_parser.add_argument(
        "--fold-file",
        default="fold.json",
        help="Path to the fold file",
    )
    sprint_parser.add_argument(
        "--cycle",
        action="store_true",
        help="Run a complete sprint cycle (resolve + edit fold)",
    )
    
    return parser


def init_project(repo_path: str, fold_file: str) -> None:
    """Initialize a FoldFlow project."""
    import os
    # Use absolute path
    abs_repo_path = os.path.abspath(repo_path)
    project = Project(repo_path=abs_repo_path, fold_file_path=fold_file)
    
    # Create an empty fold file
    project.save_fold()
    
    print(f"Initialized FoldFlow project in {abs_repo_path}")
    print(f"Fold file: {project.get_fold_file_path()}")


def add_node(
    node_type: str,
    name: str,
    node_id: Optional[str],
    command: Optional[str],
    prompt: Optional[str],
    model: str,
    api_key: Optional[str],
    dependencies: Optional[list],
    repo_path: str,
    fold_file: str,
) -> None:
    """Add a node to the fold."""
    import os
    abs_repo_path = os.path.abspath(repo_path)
    project = Project(repo_path=abs_repo_path, fold_file_path=fold_file)
    project.load_fold()
    
    fold = project.get_fold()
    
    # Create the node
    if node_type == "execute":
        node = ExecuteNode(name=name, command=command or "")
    else:  # prompt
        node = PromptNode(
            name=name,
            prompt_template=prompt or "",
            model=model,
            api_key=api_key,
        )
    
    if node_id:
        node.id = node_id
    
    # Add dependencies
    if dependencies:
        for dep_id in dependencies:
            node.add_dependency(dep_id)
    
    fold.add_node(node)
    project.save_fold()
    
    print(f"Added {node_type} node: {node.id} ({name})")


def remove_node(node_id: str, repo_path: str, fold_file: str) -> None:
    """Remove a node from the fold."""
    import os
    abs_repo_path = os.path.abspath(repo_path)
    project = Project(repo_path=abs_repo_path, fold_file_path=fold_file)
    project.load_fold()
    
    fold = project.get_fold()
    
    if fold.remove_node(node_id):
        project.save_fold()
        print(f"Removed node: {node_id}")
    else:
        print(f"Node not found: {node_id}")


def add_edge(
    from_node: str,
    to_node: str,
    resource_name: Optional[str],
    resource_type: Optional[str],
    repo_path: str,
    fold_file: str,
) -> None:
    """Add a dependency edge between nodes."""
    import os
    abs_repo_path = os.path.abspath(repo_path)
    project = Project(repo_path=abs_repo_path, fold_file_path=fold_file)
    project.load_fold()
    
    fold = project.get_fold()
    
    from_node_obj = fold.get_node(from_node)
    to_node_obj = fold.get_node(to_node)
    
    if not from_node_obj:
        print(f"Source node not found: {from_node}")
        return
    
    if not to_node_obj:
        print(f"Target node not found: {to_node}")
        return
    
    # Add dependency
    to_node_obj.add_dependency(from_node)
    
    # If a resource is specified, add it as an emitted resource from source
    # and consumed resource in target
    if resource_name and resource_type:
        # Create a resource
        if resource_type == "text":
            resource = TextResource(name=resource_name)
        elif resource_type == "skill":
            resource = SkillResource(name=resource_name)
        else:  # artifact
            resource = ArtifactResource(name=resource_name)
        
        from_node_obj.add_emitted_resource(resource_name, resource)
        to_node_obj.add_consumed_resource(resource_name, resource)
    
    project.save_fold()
    print(f"Added edge: {from_node} -> {to_node}")


def list_nodes(repo_path: str, fold_file: str) -> None:
    """List all nodes in the fold."""
    import os
    abs_repo_path = os.path.abspath(repo_path)
    project = Project(repo_path=abs_repo_path, fold_file_path=fold_file)
    project.load_fold()
    
    fold = project.get_fold()
    
    if not fold.nodes:
        print("No nodes in fold")
        return
    
    print("Nodes:")
    for node_id, node in fold.nodes.items():
        node_type = node.get_type().name.lower()
        status = "resolved" if node.resolved else "pending"
        deps = ", ".join(node.dependencies) if node.dependencies else "none"
        print(f"  {node_id}: {node.name} ({node_type}, {status}, deps: {deps})")


def show_fold(repo_path: str, fold_file: str) -> None:
    """Show the fold structure."""
    import os
    abs_repo_path = os.path.abspath(repo_path)
    project = Project(repo_path=abs_repo_path, fold_file_path=fold_file)
    project.load_fold()
    
    fold = project.get_fold()
    
    print(fold.to_json())


async def run_sprint_command(repo_path: str, fold_file: str, run_cycle: bool) -> None:
    """Execute a sprint."""
    import os
    abs_repo_path = os.path.abspath(repo_path)
    project = Project(repo_path=abs_repo_path, fold_file_path=fold_file)
    project.load_fold()
    
    if run_cycle:
        # Run complete cycle
        result = await run_sprint_cycle(project)
        sprint_results = result["sprint_results"]
        project.save_fold()
    else:
        # Just run sprint
        sprint_results = await resolve_sprint(project)
        project.save_fold()
    
    # Print results
    print("Sprint Results:")
    print(f"  Success: {sprint_results['success']}")
    print(f"  Resolved nodes: {sprint_results['resolved_nodes']}")
    print(f"  Failed nodes: {sprint_results['failed_nodes']}")
    
    if sprint_results["failed_nodes"]:
        print("\nFailed nodes details:")
        for node_id, result in sprint_results["results"].items():
            if not result["success"]:
                print(f"  {node_id}:")
                print(f"    Error: {result['error']}")


def main() -> None:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    try:
        if args.command == "init":
            init_project(args.repo_path, args.fold_file)
        
        elif args.command == "add-node":
            add_node(
                node_type=args.type,
                name=args.name,
                node_id=args.id,
                command=args.command,
                prompt=args.prompt,
                model=args.model,
                api_key=args.api_key,
                dependencies=args.dependency,
                repo_path=args.repo_path,
                fold_file=args.fold_file,
            )
        
        elif args.command == "remove-node":
            remove_node(args.node_id, args.repo_path, args.fold_file)
        
        elif args.command == "add-edge":
            add_edge(
                from_node=args.from_node,
                to_node=args.to_node,
                resource_name=args.resource_name,
                resource_type=args.resource_type,
                repo_path=args.repo_path,
                fold_file=args.fold_file,
            )
        
        elif args.command == "list-nodes":
            list_nodes(args.repo_path, args.fold_file)
        
        elif args.command == "show-fold":
            show_fold(args.repo_path, args.fold_file)
        
        elif args.command == "sprint":
            asyncio.run(
                run_sprint_command(
                    args.repo_path,
                    args.fold_file,
                    args.cycle,
                )
            )
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
