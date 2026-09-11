"""Tests for FoldFlow sprint resolution."""

import unittest
import asyncio
import tempfile
import os

from foldflow.models import Project, ExecuteNode, PromptNode, TextResource
from foldflow.sprint import resolve_sprint, resolve_node


class TestSprint(unittest.TestCase):
    """Test sprint resolution logic."""
    
    def test_resolve_execute_node(self):
        """Test resolving an execute node."""
        async def test():
            with tempfile.TemporaryDirectory() as tmpdir:
                project = Project(repo_path=tmpdir, fold_file_path="fold.json")
                
                # Create an execute node
                node = ExecuteNode(name="build", command="echo Hello")
                fold = project.get_fold()
                fold.add_node(node)
                
                # Resolve the node
                result = await resolve_node(node, tmpdir)
                self.assertTrue(result)
                self.assertTrue(node.resolved)
                self.assertIn("Hello", node.output)
                self.assertIsNone(node.error)
        
        asyncio.run(test())
    
    def test_resolve_prompt_node(self):
        """Test resolving a prompt node."""
        async def test():
            with tempfile.TemporaryDirectory() as tmpdir:
                project = Project(repo_path=tmpdir, fold_file_path="fold.json")
                
                # Create a prompt node
                node = PromptNode(name="generate", prompt_template="Generate code")
                fold = project.get_fold()
                fold.add_node(node)
                
                # Resolve the node
                result = await resolve_node(node, tmpdir)
                self.assertTrue(result)
                self.assertTrue(node.resolved)
                self.assertIsNotNone(node.output)
                self.assertIn("LLM response", node.output)
                self.assertIsNone(node.error)
        
        asyncio.run(test())
    
    def test_resolve_sprint_single_node(self):
        """Test resolving a sprint with a single node."""
        async def test():
            with tempfile.TemporaryDirectory() as tmpdir:
                project = Project(repo_path=tmpdir, fold_file_path="fold.json")
                
                # Create a single execute node
                node = ExecuteNode(name="build", command="echo Test")
                fold = project.get_fold()
                fold.add_node(node)
                
                # Resolve sprint
                result = await resolve_sprint(project)
                
                self.assertTrue(result["success"])
                self.assertEqual(len(result["resolved_nodes"]), 1)
                self.assertEqual(len(result["failed_nodes"]), 0)
                self.assertIn(node.id, result["resolved_nodes"])
        
        asyncio.run(test())
    
    def test_resolve_sprint_with_dependencies(self):
        """Test resolving a sprint with node dependencies."""
        async def test():
            with tempfile.TemporaryDirectory() as tmpdir:
                project = Project(repo_path=tmpdir, fold_file_path="fold.json")
                
                # Create nodes with dependencies
                gen_node = PromptNode(name="generate", prompt_template="Generate")
                build_node = ExecuteNode(name="build", command="echo Build")
                
                build_node.add_dependency(gen_node.id)
                
                fold = project.get_fold()
                fold.add_node(gen_node)
                fold.add_node(build_node)
                
                # Resolve sprint
                result = await resolve_sprint(project)
                
                # Both should resolve successfully
                self.assertTrue(result["success"])
                self.assertEqual(len(result["resolved_nodes"]), 2)
                self.assertEqual(len(result["failed_nodes"]), 0)
                
                # Check order - gen_node should be resolved before build_node
                self.assertIn(gen_node.id, result["resolved_nodes"])
                self.assertIn(build_node.id, result["resolved_nodes"])
        
        asyncio.run(test())
    
    def test_resolve_sprint_with_failure(self):
        """Test resolving a sprint with a failing node."""
        async def test():
            with tempfile.TemporaryDirectory() as tmpdir:
                project = Project(repo_path=tmpdir, fold_file_path="fold.json")
                
                # Create nodes where one will fail
                gen_node = PromptNode(name="generate", prompt_template="Generate")
                build_node = ExecuteNode(name="build", command="exit 1")  # This will fail
                test_node = ExecuteNode(name="test", command="echo Test")
                
                build_node.add_dependency(gen_node.id)
                test_node.add_dependency(build_node.id)
                
                fold = project.get_fold()
                fold.add_node(gen_node)
                fold.add_node(build_node)
                fold.add_node(test_node)
                
                # Resolve sprint
                result = await resolve_sprint(project)
                
                # Sprint should fail
                self.assertFalse(result["success"])
                self.assertEqual(len(result["failed_nodes"]), 1)
                self.assertIn(build_node.id, result["failed_nodes"])
                
                # gen_node should succeed, build_node should fail
                self.assertIn(gen_node.id, result["resolved_nodes"])
                self.assertIn(build_node.id, result["failed_nodes"])
                
                # test_node should not be resolved (dependency failed)
                self.assertNotIn(test_node.id, result["resolved_nodes"])
                self.assertNotIn(test_node.id, result["failed_nodes"])
        
        asyncio.run(test())
    
    def test_resolve_sprint_with_resources(self):
        """Test resolving a sprint with resources flowing between nodes."""
        async def test():
            with tempfile.TemporaryDirectory() as tmpdir:
                project = Project(repo_path=tmpdir, fold_file_path="fold.json")
                
                # Create nodes with resources
                gen_node = PromptNode(name="generate", prompt_template="Generate")
                build_node = ExecuteNode(name="build", command="echo Build")
                
                # Add resource
                output_resource = TextResource(name="output", content="Generated code")
                gen_node.add_emitted_resource("output", output_resource)
                build_node.add_consumed_resource("output", output_resource)
                
                build_node.add_dependency(gen_node.id)
                
                fold = project.get_fold()
                fold.add_node(gen_node)
                fold.add_node(build_node)
                
                # Resolve sprint
                result = await resolve_sprint(project)
                
                self.assertTrue(result["success"])
                self.assertEqual(len(result["resolved_nodes"]), 2)
        
        asyncio.run(test())


if __name__ == "__main__":
    unittest.main()
