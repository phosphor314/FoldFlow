"""Tests for FoldFlow models."""

import unittest
import json
import tempfile
import os

from foldflow.models import (
    Resource, TextResource, SkillResource, ArtifactResource,
    Node, PromptNode, ExecuteNode,
    Fold, Project, ResourceType, NodeType
)


class TestResources(unittest.TestCase):
    """Test resource classes."""
    
    def test_text_resource(self):
        """Test TextResource creation and serialization."""
        resource = TextResource(name="test", content="Hello, world!")
        self.assertEqual(resource.name, "test")
        self.assertEqual(resource.content, "Hello, world!")
        self.assertEqual(resource.get_type(), ResourceType.TEXT)
        
        # Test serialization
        data = resource.to_dict()
        self.assertEqual(data["type"], "text")
        self.assertEqual(data["name"], "test")
        self.assertEqual(data["content"], "Hello, world!")
        
        # Test deserialization
        restored = TextResource.from_dict(data)
        self.assertEqual(restored.name, resource.name)
        self.assertEqual(restored.content, resource.content)
    
    def test_skill_resource(self):
        """Test SkillResource creation and serialization."""
        resource = SkillResource(
            name="coding",
            skill_md_content="# Coding Skill\n...",
            tool_names=["python", "bash"]
        )
        self.assertEqual(resource.name, "coding")
        self.assertEqual(resource.skill_md_content, "# Coding Skill\n...")
        self.assertEqual(resource.tool_names, ["python", "bash"])
        self.assertEqual(resource.get_type(), ResourceType.SKILL)
        
        # Test serialization
        data = resource.to_dict()
        self.assertEqual(data["type"], "skill")
        
        # Test deserialization
        restored = SkillResource.from_dict(data)
        self.assertEqual(restored.name, resource.name)
        self.assertEqual(restored.skill_md_content, resource.skill_md_content)
    
    def test_artifact_resource(self):
        """Test ArtifactResource creation and serialization."""
        resource = ArtifactResource(
            name="perf",
            file_path="/tmp/perf.data",
            metadata={"format": "perf"}
        )
        self.assertEqual(resource.name, "perf")
        self.assertEqual(resource.file_path, "/tmp/perf.data")
        self.assertEqual(resource.metadata, {"format": "perf"})
        self.assertEqual(resource.get_type(), ResourceType.ARTIFACT)
        
        # Test serialization
        data = resource.to_dict()
        self.assertEqual(data["type"], "artifact")
        
        # Test deserialization
        restored = ArtifactResource.from_dict(data)
        self.assertEqual(restored.name, resource.name)
        self.assertEqual(restored.file_path, resource.file_path)


class TestNodes(unittest.TestCase):
    """Test node classes."""
    
    def test_prompt_node(self):
        """Test PromptNode creation and serialization."""
        node = PromptNode(
            name="generate",
            prompt_template="Generate code for {{task}}",
            model="gpt-4",
            temperature=0.5,
            max_tokens=1024
        )
        self.assertEqual(node.name, "generate")
        self.assertEqual(node.prompt_template, "Generate code for {{task}}")
        self.assertEqual(node.model, "gpt-4")
        self.assertEqual(node.temperature, 0.5)
        self.assertEqual(node.max_tokens, 1024)
        self.assertEqual(node.get_type(), NodeType.PROMPT)
        self.assertFalse(node.resolved)
        
        # Test serialization
        data = node.to_dict()
        self.assertEqual(data["type"], "prompt")
        self.assertEqual(data["name"], "generate")
        
        # Test deserialization
        restored = PromptNode.from_dict(data)
        self.assertEqual(restored.name, node.name)
        self.assertEqual(restored.prompt_template, node.prompt_template)
    
    def test_execute_node(self):
        """Test ExecuteNode creation and serialization."""
        node = ExecuteNode(
            name="build",
            command="make build",
            timeout=60
        )
        self.assertEqual(node.name, "build")
        self.assertEqual(node.command, "make build")
        self.assertEqual(node.timeout, 60)
        self.assertEqual(node.get_type(), NodeType.EXECUTE)
        
        # Test serialization
        data = node.to_dict()
        self.assertEqual(data["type"], "execute")
        
        # Test deserialization
        restored = ExecuteNode.from_dict(data)
        self.assertEqual(restored.name, node.name)
        self.assertEqual(restored.command, node.command)
    
    def test_node_resources(self):
        """Test adding resources to nodes."""
        node = PromptNode(name="test")
        
        text_res = TextResource(name="input", content="test")
        node.add_consumed_resource("input", text_res)
        
        self.assertIn("input", node.consumed_resources)
        self.assertEqual(node.get_consumed_resource_names(), ["input"])
        
        output_res = TextResource(name="output", content="result")
        node.add_emitted_resource("output", output_res)
        
        self.assertIn("output", node.emitted_resources)
        self.assertEqual(node.get_emitted_resource_names(), ["output"])
    
    def test_node_dependencies(self):
        """Test adding dependencies to nodes."""
        node = ExecuteNode(name="build")
        node.add_dependency("gen-node")
        node.add_dependency("test-node")
        
        self.assertEqual(node.dependencies, ["gen-node", "test-node"])
        
        # Test that duplicates are not added
        node.add_dependency("gen-node")
        self.assertEqual(node.dependencies, ["gen-node", "test-node"])


