"""Tests for edit_fold functionality."""

import unittest
import asyncio
import tempfile
import os

from foldflow.models import Project, PromptNode, ExecuteNode, TextResource, Fold
from foldflow.sprint import edit_fold, run_sprint_cycle


class TestEditFold(unittest.TestCase):
    """Test edit_fold functionality."""
    
    def test_edit_fold_dummy_mode(self):
        """Test that edit_fold with dummy model returns fold unchanged."""
        async def test():
            with tempfile.TemporaryDirectory() as tmpdir:
                project = Project(repo_path=tmpdir, fold_file_path="fold.json")
                
                # Create a simple fold
                node = ExecuteNode(name="build", command="echo Build")
                fold = project.get_fold()
                fold.add_node(node)
                
                # Create dummy sprint results
                sprint_results = {
                    "success": True,
                    "resolved_nodes": [node.id],
                    "failed_nodes": [],
                    "results": {}
                }
                
                # Edit fold with dummy model
                new_fold = await edit_fold(project, sprint_results, model="dummy")
                
                # Should be unchanged
                self.assertEqual(len(new_fold.nodes), 1)
                self.assertIn(node.id, new_fold.nodes)
        
        asyncio.run(test())
    
    def test_edit_fold_with_failed_nodes(self):
        """Test edit_fold with failed nodes in sprint results."""
        async def test():
            with tempfile.TemporaryDirectory() as tmpdir:
                project = Project(repo_path=tmpdir, fold_file_path="fold.json")
                
                # Create nodes
                gen_node = PromptNode(name="generate", prompt_template="Generate", model="dummy")
                build_node = ExecuteNode(name="build", command="echo Build")
                
                build_node.add_dependency(gen_node.id)
                
                fold = project.get_fold()
                fold.add_node(gen_node)
                fold.add_node(build_node)
                
                # Create sprint results with a failure
                sprint_results = {
                    "success": False,
                    "resolved_nodes": [gen_node.id],
                    "failed_nodes": [build_node.id],
                    "results": {
                        build_node.id: {
                            "success": False,
                            "output": "",
                            "error": "Command failed"
                        }
                    }
                }
                
                # Edit fold with dummy model
                new_fold = await edit_fold(project, sprint_results, model="dummy")
                
                # Should still have both nodes (dummy mode doesn't modify)
                self.assertEqual(len(new_fold.nodes), 2)
        
        asyncio.run(test())
    
    def test_run_sprint_cycle_dummy_mode(self):
        """Test run_sprint_cycle with dummy mode."""
        async def test():
            with tempfile.TemporaryDirectory() as tmpdir:
                project = Project(repo_path=tmpdir, fold_file_path="fold.json")
                
                # Create nodes
                gen_node = PromptNode(name="generate", prompt_template="Generate", model="dummy")
                build_node = ExecuteNode(name="build", command="echo Build")
                
                build_node.add_dependency(gen_node.id)
                
                fold = project.get_fold()
                fold.add_node(gen_node)
                fold.add_node(build_node)
                
                project.save_fold()
                
                # Run sprint cycle
                result = await run_sprint_cycle(project, edit_model="dummy")
                
                # Check results
                self.assertTrue(result["sprint_results"]["success"])
                self.assertEqual(len(result["sprint_results"]["resolved_nodes"]), 2)
                self.assertFalse(result["fold_modified"])  # Dummy mode doesn't modify
        
        asyncio.run(test())
    
    def test_edit_fold_real_model_without_api_key(self):
        """Test that edit_fold with real model fails gracefully without API key."""
        async def test():
            with tempfile.TemporaryDirectory() as tmpdir:
                project = Project(repo_path=tmpdir, fold_file_path="fold.json")
                
                # Create a simple fold
                node = ExecuteNode(name="build", command="echo Build")
                fold = project.get_fold()
                fold.add_node(node)
                
                # Create sprint results
                sprint_results = {
                    "success": True,
                    "resolved_nodes": [node.id],
                    "failed_nodes": [],
                    "results": {}
                }
                
                # Edit fold with real model but no API key
                new_fold = await edit_fold(project, sprint_results, model="mistral-tiny")
                
                # Should return original fold unchanged
                self.assertEqual(len(new_fold.nodes), 1)
                self.assertIn(node.id, new_fold.nodes)
        
        asyncio.run(test())
    
    def test_edit_fold_preserves_fold_structure(self):
        """Test that edit_fold preserves fold structure when no changes are suggested."""
        async def test():
            with tempfile.TemporaryDirectory() as tmpdir:
                project = Project(repo_path=tmpdir, fold_file_path="fold.json")
                
                # Create a complex fold
                gen_node = PromptNode(name="generate", prompt_template="Generate", model="dummy")
                build_node = ExecuteNode(name="build", command="echo Build")
                test_node = ExecuteNode(name="test", command="echo Test")
                
                build_node.add_dependency(gen_node.id)
                test_node.add_dependency(build_node.id)
                
                fold = project.get_fold()
                fold.add_node(gen_node)
                fold.add_node(build_node)
                fold.add_node(test_node)
                
                # Store original structure
                original_node_ids = set(fold.nodes.keys())
                original_deps = {
                    gen_node.id: list(gen_node.dependencies),
                    build_node.id: list(build_node.dependencies),
                    test_node.id: list(test_node.dependencies),
                }
                
                # Create sprint results
                sprint_results = {
                    "success": True,
                    "resolved_nodes": [gen_node.id, build_node.id, test_node.id],
                    "failed_nodes": [],
                    "results": {}
                }
                
                # Edit fold with dummy model
                new_fold = await edit_fold(project, sprint_results, model="dummy")
                
                # Structure should be preserved
                self.assertEqual(set(new_fold.nodes.keys()), original_node_ids)
                
                for node_id in original_node_ids:
                    node = new_fold.get_node(node_id)
                    self.assertIsNotNone(node)
                    self.assertEqual(node.dependencies, original_deps[node_id])
        
        asyncio.run(test())


if __name__ == "__main__":
    unittest.main()
