"""Tests for LLM integration with Mistral API."""

import unittest
import asyncio
import tempfile
import os

from foldflow.models import Project, PromptNode, ExecuteNode, TextResource
from foldflow.sprint import resolve_sprint


class TestLLMIntegration(unittest.TestCase):
    """Test LLM integration."""
    
    def test_dummy_model_works_without_api_key(self):
        """Test that dummy model works without API key."""
        async def test():
            with tempfile.TemporaryDirectory() as tmpdir:
                project = Project(repo_path=tmpdir, fold_file_path="fold.json")
                
                # Create a prompt node with dummy model
                node = PromptNode(
                    name="test",
                    prompt_template="Generate code",
                    model="dummy"
                )
                fold = project.get_fold()
                fold.add_node(node)
                
                # Resolve sprint
                result = await resolve_sprint(project)
                
                self.assertTrue(result["success"])
                self.assertEqual(len(result["resolved_nodes"]), 1)
                self.assertIn(node.id, result["resolved_nodes"])
                
                # Check output
                loaded_fold = project.get_fold()
                loaded_node = loaded_fold.get_node(node.id)
                self.assertIsNotNone(loaded_node)
                self.assertIn("LLM response", loaded_node.output)
        
        asyncio.run(test())
    
    def test_real_model_fails_without_api_key(self):
        """Test that real model fails without API key."""
        async def test():
            with tempfile.TemporaryDirectory() as tmpdir:
                project = Project(repo_path=tmpdir, fold_file_path="fold.json")
                
                # Create a prompt node with real model but no API key
                node = PromptNode(
                    name="test",
                    prompt_template="Generate code",
                    model="mistral-tiny"
                )
                fold = project.get_fold()
                fold.add_node(node)
                
                # Resolve sprint
                result = await resolve_sprint(project)
                
                # Should fail
                self.assertFalse(result["success"])
                self.assertEqual(len(result["failed_nodes"]), 1)
                self.assertIn(node.id, result["failed_nodes"])
                
                # Check error
                loaded_fold = project.get_fold()
                loaded_node = loaded_fold.get_node(node.id)
                self.assertIsNotNone(loaded_node)
                self.assertIn("API key not provided", loaded_node.error)
        
        asyncio.run(test())
    
    def test_real_model_with_api_key(self):
        """Test that real model works with API key (if available)."""
        # Skip this test if MISTRAL_API_KEY is not set
        if not os.environ.get("MISTRAL_API_KEY"):
            self.skipTest("MISTRAL_API_KEY not set")
        
        async def test():
            with tempfile.TemporaryDirectory() as tmpdir:
                project = Project(repo_path=tmpdir, fold_file_path="fold.json")
                
                # Create a prompt node with real model
                node = PromptNode(
                    name="test",
                    prompt_template="Say hello",
                    model="mistral-tiny"
                )
                fold = project.get_fold()
                fold.add_node(node)
                
                # Resolve sprint
                result = await resolve_sprint(project)
                
                # Should succeed
                self.assertTrue(result["success"])
                self.assertEqual(len(result["resolved_nodes"]), 1)
                
                # Check output
                loaded_fold = project.get_fold()
                loaded_node = loaded_fold.get_node(node.id)
                self.assertIsNotNone(loaded_node)
                self.assertIsNotNone(loaded_node.output)
                self.assertGreater(len(loaded_node.output), 0)
        
        asyncio.run(test())
    
    def test_dummy_model_with_resources(self):
        """Test dummy model with resources flowing between nodes."""
        async def test():
            with tempfile.TemporaryDirectory() as tmpdir:
                project = Project(repo_path=tmpdir, fold_file_path="fold.json")
                
                # Create nodes with resources
                gen_node = PromptNode(
                    name="generate",
                    prompt_template="Generate code",
                    model="dummy"
                )
                build_node = ExecuteNode(name="build", command="echo Build")
                
                # Add resource
                output_resource = TextResource(name="output", content="Generated code")
                gen_node.add_emitted_resource("output", output_resource)
                build_node.add_consumed_resource("output", output_resource)
                
                build_node.add_dependency(gen_node.id)
                
                fold = project.get_fold()
                fold.add_node(gen_node)
                fold.add_node(build_node)
                
                # Save fold
                project.save_fold()
                
                # Resolve sprint
                result = await resolve_sprint(project)
                
                self.assertTrue(result["success"])
                self.assertEqual(len(result["resolved_nodes"]), 2)
                
                # Verify resources are intact
                project.load_fold()
                loaded_fold = project.get_fold()
                
                loaded_gen = loaded_fold.get_node(gen_node.id)
                loaded_build = loaded_fold.get_node(build_node.id)
                
                self.assertIn("output", loaded_gen.emitted_resources)
                self.assertIn("output", loaded_build.consumed_resources)
                
                gen_output = loaded_gen.emitted_resources["output"]
                self.assertEqual(gen_output.content, "Generated code")
        
        asyncio.run(test())


if __name__ == "__main__":
    unittest.main()
