"""FoldFlow - A DAG-based project workflow engine."""

from .models import Resource, TextResource, SkillResource, ArtifactResource
from .models import Node, PromptNode, ExecuteNode
from .models import Fold, Project
from .sprint import resolve_sprint, edit_fold
from .cli import main

__all__ = [
    "Resource", "TextResource", "SkillResource", "ArtifactResource",
    "Node", "PromptNode", "ExecuteNode",
    "Fold", "Project",
    "resolve_sprint", "edit_fold",
    "main",
]

__version__ = "0.1.0"