class TestFold(unittest.TestCase):
    """Test Fold class."""
    
    def test_add_remove_node(self):
        """Test adding and removing nodes from fold."""
        fold = Fold()
        node = ExecuteNode(name="build")
        
        fold.add_node(node)
        self.assertIn(node.id, fold.nodes)
        
        removed = fold.remove_node(node.id)
        self.assertTrue(removed)
        self.assertNotIn(node.id, fold.nodes)
        
        # Test removing non-existent node
        removed = fold.remove_node("non-existent")
        self.assertFalse(removed)
    
    def test_get_node(self):
        """Test getting nodes from fold."""
        fold = Fold()
        node = ExecuteNode(name="build")
        fold.add_node(node)
        
        retrieved = fold.get_node(node.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "build")
        
        self.assertIsNone(fold.get_node("non-existent"))
    
    def test_dependencies(self):
        """Test dependency management in fold."""
        fold = Fold()
        
        gen_node = PromptNode(name="generate")
        build_node = ExecuteNode(name="build")
        
        build_node.add_dependency(gen_node.id)
        
        fold.add_node(gen_node)
        fold.add_node(build_node)
        
        deps = fold.get_dependencies(build_node.id)
        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0].id, gen_node.id)
        
        dependents = fold.get_dependents(gen_node.id)
        self.assertEqual(len(dependents), 1)
        self.assertEqual(dependents[0].id, build_node.id)
    
    def test_topological_order(self):
        """Test topological ordering of nodes."""
        fold = Fold()
        
        # Create a chain: a -> b -> c
        a = ExecuteNode(name="a")
        b = ExecuteNode(name="b")
        c = ExecuteNode(name="c")
        
        b.add_dependency(a.id)
        c.add_dependency(b.id)
        
        fold.add_node(a)
        fold.add_node(b)
        fold.add_node(c)
        
        order = fold.get_topological_order()
        # a should come before b, b before c
        a_idx = order.index(a.id)
        b_idx = order.index(b.id)
        c_idx = order.index(c.id)
        
        self.assertLess(a_idx, b_idx)
        self.assertLess(b_idx, c_idx)
    
    def test_resolvable_order(self):
        """Test resolvable order (bottom-up)."""
        fold = Fold()
        
        # Create a chain: a -> b -> c
        a = ExecuteNode(name="a")
        b = ExecuteNode(name="b")
        c = ExecuteNode(name="c")
        
        b.add_dependency(a.id)
        c.add_dependency(b.id)
        
        fold.add_node(a)
        fold.add_node(b)
        fold.add_node(c)
        
        order = fold.get_resolvable_order()
        # c should come first (bottom-up), then b, then a
        c_idx = order.index(c.id)
        b_idx = order.index(b.id)
        a_idx = order.index(a.id)
        
        self.assertLess(c_idx, b_idx)
        self.assertLess(b_idx, a_idx)
    
    def test_serialization(self):
        """Test fold serialization and deserialization."""
        fold = Fold()
        
        node1 = ExecuteNode(name="build", command="make")
        node2 = PromptNode(name="generate", prompt_template="Generate")
        
        fold.add_node(node1)
        fold.add_node(node2)
        
        # Serialize
        json_str = fold.to_json()
        data = json.loads(json_str)
        
        self.assertIn("nodes", data)
        self.assertEqual(len(data["nodes"]), 2)
        
        # Deserialize
        restored = Fold.from_json(json_str)
        self.assertEqual(len(restored.nodes), 2)
        
        # Check nodes are correctly restored
        build_node = restored.get_node(node1.id)
        self.assertIsNotNone(build_node)
        self.assertIsInstance(build_node, ExecuteNode)
        self.assertEqual(build_node.command, "make")


class TestProject(unittest.TestCase):
    """Test Project class."""
    
    def test_project_initialization(self):
        """Test project initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Project(repo_path=tmpdir, fold_file_path="fold.json")
            
            # Save fold
            project.save_fold()
            
            fold_path = os.path.join(tmpdir, "fold.json")
            self.assertTrue(os.path.exists(fold_path))
    
    def test_project_load_save(self):
        """Test loading and saving project fold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Project(repo_path=tmpdir, fold_file_path="fold.json")
            
            # Add a node
            fold = project.get_fold()
            node = ExecuteNode(name="build")
            fold.add_node(node)
            
            # Save
            project.save_fold()
            
            # Create new project and load
            project2 = Project(repo_path=tmpdir, fold_file_path="fold.json")
            project2.load_fold()
            
            fold2 = project2.get_fold()
            self.assertEqual(len(fold2.nodes), 1)
            
            loaded_node = fold2.get_node(node.id)
            self.assertIsNotNone(loaded_node)
            self.assertEqual(loaded_node.name, "build")


if __name__ == "__main__":
    unittest.main()
